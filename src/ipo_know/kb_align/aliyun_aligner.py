"""阿里云百炼知识库文档对齐模块.

以 crawler 模块返回的 IPO 有效文件清单为基准, 与阿里云
百炼知识库做全量对齐:

- 有效清单中存在而知识库缺失的文档, 下载 PDF 后经租约上传至
  数据中心, 解析完成后加入索引, 并在本地映射中记录
  fileId 与阿里云 FileId 的对应关系;
- 知识库中存在而不在有效清单内的文档, 从索引删除后连带删除
  数据中心文件.

三所 (SSE/BSE/SZSE) 共用同一知识库, 孤儿判定按标签隔离:
仅标签含 {source}_ 前缀的文档进入删除候选, 其他来源文档
一律跳过. 索引文档列表接口不返回标签, 标签经数据中心文件
详情 (DescribeFile) 逐篇查询获得.

阿里云知识库 ID 由平台生成不可自定义, 项目归属通过文件标签
表达 ({source}_{公司简称}_{审核ID}), fileId 对应关系依赖本地映射.

映射在文件上传成功时即写入落盘, 因此中断重跑不会产生重复
上传: 已映射但未入索引的文件走断点续传, 直接续接解析等待
与批量入索引.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from typing import Any

import httpx
import tenacity
from alibabacloud_bailian20231229 import models as bailian_models
from loguru import logger

from ipo_know.clients.aliyun_knowledge.client import AliyunKnowledgeClient
from ipo_know.kb_align.volc_aligner import build_doc_name


# 本地映射文件名: 按数据来源区分, 存放于与 SQLite 数据库相同的本地应用数据目录.
def _mapping_file_name(source: str) -> str:
    """按数据来源生成映射文件名."""
    return f'aliyun_kb_mapping_{source}.json'

# 分页查询单页大小: list_index_documents 按页码分页拉全量.
LIST_PAGE_SIZE = 100

# 上传并行度: 「下载→上传→等待解析」同时在途的篇数.
UPLOAD_CONCURRENCY = 5

# 入索引批大小: SubmitIndexAddDocumentsJob 单任务携带的文件数.
INDEX_BATCH_SIZE = 50

# 批量删除单批大小: 控制单次请求的 ID 数量, 避免超限.
DELETE_BATCH_SIZE = 10

# PDF 下载超时: 招股书体积大, 给足读取时间, 单位秒.
DOWNLOAD_TIMEOUT_SECONDS = 120

# PDF 下载最大尝试次数 (含首次请求).
DOWNLOAD_MAX_ATTEMPTS = 3

# PDF 下载请求头: bse.cn 对无浏览器 User-Agent 的请求直接
# 返回 403; SSE/SZSE 静态服务器不校验 UA, 附带该头部无副作用.
_DOWNLOAD_HEADERS: dict[str, str] = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) '
        'Gecko/20100101 Firefox/154.0'
    ),
    'Accept': 'application/pdf, */*; q=0.01',
}

# 阿里云文件名上限 128 字符且必须含扩展名.
_FILE_EXT = '.pdf'
_MAX_FILE_NAME_LEN = 128


def build_project_tag(record: Mapping[str, Any], source: str = 'sse') -> str:
    """生成项目归属标签: {source}_{公司简称}_{审核ID}.

    阿里云知识库不使用 category 层级, 以标签区分项目.

    Args:
        record: 有效文件清单条目 (FileItem 转字典).
        source: 数据来源标识, 如 'sse'/'bse'/'szse'.

    Returns:
        项目标签, 如 sse_天博智能_2160 或 bse_杰锋动力_719.
    """
    return f'{source}_{record["companyAbbr"]}_{record["auditId"]}'


def build_file_name(record: Mapping[str, Any]) -> str:
    """生成数据中心文件名: {文件标题}_{更新日期}.pdf.

    与火山文档命名一致, 额外补充扩展名并截断至 128 字符上限.

    Args:
        record: 有效文件清单条目 (FileItem 转字典).

    Returns:
        含 .pdf 扩展名的文件名.
    """
    base = build_doc_name(record)
    max_base = _MAX_FILE_NAME_LEN - len(_FILE_EXT)
    return f'{base[:max_base]}{_FILE_EXT}'


class FileMappingStore:
    """fileId 与阿里云 FileId 的本地映射存储.

    JSON 文件默认存放于本地应用数据目录 (与 SQLite 数据库
    同级), 格式为 {fileId: 阿里云FileId}, 每次变更即落盘.

    Attributes:
        _path: 映射文件路径.
        _data: 内存中的映射字典.
    """

    def __init__(
        self,
        path: pathlib.Path | str | None = None,
        source: str = 'sse',
    ) -> None:
        """初始化映射存储并加载已有映射.

        Args:
            path: 映射文件路径, 为 None 时使用本地应用数据目录
                下的默认位置 (按 source 区分).
            source: 数据来源标识, 用于生成默认映射文件名.
        """
        if path is None:
            app_data_root = os.getenv('LOCALAPPDATA')
            if app_data_root:
                base_dir = pathlib.Path(app_data_root) / 'ipo_know'
            else:
                base_dir = pathlib.Path.home() / '.ipo_know'
            path = base_dir / _mapping_file_name(source)
        self._path = pathlib.Path(path)
        self._data: dict[str, str] = {}
        self._load()

    @property
    def path(self) -> pathlib.Path:
        """映射文件路径."""
        return self._path

    def __len__(self) -> int:
        """返回映射条目数."""
        return len(self._data)

    def __contains__(self, file_id: str) -> bool:
        """判断 fileId 是否已有映射."""
        return file_id in self._data

    def get(self, file_id: str) -> str | None:
        """返回 fileId 对应的阿里云 FileId.

        Args:
            file_id: 文件唯一 ID.

        Returns:
            阿里云 FileId; 无映射时返回 None.
        """
        return self._data.get(file_id)

    def items(self) -> list[tuple[str, str]]:
        """返回全部映射条目 (fileId, 阿里云FileId)."""
        return list(self._data.items())

    def find_file_id_by_aliyun_id(self, aliyun_id: str) -> str | None:
        """按阿里云 FileId 反查 fileId.

        Args:
            aliyun_id: 阿里云 FileId.

        Returns:
            fileId; 无映射时返回 None.
        """
        for file_id, mapped in self._data.items():
            if mapped == aliyun_id:
                return file_id
        return None

    def set(self, file_id: str, aliyun_id: str) -> None:
        """写入一条映射并落盘.

        Args:
            file_id: 文件唯一 ID.
            aliyun_id: 阿里云 FileId.
        """
        self._data[file_id] = aliyun_id
        self._save()

    def remove(self, file_id: str) -> None:
        """删除一条映射并落盘, 不存在时忽略.

        Args:
            file_id: 文件唯一 ID.
        """
        if file_id in self._data:
            del self._data[file_id]
            self._save()

    def _load(self) -> None:
        """从磁盘加载映射文件, 不存在或损坏时视为空映射."""
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                self._data = {
                    str(k): str(v) for k, v in raw.items()
                }
        except (OSError, ValueError) as exc:
            logger.warning('映射文件读取失败, 按空映射处理 | {}', exc)

    def _save(self) -> None:
        """将当前映射写回磁盘."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )


