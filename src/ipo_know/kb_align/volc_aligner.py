"""火山知识库文档与切片对齐模块.

以 crawler 模块返回的上交所 IPO 有效文件清单为基准, 与火山
VikingDB 知识库做全量对齐:

- 有效清单中存在而知识库缺失的文档, 以 fileId 加字母前缀映射
  为 doc_id 调用 add_doc_v2 补充;
- 知识库中存在而不在有效清单内的文档, 先分页查出全部切片
  逐个删除, 再删除文档本体.

比对依据为文档唯一标识 (fileId 经 file_id_to_doc_id 映射后与
doc_id 比较).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from loguru import logger
from vikingdb.knowledge import AddDocV2Request
from vikingdb.knowledge import DeletePointRequest
from vikingdb.knowledge import ListDocsRequest
from vikingdb.knowledge import ListPointsRequest

from ipo_know.clients.viking_knowledge.client import VikingKnowledgeClient


# 上传文档使用的切片策略资源 ID. 非敏感信息且可能有多种取值,
# 按需在此修改即可.
STRATEGY_RESOURCE_ID = 'kb-strategy-59c0da9fd88c3b5a'

# doc_id 前缀: 知识库要求 doc_id 首字符必须为字母或下划线,
# 而上交所 fileId 可能以数字开头 (纯数字或十六进制 UUID),
# 直接透传会被服务端拒绝, 统一加字母前缀做可逆映射.
DOC_ID_PREFIX = 'sse'

# 分页查询单页大小: list_docs / list_points 接口单次查询有
# 数量上限, 必须分页多次拉取后拼接.
LIST_PAGE_SIZE = 100

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


def file_id_to_doc_id(file_id: str) -> str:
    """把上交所 fileId 映射为合法的知识库 doc_id.

    映射可逆: 去掉 DOC_ID_PREFIX 前缀即可还原 fileId.

    Args:
        file_id: 上交所文件唯一 ID.

    Returns:
        以字母开头、仅含字母数字下划线的 doc_id.
    """
    return f'{DOC_ID_PREFIX}_{file_id}'


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

    Attributes:
        _client: 火山知识库异步客户端.
    """

    def __init__(self, client: VikingKnowledgeClient | None = None) -> None:
        """初始化对齐器.

        Args:
            client: 火山知识库客户端, 为 None 时使用默认配置新建.
        """
        self._client = client or VikingKnowledgeClient()

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
            resp = await self._client.list_docs(
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
            resp = await self._client.list_points(
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
    ) -> AlignReport:
        """以有效文件清单为基准全量对齐知识库.

        Args:
            valid_files: crawler collect 返回的有效文件清单.
            dry_run: 为 True 时只输出差异不执行增删.

        Returns:
            对齐执行结果报告.
        """
        valid_ids = {
            file_id_to_doc_id(record['fileId']) for record in valid_files
        }
        kb_doc_ids = await self.list_all_doc_ids()

        to_add = [
            record for record in valid_files
            if file_id_to_doc_id(record['fileId']) not in kb_doc_ids
        ]
        to_delete = sorted(kb_doc_ids - valid_ids)

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

        total_add = len(to_add)
        for idx, record in enumerate(to_add, 1):
            await self._add_doc(record, report, idx, total_add)
        total_delete = len(to_delete)
        for idx, doc_id in enumerate(to_delete, 1):
            await self._remove_doc(doc_id, report, idx, total_delete)

        logger.info(
            '对齐完成 | 补充 {} 篇 | 删除 {} 篇 | '
            '补充失败 {} 篇 | 删除失败 {} 篇',
            len(report.added), len(report.deleted),
            len(report.failed_adds), len(report.failed_deletes),
        )
        return report

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

        Args:
            record: 有效文件清单条目.
            report: 执行结果报告, 原地更新.
            index: 当前进度序号 (从 1 开始).
            total: 待补充总数.
        """
        doc_id = file_id_to_doc_id(record['fileId'])
        try:
            await self._client.add_doc_v2(
                AddDocV2Request(
                    doc_id=doc_id,
                    doc_name=build_doc_name(record),
                    doc_type='pdf',
                    uri=record['filePath'],
                    path_segments=[build_project_dir_name(record)],
                    strategy_resource_id=STRATEGY_RESOURCE_ID,
                )
            )
            report.added.append(doc_id)
            logger.info(
                '补充文档成功 [{}/{}] | {}', index, total, doc_id,
            )
        except Exception as exc:  # 单篇失败不中断整体对齐
            logger.error(
                '补充文档失败 [{}/{}] | {} | {}',
                index, total, doc_id, exc,
            )
            report.failed_adds.append((doc_id, str(exc)))

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
                await self._client.delete_point(
                    DeletePointRequest(point_id=point_id)
                )
            await self._client.delete_doc(doc_id)
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
    # 清库
    # ==================================================
    async def purge(self, *, dry_run: bool = False) -> PurgeReport:
        """清空知识库: 删除全部切片与全部文档.

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
            resp = await self._client.list_points(
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
            resp = await self._client.list_points(
                ListPointsRequest(offset=0, limit=LIST_PAGE_SIZE)
            )
            points = list(resp.result.point_list) if resp.result else []
            page = [p.point_id for p in points if p.point_id]
            if not page:
                break
            progress = 0
            for point_id in page:
                try:
                    await self._client.delete_point(
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
            resp = await self._client.list_docs(
                ListDocsRequest(offset=0, limit=LIST_PAGE_SIZE)
            )
            docs = list(resp.result.doc_list) if resp.result else []
            page = [d.doc_id for d in docs if d.doc_id]
            if not page:
                break
            progress = 0
            for doc_id in page:
                try:
                    await self._client.delete_doc(doc_id)
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
