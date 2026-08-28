"""火山知识库文档与切片对齐模块.

以 crawler 模块返回的 IPO 有效文件清单为基准, 与火山
VikingDB 知识库做全量对齐:

- 有效清单中存在而知识库缺失的文档, 以 fileId 加数据源前缀
  映射为 doc_id 调用 add_doc_v2 补充;
- 知识库中存在而不在有效清单内的文档, 先分页查出全部切片
  逐个删除, 再删除文档本体.

三所共用同一知识库, doc_id 采用 {source}_{fileId} 可逆映射,
孤儿删除仅针对当前数据源前缀的文档, 其他数据源文档一律
跳过, 互不误删.

比对依据为文档唯一标识 (fileId 经 file_id_to_doc_id 映射后与
doc_id 比较).
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from typing import Any

import tenacity
from loguru import logger
from vikingdb.knowledge import AddDocV2Request
from vikingdb.knowledge import AddDocV2Response
from vikingdb.knowledge import DeletePointRequest
from vikingdb.knowledge import DocInfo
from vikingdb.knowledge import ListDocsRequest
from vikingdb.knowledge import ListDocsResponse
from vikingdb.knowledge import ListPointsRequest
from vikingdb.knowledge import ListPointsResponse
from vikingdb.knowledge.models.base import CommonResponse

from ipo_know.clients.viking_knowledge.client import VikingKnowledgeClient


# 上传文档使用的切片策略资源 ID 默认值. 留空表示不传该
# 参数, 由知识库使用自身默认切片策略 (SDK 序列化时对
# None 字段 exclude_none, 但空字符串会原样提交, 故留空
# 场景必须不传而非传 '').
STRATEGY_RESOURCE_ID = ''

# doc_id 前缀: 知识库要求 doc_id 首字符必须为字母或下划线,
# 而上交所 fileId 可能以数字开头 (纯数字或十六进制 UUID),
# 直接透传会被服务端拒绝, 统一加字母前缀做可逆映射.
# 同时作为多数据源隔离的默认 source: 三所共库时各所分别
# 使用 sse_/bse_/szse_ 前缀, 孤儿删除按前缀隔离互不误删.
DOC_ID_PREFIX = 'sse'

# 分页查询单页大小: list_docs / list_points 接口单次查询有
# 数量上限, 必须分页多次拉取后拼接.
LIST_PAGE_SIZE = 100

# 上传并发度: 补充文档同时在途的最大篇数.
UPLOAD_CONCURRENCY = 5

# 删除并发度: 孤儿文档同时在途的最大篇数.
DELETE_CONCURRENCY = 3

# 单次 API 调用最大尝试次数 (含首次请求), 失败指数退避重试.
API_MAX_ATTEMPTS = 3

# add_doc_v2 文档内容去重错误码: 服务端检测到重复文档时返回,
# 对齐重跑场景下视为「已存在」幂等跳过而非失败.
DUPLICATE_DOC_CODE = 1001002

# SDK 确定性错误码 (vikingdb.knowledge.exceptions.EXCEPTION_MAP 中
# 除服务端内部错误 1000028 与限流 1000029 外的全部错误码):
# 请求参数、权限、资源不存在等客户端确定性错误, 重试无法改变
# 结果, 直接上抛避免每项白耗数秒.
_DETERMINISTIC_ERROR_CODES: frozenset[int] = frozenset({
    1000001, 1000002, 1000003, 1000004, 1000005, 1000006,
    1000007, 1000008, 1000010, 1000011, 1000013, 1000014,
    1000015, 1000016, 1000017, 1000018, 1000019, 1000020,
    1000021, 1000022, 1000023, 1000024, 1000025, 1000026,
    1000030, 1001001, 1001010, 1002001,
})

# fileTypeMap → 披露文件类别名
# 来源: c36_file_type_mapping_report.md 映射表 (I + 三位类别码 + 阶段码)
CATEGORY_NAMES: dict[str, str] = {
    'I0011': '招股说明书(申报稿)',
    'I0012': '招股说明书(上会稿)',
    'I0013': '招股说明书(注册稿)',
    'I0021': '财务报告及审计报告(申报稿)',
    'I0022': '财务报告及审计报告(上会稿)',
    'I0023': '财务报告及审计报告(注册稿)',
    'I0031': '法律意见书(申报稿)',
    'I0032': '法律意见书(上会稿)',
    'I0033': '法律意见书(注册稿)',
    'I0051': '发行保荐书(申报稿)',
    'I0052': '发行保荐书(上会稿)',
    'I0053': '发行保荐书(注册稿)',
    'I0061': '上市保荐书(申报稿)',
    'I0062': '上市保荐书(上会稿)',
    'I0063': '上市保荐书(注册稿)',
    'I1010': '注册批复',
    'I1020': '终止审核决定',
    'I2010': '上市委审议会议公告',
    'I2020': '上市委审议会议结果公告',
}

# 知识库文档名禁止的特殊字符与空白
_INVALID_NAME_CHARS_RE = re.compile(r"[\\/:*?\"<>|'\s]+")


def _is_duplicate_error(exc: BaseException) -> bool:
    """判断异常是否为 add_doc_v2 的文档内容去重错误.

    服务端检测到重复文档时返回错误码 1001002, SDK 将其承载
    在 VikingException 的 .code 属性中 (该码不在 SDK 的
    EXCEPTION_MAP 内, 以基类 VikingKnowledgeException 抛出).

    Args:
        exc: 待判定的异常对象.

    Returns:
        为去重错误码时返回 True.
    """
    return str(getattr(exc, 'code', None)) == str(DUPLICATE_DOC_CODE)


def _is_retryable_add_error(exc: BaseException) -> bool:
    """判断 add_doc_v2 异常是否值得重试.

    去重错误为确定性结果, 重试无意义, 交由调用方幂等处理;
    其余异常 (网络抖动/限流等) 均重试.

    Args:
        exc: 待判定的异常对象.

    Returns:
        可重试时返回 True.
    """
    return not _is_duplicate_error(exc)


def _is_retryable_api_error(exc: BaseException) -> bool:
    """判断通用 API 异常是否值得重试.

    仅对可恢复错误重试: 网络类异常、HTTP 5xx 与 429 限流、
    服务端内部错误 (1000028)、限流错误 (1000029) 及无错误码
    的未知异常. SDK EXCEPTION_MAP 中的确定性客户端错误码
    (参数非法、资源不存在、权限不足等) 重试无法改变结果,
    直接短路交由调用方记入失败报告.

    Args:
        exc: 待判定的异常对象.

    Returns:
        可重试时返回 True.
    """
    status_code = getattr(exc, 'status_code', None)
    if isinstance(status_code, int) and (
        status_code >= 500 or status_code == 429
    ):
        return True
    code = getattr(exc, 'code', None)
    if isinstance(code, int):
        return code not in _DETERMINISTIC_ERROR_CODES
    # 网络超时、连接异常等无 code/status_code 的异常一律重试.
    return True


# API 调用通用重试: 指数退避 1~10 秒, 最多 API_MAX_ATTEMPTS 次;
# SDK 确定性错误码直接短路不重试.
_RETRY_API = tenacity.retry(
    stop=tenacity.stop_after_attempt(API_MAX_ATTEMPTS),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    retry=tenacity.retry_if_exception(_is_retryable_api_error),
    reraise=True,
    before_sleep=tenacity.before_sleep_log(logger, 'WARNING'),
)

# add_doc_v2 专用重试: 去重错误为确定性结果, 重试无意义,
# 直接短路交由调用方按「已存在」幂等处理.
_RETRY_ADD_DOC = tenacity.retry(
    stop=tenacity.stop_after_attempt(API_MAX_ATTEMPTS),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    retry=tenacity.retry_if_exception(_is_retryable_add_error),
    reraise=True,
    before_sleep=tenacity.before_sleep_log(logger, 'WARNING'),
)


def file_id_to_doc_id(file_id: str, source: str = DOC_ID_PREFIX) -> str:
    """把 fileId 映射为合法的知识库 doc_id.

    映射可逆: 去掉 {source}_ 前缀即可还原 fileId. source
    同时承担多数据源隔离职责, 三所共库时各所文档按前缀区分.

    Args:
        file_id: 文件唯一 ID.
        source: 数据源标识, 默认 DOC_ID_PREFIX (sse).

    Returns:
        以字母开头、仅含字母数字下划线的 doc_id.
    """
    return f'{source}_{file_id}'


def category_name(file_type_map: str) -> str:
    """返回 fileTypeMap 对应的披露文件类别名.

    Args:
        file_type_map: 文件类型映射编码.

    Returns:
        类别名; 映射表外的编码回退为 其他_{file_type_map}.
    """
    return CATEGORY_NAMES.get(file_type_map, f'其他_{file_type_map}')


def sanitize_kb_name(name: str) -> str:
    r"""清洗知识库文档名/目录名中的非法字符.

    知识库 doc_name 不能包含特殊用途字符 < > : ' " / \\ | ? *
    及空格, 统一替换为下划线.

    Args:
        name: 原始名称.

    Returns:
        清洗后的名称; 清洗后为空时回退为 unknown.
    """
    cleaned = _INVALID_NAME_CHARS_RE.sub('_', name).strip(' .')
    return cleaned or 'unknown'


def build_project_dir_name(record: Mapping[str, Any]) -> str:
    """生成知识库目录名: {公司名}_{审核ID}.

    与下载脚本的本地目录模式一致, 以区分同一公司的多次申报.

    Args:
        record: 有效文件清单条目 (FileItem 转字典).

    Returns:
        清洗后的目录名, 作为 add_doc_v2 的 path_segments 元素.
    """
    return sanitize_kb_name(f'{record["companyName"]}_{record["auditId"]}')


def build_doc_name(record: Mapping[str, Any]) -> str:
    """生成知识库文档名: {文件标题}_{更新日期}.

    不带类别前缀与扩展名. fileTitle 缺失或为空时回退为
    fileId, 兼容不含该键的清单记录.

    Args:
        record: 有效文件清单条目 (FileItem 转字典).

    Returns:
        清洗后的文档名.
    """
    title = (record.get('fileTitle') or '').strip() or record['fileId']
    date_suffix = (record.get('fileUpdTime') or '')[:8]
    parts = [title]
    if date_suffix:
        parts.append(date_suffix)
    return sanitize_kb_name('_'.join(parts))


@dataclass
class AlignReport:
    """对齐执行结果报告.

    Attributes:
        total_kb_docs: 对齐前知识库中的文档总数.
        valid_count: 有效文件清单条目数.
        to_add_count: 待补充文档数.
        to_delete_count: 待删除文档数.
        dry_run: 是否为预演模式.
        added: 实际补充成功的 doc_id 列表.
        deleted: 实际删除成功的 doc_id 列表.
        failed_adds: 补充失败项, (doc_id, 原因).
        failed_deletes: 删除失败项, (doc_id, 原因).
        skipped_existing: 因服务端去重 (已存在) 跳过的 doc_id 列表.
        parse_failed: 提交后解析失败项, (doc_id, 失败原因).
    """

    total_kb_docs: int = 0
    valid_count: int = 0
    to_add_count: int = 0
    to_delete_count: int = 0
    dry_run: bool = False
    added: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    failed_adds: list[tuple[str, str]] = field(default_factory=list)
    failed_deletes: list[tuple[str, str]] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    parse_failed: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class PurgeReport:
    """清库执行结果报告.

    Attributes:
        dry_run: 是否为预演模式.
        total_docs: 清库前文档总数.
        total_points: 清库前切片总数 (含孤儿切片).
        deleted_docs: 实际删除的文档数.
        deleted_points: 实际删除的切片数.
        failed: 删除失败项, (doc_id 或 point_id, 原因).
    """

    dry_run: bool = False
    total_docs: int = 0
    total_points: int = 0
    deleted_docs: int = 0
    deleted_points: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)


class VolcKBAligner:
    """火山知识库文档对齐器.

    以有效文件清单为准, 补齐知识库缺失文档并删除无关文档.
    doc_id 采用 {source}_{fileId} 可逆映射, 孤儿删除仅作用于
    本实例 source 前缀的文档, 其他数据源文档一律跳过, 三所
    共库时互不误删.

    Attributes:
        _client: 火山知识库异步客户端.
        _source: 数据源标识, 驱动 doc_id 前缀与孤儿删除隔离.
        _strategy_resource_id: 上传文档使用的切片策略资源
            ID, 留空时不传该参数, 走知识库默认切片策略.
    """

    def __init__(
        self,
        client: VikingKnowledgeClient | None = None,
        source: str = DOC_ID_PREFIX,
        strategy_resource_id: str = STRATEGY_RESOURCE_ID,
    ) -> None:
        """初始化对齐器.

        Args:
            client: 火山知识库客户端, 为 None 时使用默认配置新建.
            source: 数据源标识 (如 sse/bse/szse), 决定 doc_id
                前缀与孤儿删除的作用范围, 默认 DOC_ID_PREFIX.
            strategy_resource_id: 上传文档使用的切片策略资源
                ID (如 kb-strategy-xxxx), 留空时不传该参数,
                由知识库使用自身默认切片策略.
        """
        self._client = client or VikingKnowledgeClient()
        self._source = source
        self._strategy_resource_id = strategy_resource_id

    # ==================================================
    # 底层 API 重试包装
    # ==================================================
    @_RETRY_ADD_DOC
    async def _api_add_doc(
        self, request: AddDocV2Request,
    ) -> AddDocV2Response:
        """add_doc_v2 包装, 失败指数退避重试, 去重错误不重试."""
        return await self._client.add_doc_v2(request)

    @_RETRY_API
    async def _api_delete_doc(self, doc_id: str) -> CommonResponse:
        """delete_doc 包装, 失败指数退避重试."""
        return await self._client.delete_doc(doc_id)

    @_RETRY_API
    async def _api_delete_point(
        self, request: DeletePointRequest,
    ) -> CommonResponse:
        """delete_point 包装, 失败指数退避重试."""
        return await self._client.delete_point(request)

    @_RETRY_API
    async def _api_get_doc(self, doc_id: str) -> DocInfo:
        """get_doc 包装, 失败指数退避重试."""
        return await self._client.get_doc(doc_id)

    @_RETRY_API
    async def _api_list_docs(
        self, request: ListDocsRequest,
    ) -> ListDocsResponse:
        """list_docs 包装, 失败指数退避重试."""
        return await self._client.list_docs(request)

    @_RETRY_API
    async def _api_list_points(
        self, request: ListPointsRequest,
    ) -> ListPointsResponse:
        """list_points 包装, 失败指数退避重试."""
        return await self._client.list_points(request)

    # ==================================================
    # 全量查询
    # ==================================================
    async def list_all_doc_ids(self) -> set[str]:
        """分页拉取知识库全量文档的 doc_id 集合.

        list_docs 单次查询有数量上限, 按 offset 分页多次拉取
        后拼接去重.

        Returns:
            知识库中全部文档的 doc_id 集合.
        """
        doc_ids: set[str] = set()
        offset = 0
        while True:
            resp = await self._api_list_docs(
                ListDocsRequest(offset=offset, limit=LIST_PAGE_SIZE)
            )
            page = list(resp.result.doc_list) if resp.result else []
            for doc in page:
                if doc.doc_id:
                    doc_ids.add(doc.doc_id)
            if len(page) < LIST_PAGE_SIZE:
                break
            offset += LIST_PAGE_SIZE
        return doc_ids

    async def _list_point_ids(self, doc_id: str) -> list[str]:
        """分页拉取指定文档的全部切片 ID.

        Args:
            doc_id: 文档 ID.

        Returns:
            该文档下全部切片的 point_id 列表.
        """
        point_ids: list[str] = []
        offset = 0
        while True:
            resp = await self._api_list_points(
                ListPointsRequest(
                    doc_ids=[doc_id], offset=offset, limit=LIST_PAGE_SIZE,
                )
            )
            page = list(resp.result.point_list) if resp.result else []
            for point in page:
                if point.point_id:
                    point_ids.append(point.point_id)
            if len(page) < LIST_PAGE_SIZE:
                break
            offset += LIST_PAGE_SIZE
        return point_ids

    # ==================================================
    # 对齐主流程
    # ==================================================
    async def align(
        self,
        valid_files: list[dict[str, Any]],
        *,
        dry_run: bool = False,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> AlignReport:
        """以有效文件清单为基准全量对齐知识库.

        孤儿删除按当前 source 的 doc_id 前缀隔离: 仅
        {source}_ 前缀文档进入差集删除候选, 其他数据源
        文档一律跳过 (既不删除也不参与比对).

        Args:
            valid_files: crawler collect 返回的有效文件清单.
            dry_run: 为 True 时只输出差异不执行增删.
            on_progress: 可选进度回调 (已完成篇数, 待补充总篇数);
                补充阶段每完成一篇回调一次, 成功/去重跳过/失败均计.
                预演模式不回调.

        Returns:
            对齐执行结果报告.
        """
        prefix = f'{self._source}_'
        valid_ids = {
            file_id_to_doc_id(record['fileId'], self._source)
            for record in valid_files
        }
        kb_doc_ids = await self.list_all_doc_ids()

        own_ids = {d for d in kb_doc_ids if d.startswith(prefix)}
        skipped_other = len(kb_doc_ids) - len(own_ids)
        if skipped_other:
            logger.info('其他数据源文档跳过 {} 篇', skipped_other)

        to_add = [
            record
            for record in valid_files
            if file_id_to_doc_id(record['fileId'], self._source)
            not in kb_doc_ids
        ]
        to_delete = sorted(own_ids - valid_ids)

        report = AlignReport(
            total_kb_docs=len(kb_doc_ids),
            valid_count=len(valid_files),
            to_add_count=len(to_add),
            to_delete_count=len(to_delete),
            dry_run=dry_run,
        )
        logger.info(
            '对齐差异 | 知识库 {} 篇 | 有效清单 {} 篇 | '
            '待补充 {} 篇 | 待删除 {} 篇',
            len(kb_doc_ids), len(valid_files), len(to_add), len(to_delete),
        )

        if dry_run:
            self._log_dry_run(to_add, to_delete)
            return report

        await self._add_all(to_add, report, on_progress)
        await self._delete_all(to_delete, report)
        await self._verify_added(report)

        logger.info(
            '对齐完成 | 补充 {} 篇 | 已存在跳过 {} 篇 | 删除 {} 篇 | '
            '补充失败 {} 篇 | 删除失败 {} 篇 | 解析失败 {} 篇',
            len(report.added), len(report.skipped_existing),
            len(report.deleted), len(report.failed_adds),
            len(report.failed_deletes), len(report.parse_failed),
        )
        return report

    async def _add_all(
        self,
        to_add: list[dict[str, Any]],
        report: AlignReport,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """并发补充文档, 以 UPLOAD_CONCURRENCY 限流.

        进度序号经 enumerate 预分配, 并发下仍保持稳定.

        Args:
            to_add: 待补充的文件清单条目.
            report: 执行结果报告, 原地更新.
            on_progress: 可选进度回调 (已完成篇数, 总篇数).
        """
        if not to_add:
            return
        total = len(to_add)
        semaphore = asyncio.Semaphore(UPLOAD_CONCURRENCY)
        done = 0

        async def worker(idx: int, record: dict[str, Any]) -> None:
            """限流并发执行单篇文档补充."""
            nonlocal done
            async with semaphore:
                await self._add_doc(record, report, idx, total)
            done += 1
            if on_progress is not None:
                on_progress(done, total)

        await asyncio.gather(
            *(worker(i, r) for i, r in enumerate(to_add, 1)),
        )

    async def _delete_all(
        self,
        to_delete: list[str],
        report: AlignReport,
    ) -> None:
        """并发删除孤儿文档, 以 DELETE_CONCURRENCY 限流.

        Args:
            to_delete: 待删除的 doc_id 列表.
            report: 执行结果报告, 原地更新.
        """
        if not to_delete:
            return
        total = len(to_delete)
        semaphore = asyncio.Semaphore(DELETE_CONCURRENCY)

        async def worker(idx: int, doc_id: str) -> None:
            """限流并发执行单篇文档删除."""
            async with semaphore:
                await self._remove_doc(doc_id, report, idx, total)

        await asyncio.gather(
            *(worker(i, d) for i, d in enumerate(to_delete, 1)),
        )

    def _log_dry_run(
        self,
        to_add: list[dict[str, Any]],
        to_delete: list[str],
    ) -> None:
        """预演模式输出待增删明细.

        Args:
            to_add: 待补充的文件清单条目.
            to_delete: 待删除的 doc_id 列表.
        """
        for record in to_add:
            logger.info(
                '[dry-run] 待补充 | {} | {}',
                record['fileId'], build_doc_name(record),
            )
        for doc_id in to_delete:
            logger.info('[dry-run] 待删除 | {}', doc_id)

    # ==================================================
    # 单篇增删
    # ==================================================
    async def _add_doc(
        self,
        record: dict[str, Any],
        report: AlignReport,
        index: int,
        total: int,
    ) -> None:
        """按有效清单条目补充一篇文档, 失败记入报告不中断.

        服务端返回去重错误码时按「已存在」幂等跳过, 不计失败.

        Args:
            record: 有效文件清单条目.
            report: 执行结果报告, 原地更新.
            index: 当前进度序号 (从 1 开始).
            total: 待补充总数.
        """
        doc_id = file_id_to_doc_id(record['fileId'], self._source)
        try:
            await self._api_add_doc(self._build_add_request(record, doc_id))
            report.added.append(doc_id)
            logger.info(
                '补充文档成功 [{}/{}] | {}', index, total, doc_id,
            )
        except Exception as exc:  # 单篇失败不中断整体对齐
            if _is_duplicate_error(exc):
                report.skipped_existing.append(doc_id)
                logger.info(
                    '补充文档跳过 (已存在) [{}/{}] | {}',
                    index, total, doc_id,
                )
                return
            logger.error(
                '补充文档失败 [{}/{}] | {} | {}',
                index, total, doc_id, exc,
            )
            report.failed_adds.append((doc_id, str(exc)))

    def _build_add_request(
        self, record: dict[str, Any], doc_id: str,
    ) -> AddDocV2Request:
        """构造 add_doc_v2 请求 (文档来源接缝).

        当前为 URL 直传模式: uri 直接取清单 filePath 的原始
        文件链接, 由服务端负责拉取与解析. 未来切换本地下载
        上传模式时仅需替换本方法, _add_doc 与并发/重试流程
        无需改动.

        切片策略 ID 留空时不传入 strategy_resource_id, 由
        知识库使用自身默认切片策略 (SDK 序列化虽对 None
        做 exclude_none, 但空字符串会原样提交, 故留空场景
        必须不传而非传 '').

        Args:
            record: 有效文件清单条目.
            doc_id: 映射后的知识库文档 ID.

        Returns:
            待提交的 add_doc_v2 请求.
        """
        kwargs: dict[str, Any] = {
            'doc_id': doc_id,
            'doc_name': build_doc_name(record),
            'doc_type': 'pdf',
            'uri': record['filePath'],
            'path_segments': [build_project_dir_name(record)],
        }
        if self._strategy_resource_id:
            kwargs['strategy_resource_id'] = (
                self._strategy_resource_id
            )
        return AddDocV2Request(**kwargs)

    async def _remove_doc(
        self,
        doc_id: str,
        report: AlignReport,
        index: int,
        total: int,
    ) -> None:
        """删除一篇无关文档: 先删全部切片再删文档, 失败记入报告.

        Args:
            doc_id: 待删除文档 ID.
            report: 执行结果报告, 原地更新.
            index: 当前进度序号 (从 1 开始).
            total: 待删除总数.
        """
        try:
            point_ids = await self._list_point_ids(doc_id)
            for point_id in point_ids:
                await self._api_delete_point(
                    DeletePointRequest(point_id=point_id)
                )
            await self._api_delete_doc(doc_id)
            report.deleted.append(doc_id)
            logger.info(
                '删除文档成功 [{}/{}] | {} | 连带切片 {} 个',
                index, total, doc_id, len(point_ids),
            )
        except Exception as exc:  # 单篇失败不中断整体对齐
            logger.error(
                '删除文档失败 [{}/{}] | {} | {}',
                index, total, doc_id, exc,
            )
            report.failed_deletes.append((doc_id, str(exc)))

    # ==================================================
    # 解析状态核验
    # ==================================================
    async def _verify_added(self, report: AlignReport) -> None:
        """核验本轮新增文档的服务端解析状态.

        服务端解析为异步过程: 提交成功仅代表入库受理, 解析
        结果需另行读取. 此处对 report.added 限并发逐篇调用
        get_doc 做一次快照核验 (不轮询等待): 解析失败记入
        report.parse_failed, 仍在解析的仅记日志. 核验自身
        异常只 warning 不阻断对齐流程.

        Args:
            report: 执行结果报告, parse_failed 原地更新.
        """
        if not report.added:
            return
        total = len(report.added)
        logger.info('解析状态核验 (快照) | 共 {} 篇', total)
        semaphore = asyncio.Semaphore(UPLOAD_CONCURRENCY)

        async def worker(doc_id: str) -> None:
            """限流并发核验单篇文档的解析状态."""
            async with semaphore:
                await self._verify_one(doc_id, report)

        try:
            await asyncio.gather(*(worker(d) for d in report.added))
        except Exception as exc:  # 核验自身异常不阻断对齐
            logger.warning('解析状态核验异常, 跳过核验 | {}', exc)
        logger.info(
            '解析状态核验完成 | 核验 {} 篇 | 解析失败 {} 篇',
            total, len(report.parse_failed),
        )

    async def _verify_one(
        self, doc_id: str, report: AlignReport,
    ) -> None:
        """核验单篇文档解析状态, 异常仅 warning 不阻断.

        Args:
            doc_id: 待核验的新增文档 ID.
            report: 执行结果报告, parse_failed 原地更新.
        """
        try:
            info = await self._api_get_doc(doc_id)
        except Exception as exc:
            logger.warning(
                '解析状态核验失败 | {} | {}', doc_id, exc,
            )
            return
        status = info.status
        if status is not None and status.failed_code:
            reason = status.failed_msg or f'failed_code={status.failed_code}'
            report.parse_failed.append((doc_id, reason))
            logger.warning('文档解析失败 | {} | {}', doc_id, reason)
            return
        state = status.process_status if status else None
        logger.debug(
            '文档解析快照 | {} | process_status={}', doc_id, state,
        )

    # ==================================================
    # 清库
    # ==================================================
    async def purge(self, *, dry_run: bool = False) -> PurgeReport:
        """清空知识库: 删除全部切片与全部文档.

        注意: 本方法为全库清空, 不按 source 前缀隔离, 会
        删除库内所有数据源 (含其他所) 的文档, 慎用.

        切片先于文档删除, 且拉取切片时不按 doc_id 过滤, 覆盖
        文档已删除但切片残留的孤儿切片场景.

        Args:
            dry_run: 为 True 时只盘点数量不执行删除.

        Returns:
            清库执行结果报告.
        """
        report = PurgeReport(dry_run=dry_run)
        doc_ids = await self.list_all_doc_ids()
        report.total_docs = len(doc_ids)
        report.total_points = await self._count_all_points()
        logger.info(
            '清库盘点 | 文档 {} 篇 | 切片 {} 个',
            report.total_docs, report.total_points,
        )
        if dry_run:
            return report

        report.deleted_points = await self._purge_points(
            report, report.total_points,
        )
        report.deleted_docs = await self._purge_docs(
            report, report.total_docs,
        )
        logger.info(
            '清库完成 | 删除文档 {} 篇 | 删除切片 {} 个 | 失败 {} 项',
            report.deleted_docs, report.deleted_points, len(report.failed),
        )
        return report

    async def _count_all_points(self) -> int:
        """分页盘点知识库全部切片数量 (不按 doc_id 过滤).

        Returns:
            切片总数.
        """
        total = 0
        offset = 0
        while True:
            resp = await self._api_list_points(
                ListPointsRequest(offset=offset, limit=LIST_PAGE_SIZE)
            )
            page = list(resp.result.point_list) if resp.result else []
            total += len(page)
            if len(page) < LIST_PAGE_SIZE:
                break
            offset += LIST_PAGE_SIZE
        return total

    async def _purge_points(
        self, report: PurgeReport, total: int,
    ) -> int:
        """循环删除全部切片, 每轮始终取首页避免 offset 漂移.

        Args:
            report: 清库报告, 失败项原地追加.
            total: 盘点得到的切片总数, 用于进度展示.

        Returns:
            实际删除的切片数.
        """
        deleted = 0
        while True:
            resp = await self._api_list_points(
                ListPointsRequest(offset=0, limit=LIST_PAGE_SIZE)
            )
            points = list(resp.result.point_list) if resp.result else []
            page = [p.point_id for p in points if p.point_id]
            if not page:
                break
            progress = 0
            for point_id in page:
                try:
                    await self._api_delete_point(
                        DeletePointRequest(point_id=point_id)
                    )
                    deleted += 1
                    progress += 1
                except Exception as exc:  # 单项失败不中断
                    logger.error('删除切片失败 | {} | {}', point_id, exc)
                    report.failed.append((point_id, str(exc)))
            logger.info('切片删除进度 [{}/{}]', deleted, total)
            if progress == 0:  # 本轮无任何进展, 终止以防死循环
                logger.error('本轮切片删除无进展, 终止清库切片阶段')
                break
        return deleted

    async def _purge_docs(
        self, report: PurgeReport, total: int,
    ) -> int:
        """循环删除全部文档, 每轮始终取首页避免 offset 漂移.

        Args:
            report: 清库报告, 失败项原地追加.
            total: 盘点得到的文档总数, 用于进度展示.

        Returns:
            实际删除的文档数.
        """
        deleted = 0
        while True:
            resp = await self._api_list_docs(
                ListDocsRequest(offset=0, limit=LIST_PAGE_SIZE)
            )
            docs = list(resp.result.doc_list) if resp.result else []
            page = [d.doc_id for d in docs if d.doc_id]
            if not page:
                break
            progress = 0
            for doc_id in page:
                try:
                    await self._api_delete_doc(doc_id)
                    deleted += 1
                    progress += 1
                except Exception as exc:  # 单项失败不中断
                    logger.error('删除文档失败 | {} | {}', doc_id, exc)
                    report.failed.append((doc_id, str(exc)))
            logger.info('文档删除进度 [{}/{}]', deleted, total)
            if progress == 0:  # 本轮无任何进展, 终止以防死循环
                logger.error('本轮文档删除无进展, 终止清库文档阶段')
                break
        return deleted