@dataclass
class AliyunAlignReport:
    """阿里云知识库对齐执行结果报告.

    Attributes:
        total_kb_docs: 对齐前知识库中的文档总数.
        valid_count: 有效文件清单条目数.
        to_add_count: 待补充文档数.
        to_delete_count: 待删除文档数.
        dry_run: 是否为预演模式.
        added: 实际补充成功的 fileId 列表.
        deleted: 实际删除成功的阿里云 FileId 列表.
        failed_adds: 补充失败项, (fileId, 原因).
        failed_deletes: 删除失败项, (阿里云FileId, 原因).
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
class AliyunPurgeReport:
    """阿里云知识库清库执行结果报告.

    Attributes:
        dry_run: 是否为预演模式.
        total_docs: 清库前知识库文档总数.
        total_mapped_files: 清库前本地映射条目数.
        deleted_docs: 实际从索引删除的文档数.
        deleted_files: 实际从数据中心删除的文件数.
        failed: 删除失败项, (文档或文件 ID, 原因).
    """

    dry_run: bool = False
    total_docs: int = 0
    total_mapped_files: int = 0
    deleted_docs: int = 0
    deleted_files: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)


class AliyunKBAligner:
    """阿里云百炼知识库文档对齐器.

    以有效文件清单为准, 补齐知识库缺失文档并删除无关文档.
    文档增删均需经过上传/解析/入索引的异步流程, 由客户端内部
    轮询等待完成.

    Attributes:
        _client: 百炼知识库异步客户端.
        _mapping: fileId 本地映射存储.
    """

    def __init__(
        self,
        source: str = 'sse',
        client: AliyunKnowledgeClient | None = None,
        mapping: FileMappingStore | None = None,
    ) -> None:
        """初始化对齐器.

        Args:
            source: 数据来源标识 ('sse'/'bse'/'szse'), 影响
                项目标签前缀和映射文件路径.
            client: 百炼知识库客户端, 为 None 时使用默认配置新建.
            mapping: fileId 映射存储, 为 None 时按 source 生成默认路径.
        """
        self._source = source
        self._client = client or AliyunKnowledgeClient()
        self._mapping = mapping or FileMappingStore(source=source)

    # ==================================================
    # 全量查询
    # ==================================================
    async def list_all_index_documents(
        self,
    ) -> list[bailian_models.ListIndexDocumentsResponseBodyDataDocuments]:
        """分页拉取知识库全量文档.

        list_index_documents 按页码分页, 多次拉取后拼接.

        Returns:
            知识库中全部文档对象列表.
        """
        documents: list[
            bailian_models.ListIndexDocumentsResponseBodyDataDocuments
        ] = []
        page_number = 1
        while True:
            resp = await self._client.list_index_documents(
                bailian_models.ListIndexDocumentsRequest(
                    index_id=self._client.index_id,
                    page_number=page_number,
                    page_size=LIST_PAGE_SIZE,
                )
            )
            page = (
                list(resp.body.data.documents)
                if resp.body.data and resp.body.data.documents
                else []
            )
            documents.extend(page)
            if len(page) < LIST_PAGE_SIZE:
                break
            page_number += 1
        return documents

    # ==================================================
    # 对齐主流程
    # ==================================================
    async def align(
        self,
        valid_files: list[dict[str, Any]],
        *,
        dry_run: bool = False,
    ) -> AliyunAlignReport:
        """以有效文件清单为基准全量对齐知识库.

        通过本地映射判断清单文件状态: 已映射且已入索引的直接
        保留; 已映射但未入索引的走断点续传 (不重传, 续接解析
        等待与批量入索引); 无映射的走完整上传流程.

        孤儿删除按标签隔离: 三所共用同一知识库, 仅标签含当前
        {source}_ 前缀且无法对应到有效清单的文档才删除, 其他
        来源 (含无标签/标签不可读) 的文档一律跳过.

        Args:
            valid_files: crawler collect 返回的有效文件清单.
            dry_run: 为 True 时只输出差异不执行增删.

        Returns:
            对齐执行结果报告.
        """
        index_docs = await self.list_all_index_documents()
        index_ids = {doc.id for doc in index_docs if doc.id}

        keep_ids: set[str] = set()
        resume: list[tuple[dict[str, Any], str]] = []
        fresh: list[dict[str, Any]] = []
        for record in valid_files:
            aliyun_id = self._mapping.get(record['fileId'])
            if not aliyun_id:
                fresh.append(record)
            elif aliyun_id in index_ids:
                keep_ids.add(aliyun_id)
            else:
                # 已映射未入索引: 上传后中断的断点续传对象
                resume.append((record, aliyun_id))

        candidates = [
            doc for doc in index_docs if doc.id not in keep_ids
        ]
        to_delete = await self._filter_by_source_tag(candidates)

        report = AliyunAlignReport(
            total_kb_docs=len(index_ids),
            valid_count=len(valid_files),
            to_add_count=len(resume) + len(fresh),
            to_delete_count=len(to_delete),
            dry_run=dry_run,
        )
        skipped = len(candidates) - len(to_delete)
        logger.info(
            '对齐差异 | 知识库 {} 篇 | 有效清单 {} 篇 | '
            '待补充 {} 篇 (断点续传 {} 篇) | 待删除 {} 篇 | '
            '跳过非本来源文档 {} 篇',
            len(index_ids), len(valid_files),
            len(resume) + len(fresh), len(resume), len(to_delete),
            skipped,
        )

        if dry_run:
            self._log_dry_run(fresh, resume, to_delete)
            return report

        parsed = await self._resume_mapped(resume, fresh, report)
        parsed.extend(await self._upload_all(fresh, report))
        await self._index_parsed(parsed, report)

        total_delete = len(to_delete)
        for idx, doc in enumerate(to_delete, 1):
            await self._remove_doc(doc, report, idx, total_delete)

        logger.info(
            '对齐完成 | 补充 {} 篇 | 删除 {} 篇 | '
            '补充失败 {} 篇 | 删除失败 {} 篇',
            len(report.added), len(report.deleted),
            len(report.failed_adds), len(report.failed_deletes),
        )
        return report

    async def _filter_by_source_tag(
        self,
        docs: list[
            bailian_models.ListIndexDocumentsResponseBodyDataDocuments
        ],
    ) -> list[
        bailian_models.ListIndexDocumentsResponseBodyDataDocuments
    ]:
        """按来源标签前缀过滤孤儿删除候选集.

        三所共用同一知识库, 仅标签含 {source}_ 前缀的文档允许
        进入删除候选; 其他来源标签、无标签或标签查询失败的文档
        一律跳过 (既不删除也不参与比对).

        索引文档列表接口不返回标签, 标签经数据中心文件详情
        (DescribeFile, FileId 与索引文档 ID 同源) 逐篇查询.

        Args:
            docs: 待判定的候选文档 (知识库存在但不在保留集).

        Returns:
            标签以 {source}_ 开头的候选文档列表.
        """
        prefix = f'{self._source}_'
        kept: list[
            bailian_models.ListIndexDocumentsResponseBodyDataDocuments
        ] = []
        skipped = 0
        for doc in docs:
            tags = await self._doc_tags(doc.id or '')
            if tags is None:
                logger.warning(
                    '孤儿判定跳过: 标签查询失败 | {} | {}',
                    doc.id, doc.name,
                )
                skipped += 1
                continue
            if any(tag.startswith(prefix) for tag in tags):
                kept.append(doc)
            else:
                logger.debug(
                    '孤儿判定跳过: 非本来源标签 | {} | {} | {}',
                    doc.id, doc.name, tags,
                )
                skipped += 1
        if skipped:
            logger.info('跳过非本来源文档 {} 篇', skipped)
        return kept

    async def _doc_tags(self, aliyun_id: str) -> list[str] | None:
        """查询数据中心文件标签.

        Args:
            aliyun_id: 阿里云 FileId (与索引文档 ID 同源).

        Returns:
            标签列表 (可为空列表); 文件不存在或查询失败时
            返回 None.
        """
        try:
            resp = await self._client.describe_file(aliyun_id)
        except Exception:
            return None
        data = resp.body.data
        if data is None:
            return None
        return list(data.tags) if data.tags else []

    def _log_dry_run(
        self,
        fresh: list[dict[str, Any]],
        resume: list[tuple[dict[str, Any], str]],
        to_delete: list[
            bailian_models.ListIndexDocumentsResponseBodyDataDocuments
        ],
    ) -> None:
        """预演模式输出待增删明细.

        Args:
            fresh: 待全新上传的文件清单条目.
            resume: 断点续传对象, (清单条目, 阿里云FileId).
            to_delete: 待删除的知识库文档对象.
        """
        for record in fresh:
            logger.info(
                '[dry-run] 待补充 | {} | {}',
                record['fileId'], build_file_name(record),
            )
        for record, aliyun_id in resume:
            logger.info(
                '[dry-run] 断点续传 | {} | {}',
                record['fileId'], aliyun_id,
            )
        for doc in to_delete:
            logger.info(
                '[dry-run] 待删除 | {} | {}', doc.id, doc.name,
            )

    # ==================================================
    # 单篇增删
    # ==================================================
    async def _resume_mapped(
        self,
        resume: list[tuple[dict[str, Any], str]],
        fresh: list[dict[str, Any]],
        report: AliyunAlignReport,
    ) -> list[tuple[str, str]]:
        """断点续传: 复用已上传未入索引的文件, 不重新上传.

        逐篇查询数据中心文件解析状态: 成功的直接进入批量入
        索引队列; 仍在解析的等待完成; 解析失败或文件已被删除
        的清理映射后降级为重新上传.

        Args:
            resume: (清单条目, 阿里云FileId) 断点续传对象列表.
            fresh: 重新上传队列, 降级条目原地追加.
            report: 执行结果报告, 续传失败原地追加.

        Returns:
            (上交所fileId, 阿里云FileId) 解析成功待入索引列表.
        """
        parsed: list[tuple[str, str]] = []
        requeue_start = len(fresh)
        total = len(resume)
        for idx, (record, aliyun_id) in enumerate(resume, 1):
            file_id = record['fileId']
            status = await self._describe_file_status(aliyun_id)
            if status is None:
                # 文件已不存在: 清除映射转重新上传
                self._mapping.remove(file_id)
                fresh.append(record)
                continue
            if status != 'PARSE_SUCCESS':
                logger.info(
                    '断点续传 [{}/{}] 等待解析 | {} | {}',
                    idx, total, file_id, aliyun_id,
                )
                try:
                    await self._client.wait_file_parsed(aliyun_id)
                except Exception as exc:
                    final = await self._describe_file_status(aliyun_id)
                    if final == 'PARSE_FAILED':
                        logger.warning(
                            '断点续传解析失败, 删除后重传 | {} | {}',
                            file_id, exc,
                        )
                        await self._delete_file_quiet(aliyun_id)
                        self._mapping.remove(file_id)
                        fresh.append(record)
                    else:  # 等待超时等: 保留映射, 下次续传重试
                        logger.error(
                            '断点续传失败 [{}/{}] | {} | {}',
                            idx, total, file_id, exc,
                        )
                        report.failed_adds.append((file_id, str(exc)))
                    continue
            logger.info(
                '断点续传 [{}/{}] 解析完成, 等待批量入索引 | {} | {}',
                idx, total, file_id, aliyun_id,
            )
            parsed.append((file_id, aliyun_id))
        if total:
            logger.info(
                '断点续传阶段完成 | 续传成功 {} / {} 篇 | 转重传 {} 篇',
                len(parsed), total, len(fresh) - requeue_start,
            )
        return parsed

    async def _upload_all(
        self,
        fresh: list[dict[str, Any]],
        report: AliyunAlignReport,
    ) -> list[tuple[str, str]]:
        """并行上传新文件并等待解析, 返回解析成功清单.

        上传阶段以 UPLOAD_CONCURRENCY 为上限并行执行
        「下载→上传→等待解析」, 入索引由调用方统一批量提交.

        Args:
            fresh: 待全新上传的有效文件清单条目.
            report: 执行结果报告, 原地更新.

        Returns:
            (上交所fileId, 阿里云FileId) 解析成功列表.
        """
        if not fresh:
            return []
        total = len(fresh)
        semaphore = asyncio.Semaphore(UPLOAD_CONCURRENCY)

        async def worker(
            idx: int, record: dict[str, Any],
        ) -> tuple[str, str] | None:
            """限流并发下单篇文档的上传与解析."""
            async with semaphore:
                return await self._upload_and_parse(
                    record, idx, total, report,
                )

        results = await asyncio.gather(
            *(worker(i, r) for i, r in enumerate(fresh, 1))
        )
        parsed = [pair for pair in results if pair is not None]
        logger.info(
            '上传阶段完成 | 解析成功待入索引 {} / {} 篇',
            len(parsed), total,
        )
        return parsed

    async def _upload_and_parse(
        self,
        record: dict[str, Any],
        index: int,
        total: int,
        report: AliyunAlignReport,
    ) -> tuple[str, str] | None:
        """上传并解析单篇文档 (不执行入索引).

        上传成功即写入映射, 任一步失败记入报告, 不中断其他文档.

        Args:
            record: 有效文件清单条目.
            index: 当前进度序号 (从 1 开始).
            total: 待补充总数.
            report: 执行结果报告, 原地更新.

        Returns:
            (上交所fileId, 阿里云FileId); 失败时返回 None.
        """
        file_id = record['fileId']
        logger.info(
            '补充文档 [{}/{}] 开始下载上传 | {}', index, total, file_id,
        )
        try:
            content = await self._download_pdf(record['filePath'])
            aliyun_id = await self._client.upload_file(
                file_name=build_file_name(record),
                content=content,
                tags=[build_project_tag(record, self._source)],
                original_file_url=record['filePath'],
            )
            # 映射即传即写: 后续解析/入索引阶段中断也不致重传
            self._mapping.set(file_id, aliyun_id)
            await self._client.wait_file_parsed(aliyun_id)
            logger.info(
                '补充文档 [{}/{}] 解析完成, 等待批量入索引 | {}',
                index, total, file_id,
            )
            return file_id, aliyun_id
        except Exception as exc:  # 单篇失败不中断整体对齐
            logger.error(
                '补充文档失败 [{}/{}] | {} | {}',
                index, total, file_id, exc,
            )
            report.failed_adds.append((file_id, str(exc)))
            return None

    async def _index_parsed(
        self,
        parsed: list[tuple[str, str]],
        report: AliyunAlignReport,
    ) -> None:
        """分批提交已解析文档入索引并记录结果.

        映射已在上传成功时写入; 入索引失败篇记入报告, 因映射
        仍在, 下次对齐走断点续传重试入索引而不会重传.

        Args:
            parsed: (上交所fileId, 阿里云FileId) 列表.
            report: 执行结果报告, 原地更新.
        """
        if not parsed:
            return
        batches = [
            parsed[i:i + INDEX_BATCH_SIZE]
            for i in range(0, len(parsed), INDEX_BATCH_SIZE)
        ]
        for batch_idx, batch in enumerate(batches, 1):
            batch_ids = [aliyun_id for _, aliyun_id in batch]
            try:
                failed_ids = set(
                    await self._client.add_documents_to_index(batch_ids)
                )
            except Exception as exc:  # 整批任务失败
                logger.error(
                    '入索引批次失败 [{}/{}] | {}',
                    batch_idx, len(batches), exc,
                )
                for file_id, _ in batch:
                    report.failed_adds.append((file_id, str(exc)))
                continue
            ok_count = 0
            for file_id, aliyun_id in batch:
                if aliyun_id in failed_ids:
                    report.failed_adds.append(
                        (file_id, '入索引任务中该文档失败')
                    )
                    continue
                report.added.append(file_id)
                ok_count += 1
                logger.info(
                    '补充文档成功 | {} -> {}', file_id, aliyun_id,
                )
            logger.info(
                '入索引批次完成 [{}/{}] | 成功 {} / {} 篇',
                batch_idx, len(batches), ok_count, len(batch),
            )

    async def _remove_doc(
        self,
        doc: bailian_models.ListIndexDocumentsResponseBodyDataDocuments,
        report: AliyunAlignReport,
        index: int,
        total: int,
    ) -> None:
        """删除一篇无关文档: 移出索引并删除数据中心文件.

        Args:
            doc: 待删除的知识库文档对象.
            report: 执行结果报告, 原地更新.
            index: 当前进度序号 (从 1 开始).
            total: 待删除总数.
        """
        aliyun_id = doc.id or ''
        try:
            await self._client.delete_index_document(
                bailian_models.DeleteIndexDocumentRequest(
                    index_id=self._client.index_id,
                    document_ids=[aliyun_id],
                )
            )
            await self._client.delete_files(
                bailian_models.DeleteFilesRequest(file_ids=[aliyun_id])
            )
            sse_id = self._mapping.find_file_id_by_aliyun_id(aliyun_id)
            if sse_id:
                self._mapping.remove(sse_id)
            report.deleted.append(aliyun_id)
            logger.info(
                '删除文档成功 [{}/{}] | {} | {}',
                index, total, aliyun_id, doc.name,
            )
        except Exception as exc:  # 单篇失败不中断整体对齐
            logger.error(
                '删除文档失败 [{}/{}] | {} | {}',
                index, total, aliyun_id, exc,
            )
            report.failed_deletes.append((aliyun_id, str(exc)))

    async def _download_pdf(self, url: str) -> bytes:
        """下载披露文件 PDF 字节内容.

        携带浏览器 UA 请求头 (bse.cn 拒绝非浏览器 UA), 并对
        HTTP 状态错误与网络错误做指数退避重试.

        Args:
            url: 文件完整下载 URL (清单 filePath).

        Returns:
            PDF 字节内容.

        Raises:
            httpx.HTTPStatusError: 服务端返回 4xx/5xx, 重试耗尽后抛出.
            httpx.RequestError: 网络层错误, 重试耗尽后抛出.
        """
        retry_decorator = tenacity.retry(
            stop=tenacity.stop_after_attempt(DOWNLOAD_MAX_ATTEMPTS),
            wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
            retry=tenacity.retry_if_exception_type(
                (httpx.HTTPStatusError, httpx.RequestError),
            ),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(logger, 'WARNING'),
        )

        @retry_decorator
        async def _do() -> bytes:
            async with httpx.AsyncClient(
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
                follow_redirects=True,
                headers=_DOWNLOAD_HEADERS,
            ) as http:
                resp = await http.get(url)
                resp.raise_for_status()
                return resp.content

        return await _do()

    async def _describe_file_status(self, aliyun_id: str) -> str | None:
        """查询数据中心文件解析状态.

        Args:
            aliyun_id: 阿里云 FileId.

        Returns:
            解析状态 (如 PARSE_SUCCESS/PARSING/PARSE_FAILED);
            文件不存在或查询失败时返回 None.
        """
        try:
            resp = await self._client.describe_file(aliyun_id)
        except Exception:
            return None
        data = resp.body.data
        return data.status if data else None

    async def _delete_file_quiet(self, aliyun_id: str) -> None:
        """尽力删除数据中心文件, 失败仅告警不中断.

        Args:
            aliyun_id: 阿里云 FileId.
        """
        try:
            await self._client.delete_files(
                bailian_models.DeleteFilesRequest(file_ids=[aliyun_id])
            )
        except Exception as exc:
            logger.warning(
                '删除数据中心文件失败 | {} | {}', aliyun_id, exc,
            )

    # ==================================================
    # 清库
    # ==================================================
    async def purge(self, *, dry_run: bool = False) -> AliyunPurgeReport:
        """清空知识库: 删除索引全部文档及对应数据中心文件.

        阿里云切片随索引文档删除而删除, 且不支持无文件过滤的
        全量切片列举, 因此不单独处理孤儿切片.

        Args:
            dry_run: 为 True 时只盘点数量不执行删除.

        Returns:
            清库执行结果报告.
        """
        report = AliyunPurgeReport(dry_run=dry_run)
        index_docs = await self.list_all_index_documents()
        report.total_docs = len(index_docs)
        report.total_mapped_files = len(self._mapping)
        logger.info(
            '清库盘点 | 索引文档 {} 篇 | 本地映射 {} 条',
            report.total_docs, report.total_mapped_files,
        )
        if dry_run:
            return report

        index_ids = [doc.id for doc in index_docs if doc.id]
        report.deleted_docs = await self._purge_index(index_ids, report)

        # 数据中心文件 = 索引内文件 + 映射中记录的文件
        file_ids = set(index_ids) | {
            aliyun_id for _, aliyun_id in self._mapping.items()
        }
        deleted_file_ids = await self._purge_data_files(
            sorted(file_ids), report,
        )
        report.deleted_files = len(deleted_file_ids)

        for file_id, aliyun_id in self._mapping.items():
            if aliyun_id in deleted_file_ids:
                self._mapping.remove(file_id)

        logger.info(
            '清库完成 | 索引删除 {} 篇 | 数据中心删除 {} 个 | '
            '失败 {} 项',
            report.deleted_docs, report.deleted_files, len(report.failed),
        )
        return report

    async def _purge_index(
        self, doc_ids: list[str], report: AliyunPurgeReport,
    ) -> int:
        """分批删除索引内全部文档.

        Args:
            doc_ids: 待删除的阿里云 FileId 列表.
            report: 清库报告, 失败项原地追加.

        Returns:
            实际删除的文档数.
        """
        deleted = 0
        for i in range(0, len(doc_ids), DELETE_BATCH_SIZE):
            batch = doc_ids[i:i + DELETE_BATCH_SIZE]
            try:
                await self._client.delete_index_document(
                    bailian_models.DeleteIndexDocumentRequest(
                        index_id=self._client.index_id,
                        document_ids=batch,
                    )
                )
                deleted += len(batch)
            except Exception as exc:  # 单批失败不中断
                logger.error('批量删除索引文档失败 | {} | {}', batch, exc)
                for doc_id in batch:
                    report.failed.append((doc_id, str(exc)))
            logger.info('索引文档删除进度 | 累计 {} 篇', deleted)
        return deleted

    async def _purge_data_files(
        self, file_ids: list[str], report: AliyunPurgeReport,
    ) -> set[str]:
        """分批删除数据中心全部文件.

        Args:
            file_ids: 待删除的阿里云 FileId 列表.
            report: 清库报告, 失败项原地追加.

        Returns:
            实际删除成功的 FileId 集合.
        """
        deleted: set[str] = set()
        total = len(file_ids)
        for i in range(0, len(file_ids), DELETE_BATCH_SIZE):
            batch = file_ids[i:i + DELETE_BATCH_SIZE]
            try:
                await self._client.delete_files(
                    bailian_models.DeleteFilesRequest(file_ids=batch)
                )
                deleted.update(batch)
            except Exception as exc:  # 单批失败不中断
                logger.error('批量删除数据中心文件失败 | {} | {}',
                             batch, exc)
                for file_id in batch:
                    report.failed.append((file_id, str(exc)))
            logger.info(
                '数据中心文件删除进度 [{}/{}]', len(deleted), total,
            )
        return deleted
