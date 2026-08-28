"""阿里云百炼知识库文档对齐模块.

以 crawler 模块返回的 IPO 有效文件清单为基准, 与阿里云
百炼知识库做全量对齐:

- 有效清单中存在而知识库缺失的文档, 下载 PDF 后经租约上传至
  数据中心, 解析完成后加入索引;
- 知识库中存在而不在有效清单内的文档, 从索引删除后连带删除
  数据中心文件.

本地映射已废弃, 文件对应关系改由云端标签锚点承载: 上传时为每
个文件写入 ``fileid_`` 哈希锚点等标签 (锚点为哈希而非原始 fileId,
见 ``aliyun_tags``), 对齐时并行拉取索引文档与数据中心文件两份只读快
照, 从标签反向解析锚点哈希并在本地用同一函数换算匹配, 构建倒排索引.
中断重跑不产生重复上传: 已上传未
入索引的文件按快照状态续接 (解析成功直接入索引 / 处理中续接等
待 / 失败态删除后重传).

三所 (SSE/BSE/SZSE) 共用同一知识库, 孤儿判定按标签隔离: 仅标签
含本交易所裸标签的文档进入删除候选, 无标签 / 他来源 / 查无此文
件的文档一律跳过 (保守隔离).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from typing import Any

import httpx
import tenacity
from alibabacloud_bailian20231229 import models as bailian_models
from loguru import logger

from ipo_know.clients.aliyun_knowledge.client import FILE_FAILED_STATUSES
from ipo_know.clients.aliyun_knowledge.client import AliyunKnowledgeClient
from ipo_know.clients.aliyun_knowledge.client import DataCenterFileItem
from ipo_know.kb_align.aliyun_tags import build_file_tags
from ipo_know.kb_align.aliyun_tags import extract_fileid
from ipo_know.kb_align.aliyun_tags import fileid_anchor
from ipo_know.kb_align.aliyun_tags import has_source_tag
from ipo_know.kb_align.volc_aligner import build_doc_name


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

# 数据中心文件解析处理中状态集合: 仍在上传/解析流水线中的中间
# 态, 续接时经 wait_file_parsed 实时等待, 孤儿清理一律跳过以防
# 误杀在途任务.
_PARSE_PENDING_STATUSES = frozenset({
    'INIT',
    'UPLOADING',
    'UPLOADED',
    'PARSING',
    'IN_PARSE_QUEUE',
})

# 本应用已知交易所来源: 三所共用同一知识库, 本应用上传的文件均
# 携带其一的裸标签, 用于清库时识别本应用管理的文件.
_APP_SOURCES = ('sse', 'bse', 'szse')


def has_app_tags(tags: Iterable[str]) -> bool:
    """判断云端文件标签是否属于本应用管理.

    含 ``fileid_`` 锚点标签, 或含任一交易所裸来源标签即视为本应
    用上传的文件; 两者皆无的视为外部文件 (如控制台手工上传).

    Args:
        tags: 云端文件的标签列表.

    Returns:
        属于本应用管理时返回 True.
    """
    return bool(extract_fileid(tags)) or any(
        has_source_tag(tags, src) for src in _APP_SOURCES
    )


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


@dataclass
class AliyunAlignReport:
    """阿里云知识库对齐执行结果报告.

    Attributes:
        total_kb_docs: 对齐前知识库中的文档总数.
        valid_count: 有效文件清单条目数.
        to_add_count: 待补充文档数 (续接 + 全新上传).
        to_delete_count: 待删除的索引孤儿文档数.
        dry_run: 是否为预演模式.
        added: 实际补充成功的 fileId 列表.
        deleted: 实际删除成功的阿里云 FileId 列表, 含索引孤儿
            文档与数据中心残留文件两类.
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

    清库仅删除索引全部文档与「有本应用标签」的数据中心文件;
    无本应用标签 (无 fileid_ 锚点且无交易所裸来源标签) 的外部文
    件 (如控制台手工上传) 一律排除保留, 只统计告警, 收敛破坏半径.

    Attributes:
        dry_run: 是否为预演模式.
        total_docs: 清库前知识库文档总数.
        total_data_files: 清库前数据中心文件总数.
        deleted_docs: 实际从索引删除的文档数.
        deleted_files: 实际从数据中心删除的文件数.
        excluded_external_files: 无本应用标签而排除保留的数据中心文
            件数.
        failed: 删除失败项, (文档或文件 ID, 原因).
    """

    dry_run: bool = False
    total_docs: int = 0
    total_data_files: int = 0
    deleted_docs: int = 0
    deleted_files: int = 0
    excluded_external_files: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)


class AliyunKBAligner:
    """阿里云百炼知识库文档对齐器.

    以有效文件清单为准, 补齐知识库缺失文档并删除无关文档.
    文档增删均需经过上传/解析/入索引的异步流程, 由客户端内部
    轮询等待完成. 文件对应关系依赖云端 ``fileid_`` 标签锚点,
    本地不持久化任何映射.

    Attributes:
        _source: 数据来源标识, 决定上传标签与孤儿判定前缀.
        _client: 百炼知识库异步客户端.
    """

    def __init__(
        self,
        source: str = 'sse',
        client: AliyunKnowledgeClient | None = None,
    ) -> None:
        """初始化对齐器.

        Args:
            source: 数据来源标识 ('sse'/'bse'/'szse'), 影响
                上传标签与孤儿判定的交易所裸标签.
            client: 百炼知识库客户端, 为 None 时使用默认配置新建.
        """
        self._source = source
        self._client = client or AliyunKnowledgeClient()

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
        on_progress: Callable[[int, int], None] | None = None,
    ) -> AliyunAlignReport:
        """以有效文件清单为基准全量对齐知识库.

        并行拉取索引文档与数据中心文件两份只读快照, 任一列举
        失败异常向上抛出整体中止, 绝不持半量快照进入删除阶段.

        通过云端 ``fileid_`` 哈希锚点标签判断清单文件状态: 命中且已
        入索引的直接保留; 命中但未入索引的按快照状态续接 (解析
        成功直接入索引 / 处理中续接等待 / 失败态删除后重传); 无
        标签命中的走完整上传流程.

        孤儿删除按标签隔离: 三所共用同一知识库, 仅标签含本交易
        所裸标签且无法对应到有效清单的文档才删除, 无标签 / 他
        来源 / 查无此文件的文档一律跳过.

        Args:
            valid_files: crawler collect 返回的有效文件清单.
            dry_run: 为 True 时只输出差异不执行增删.
            on_progress: 可选进度回调 (已完成篇数, 待补充总篇数);
                续接与上传阶段每完成一篇回调一次, 分母随降级重传动态增长.
                预演模式不回调.

        Returns:
            对齐执行结果报告.
        """
        index_docs, data_files = await asyncio.gather(
            self.list_all_index_documents(),
            self._client.list_all_data_center_files(),
        )
        index_ids = {doc.id for doc in index_docs if doc.id}

        files_by_anchor, tags_by_aliyun_id = self._build_snapshot(
            data_files, index_ids,
        )

        keep_ids: set[str] = set()
        resume: list[tuple[dict[str, Any], DataCenterFileItem]] = []
        fresh: list[dict[str, Any]] = []
        for record in valid_files:
            # 本地换算同一哈希后查倒排索引, 与打标侧同函数同 strip 语义
            anchor = fileid_anchor(record['fileId'])
            item = files_by_anchor.get(anchor)
            if item is None:
                fresh.append(record)
            elif item.file_id in index_ids:
                keep_ids.add(item.file_id)
            else:
                # 已上传未入索引: 按快照状态走续接
                resume.append((record, item))

        candidates = [
            doc for doc in index_docs if doc.id not in keep_ids
        ]
        to_delete = self._filter_by_source_tag(
            candidates, tags_by_aliyun_id,
        )

        matched_ids = {item.file_id for item in files_by_anchor.values()}
        residual = self._residual_data_files(
            data_files, index_ids, matched_ids,
        )

        report = AliyunAlignReport(
            total_kb_docs=len(index_ids),
            valid_count=len(valid_files),
            to_add_count=len(resume) + len(fresh),
            to_delete_count=len(to_delete),
            dry_run=dry_run,
        )
        logger.info(
            '对齐差异 | 索引 {} 篇 | 数据中心 {} 个 | 有效清单 {} 篇 | '
            '待补充 {} 篇 (续接 {} 篇) | 待删除索引文档 {} 篇 | '
            '待清理残留文件 {} 个',
            len(index_ids), len(data_files), len(valid_files),
            len(resume) + len(fresh), len(resume),
            len(to_delete), len(residual),
        )

        if dry_run:
            self._log_dry_run(fresh, resume, to_delete, residual)
            return report

        # 单篇完成计数: 续接与上传两阶段共用同一计数盒,
        # 分母取续接+重传队列实时长度 (降级重传会动态增长).
        on_item_done: Callable[[], None] | None
        if on_progress is None:
            on_item_done = None
        else:
            cb = on_progress
            done_box = [0]

            def on_item_done() -> None:
                done_box[0] += 1
                cb(done_box[0], len(resume) + len(fresh))

        parsed = await self._resume_cloud(
            resume, fresh, report, on_item_done,
        )
        parsed.extend(
            await self._upload_all(fresh, report, on_item_done)
        )
        await self._index_parsed(parsed, report)

        total_delete = len(to_delete)
        for idx, doc in enumerate(to_delete, 1):
            await self._remove_doc(doc, report, idx, total_delete)

        total_residual = len(residual)
        for idx, item in enumerate(residual, 1):
            await self._remove_residual_file(
                item, report, idx, total_residual,
            )

        logger.info(
            '对齐完成 | 补充 {} 篇 | 删除 {} 篇 | '
            '补充失败 {} 篇 | 删除失败 {} 篇',
            len(report.added), len(report.deleted),
            len(report.failed_adds), len(report.failed_deletes),
        )
        return report

    def _build_snapshot(
        self,
        data_files: list[DataCenterFileItem],
        index_ids: set[str],
    ) -> tuple[dict[str, DataCenterFileItem], dict[str, list[str]]]:
        """由数据中心快照构建两张内存查找表.

        倒排索引 {锚点哈希 -> 云端文件} 经 ``fileid_`` 标签解析获
        得, key 为哈希锚点而非原始 fileId; 发现重复锚点 (同一哈希对
        应多个云端文件, 含哈希碰撞与重复上传) 时告警并保留已入索引者,
        其余交由孤儿/残留清理.

        Args:
            data_files: 数据中心全量文件快照.
            index_ids: 索引文档 ID 集合, 用于重复锚点取舍.

        Returns:
            (files_by_anchor, tags_by_aliyun_id) 两张查找表.
        """
        files_by_anchor: dict[str, DataCenterFileItem] = {}
        tags_by_aliyun_id: dict[str, list[str]] = {}
        for item in data_files:
            if item.file_id:
                tags_by_aliyun_id[item.file_id] = item.tags
            anchor = extract_fileid(item.tags)
            if not anchor:
                continue
            prev = files_by_anchor.get(anchor)
            if prev is None:
                files_by_anchor[anchor] = item
                continue
            # 重复锚点: 保留已在索引者, 其余按孤儿清理
            if (
                item.file_id in index_ids
                and prev.file_id not in index_ids
            ):
                kept, dropped = item, prev
            else:
                kept, dropped = prev, item
            logger.warning(
                '发现重复 fileid 锚点 | {} | 保留={} | 待清理={}',
                anchor, kept.file_id, dropped.file_id,
            )
            files_by_anchor[anchor] = kept
        return files_by_anchor, tags_by_aliyun_id

    def _filter_by_source_tag(
        self,
        docs: list[
            bailian_models.ListIndexDocumentsResponseBodyDataDocuments
        ],
        tags_by_aliyun_id: Mapping[str, list[str]],
    ) -> list[
        bailian_models.ListIndexDocumentsResponseBodyDataDocuments
    ]:
        """按来源裸标签过滤孤儿删除候选集.

        三所共用同一知识库, 仅标签含本交易所裸标签的文档允许进
        入删除候选; 无标签、他来源标签或数据中心查无此文件的文档
        一律跳过 (既不删除也不参与比对, 保守隔离).

        标签取自数据中心快照, 不再逐篇 DescribeFile.

        Args:
            docs: 待判定的候选文档 (知识库存在但不在保留集).
            tags_by_aliyun_id: {阿里云FileId -> 标签列表} 快照表.

        Returns:
            含本交易所裸标签的候选文档列表.
        """
        kept: list[
            bailian_models.ListIndexDocumentsResponseBodyDataDocuments
        ] = []
        skipped = 0
        for doc in docs:
            doc_id = doc.id or ''
            tags = tags_by_aliyun_id.get(doc_id)
            if tags is None:
                logger.debug(
                    '孤儿判定跳过: 数据中心查无此文件 | {} | {}',
                    doc_id, doc.name,
                )
                skipped += 1
                continue
            if has_source_tag(tags, self._source):
                kept.append(doc)
            else:
                logger.debug(
                    '孤儿判定跳过: 无标签或非本来源 | {} | {} | {}',
                    doc_id, doc.name, tags,
                )
                skipped += 1
        if skipped:
            logger.info('跳过非本来源文档 {} 篇', skipped)
        return kept

    def _residual_data_files(
        self,
        data_files: list[DataCenterFileItem],
        index_ids: set[str],
        matched_ids: set[str],
    ) -> list[DataCenterFileItem]:
        """筛选数据中心侧的本来源残留文件.

        带本交易所裸标签、不在索引、且未匹配到有效清单的云端文
        件判定为残留 (含重复 ``fileid_`` 标签取舍后的落选者); 解
        析处理中状态一律跳过, 防误杀在途任务.

        Args:
            data_files: 数据中心全量文件快照.
            index_ids: 索引文档 ID 集合.
            matched_ids: 已匹配有效清单的云端文件 ID 集合.

        Returns:
            待删除的残留文件列表.
        """
        residual: list[DataCenterFileItem] = []
        skipped = 0
        for item in data_files:
            if not item.file_id or item.file_id in index_ids:
                continue
            if item.file_id in matched_ids:
                continue
            if not has_source_tag(item.tags, self._source):
                continue
            if item.status in _PARSE_PENDING_STATUSES:
                logger.debug(
                    '残留清理跳过: 处理中状态 | {} | 状态={}',
                    item.file_id, item.status,
                )
                skipped += 1
                continue
            residual.append(item)
        if skipped:
            logger.info('残留清理跳过处理中文件 {} 个', skipped)
        return residual

    def _log_dry_run(
        self,
        fresh: list[dict[str, Any]],
        resume: list[tuple[dict[str, Any], DataCenterFileItem]],
        to_delete: list[
            bailian_models.ListIndexDocumentsResponseBodyDataDocuments
        ],
        residual: list[DataCenterFileItem],
    ) -> None:
        """预演模式输出待增删明细.

        Args:
            fresh: 待全新上传的文件清单条目.
            resume: 续接对象, (清单条目, 云端文件快照).
            to_delete: 待删除的索引孤儿文档对象.
            residual: 待清理的数据中心残留文件.
        """
        for record in fresh:
            logger.info(
                '[dry-run] 待补充 | {} | {}',
                record['fileId'], build_file_name(record),
            )
        for record, item in resume:
            logger.info(
                '[dry-run] 续接 | {} | {} | 状态={}',
                record['fileId'], item.file_id, item.status,
            )
        for doc in to_delete:
            logger.info(
                '[dry-run] 待删除 | {} | {}', doc.id, doc.name,
            )
        for item in residual:
            logger.info(
                '[dry-run] 待清理残留 | {} | {}',
                item.file_id, item.file_name,
            )

    # ==================================================
    # 单篇增删
    # ==================================================
    async def _resume_cloud(
        self,
        resume: list[tuple[dict[str, Any], DataCenterFileItem]],
        fresh: list[dict[str, Any]],
        report: AliyunAlignReport,
        on_item_done: Callable[[], None] | None = None,
    ) -> list[tuple[str, str]]:
        """续接: 复用已上传未入索引的云端文件, 不重新上传.

        解析状态取自数据中心快照, 不再逐篇 DescribeFile: 解析成
        功的直接进入批量入索引队列; 处理中状态的经
        wait_file_parsed 实时续接等待; 显式失败终态删除云端文
        件后降级为重新上传; 未知状态保守保留文件并记入失败清单,
        待下轮快照重试, 严禁误删健康文件.

        Args:
            resume: (清单条目, 云端文件快照) 续接对象列表.
            fresh: 重新上传队列, 降级条目原地追加.
            report: 执行结果报告, 续传失败原地追加.
            on_item_done: 可选单篇完成钩子, 每个条目任一出循环口调用一次.

        Returns:
            (本地fileId, 阿里云FileId) 解析成功待入索引列表.
        """
        parsed: list[tuple[str, str]] = []
        requeue_start = len(fresh)
        total = len(resume)

        def tick() -> None:
            """单篇完成计数钩子 (允许为空)."""
            if on_item_done is not None:
                on_item_done()

        for idx, (record, item) in enumerate(resume, 1):
            file_id = record['fileId']
            aliyun_id = item.file_id
            status = item.status
            if status == 'PARSE_SUCCESS':
                logger.info(
                    '续接 [{}/{}] 解析完成, 等待批量入索引 | {} | {}',
                    idx, total, file_id, aliyun_id,
                )
                parsed.append((file_id, aliyun_id))
                tick()
                continue
            if status in _PARSE_PENDING_STATUSES:
                logger.info(
                    '续接 [{}/{}] 等待解析 | {} | {} | 状态={}',
                    idx, total, file_id, aliyun_id, status,
                )
                try:
                    await self._client.wait_file_parsed(aliyun_id)
                except Exception as exc:
                    final = await self._describe_file_status(aliyun_id)
                    if final in FILE_FAILED_STATUSES:
                        logger.warning(
                            '续接解析失败, 删除后重传 | {} | {} | 状态={}',
                            file_id, exc, final,
                        )
                        await self._delete_file_quiet(aliyun_id)
                        fresh.append(record)
                    else:  # 等待超时等: 文件仍在, 下次续接重试
                        logger.error(
                            '续接失败 [{}/{}] | {} | {}',
                            idx, total, file_id, exc,
                        )
                        report.failed_adds.append((file_id, str(exc)))
                    tick()
                    continue
                logger.info(
                    '续接 [{}/{}] 解析完成, 等待批量入索引 | {} | {}',
                    idx, total, file_id, aliyun_id,
                )
                parsed.append((file_id, aliyun_id))
                tick()
                continue
            if status in FILE_FAILED_STATUSES:
                # 显式失败终态 (快照判定): 删除云端文件后降级重传
                logger.warning(
                    '续接发现失败态, 删除后重传 | {} | {} | 状态={}',
                    file_id, aliyun_id, status,
                )
                await self._delete_file_quiet(aliyun_id)
                fresh.append(record)
            else:  # 未知状态: 保守保留文件, 记入失败清单待下轮重试
                logger.error(
                    '续接发现未知状态, 保留文件待下轮重试 '
                    '| {} | {} | 状态={}',
                    file_id, aliyun_id, status,
                )
                report.failed_adds.append(
                    (file_id, f'未知状态 {status}'),
                )
            tick()
        if total:
            logger.info(
                '续接阶段完成 | 续接成功 {} / {} 篇 | 转重传 {} 篇',
                len(parsed), total, len(fresh) - requeue_start,
            )
        return parsed

    async def _upload_all(
        self,
        fresh: list[dict[str, Any]],
        report: AliyunAlignReport,
        on_item_done: Callable[[], None] | None = None,
    ) -> list[tuple[str, str]]:
        """并行上传新文件并等待解析, 返回解析成功清单.

        上传阶段以 UPLOAD_CONCURRENCY 为上限并行执行
        「下载→上传→等待解析」, 入索引由调用方统一批量提交.

        Args:
            fresh: 待全新上传的有效文件清单条目.
            report: 执行结果报告, 原地更新.
            on_item_done: 可选单篇完成钩子, 成功/失败/返回空均计一次.

        Returns:
            (本地fileId, 阿里云FileId) 解析成功列表.
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
                result = await self._upload_and_parse(
                    record, idx, total, report,
                )
            if on_item_done is not None:
                on_item_done()
            return result

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

        上传时写入云端哈希锚点标签, 任一步失败记入报告, 不中断其他文
        文档. 中断幂等性由下轮快照的标签匹配保证, 本地不落盘任
        何映射.

        Args:
            record: 有效文件清单条目.
            index: 当前进度序号 (从 1 开始).
            total: 待补充总数.
            report: 执行结果报告, 原地更新.

        Returns:
            (本地fileId, 阿里云FileId); 失败时返回 None.
        """
        file_id = record['fileId']
        logger.info(
            '补充文档 [{}/{}] 开始下载上传 | {}', index, total, file_id,
        )
        try:
            content = await self._download_pdf(record['filePath'])
            tags = build_file_tags(record, self._source)
            logger.debug(
                '上传打标 | {} | 锚点={}',
                file_id, extract_fileid(tags),
            )
            aliyun_id = await self._client.upload_file(
                file_name=build_file_name(record),
                content=content,
                tags=tags,
                original_file_url=record['filePath'],
            )
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

        入索引失败篇记入报告; 因云端文件与标签仍在, 下次对齐经
        快照标签匹配走续接重试入索引而不会重传.

        Args:
            parsed: (本地fileId, 阿里云FileId) 列表.
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
        """删除一篇索引孤儿文档: 移出索引并删除数据中心文件.

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
            report.deleted.append(aliyun_id)
            logger.info(
                '删除孤儿文档成功 [{}/{}] | {} | {}',
                index, total, aliyun_id, doc.name,
            )
        except Exception as exc:  # 单篇失败不中断整体对齐
            logger.error(
                '删除孤儿文档失败 [{}/{}] | {} | {}',
                index, total, aliyun_id, exc,
            )
            report.failed_deletes.append((aliyun_id, str(exc)))

    async def _remove_residual_file(
        self,
        item: DataCenterFileItem,
        report: AliyunAlignReport,
        index: int,
        total: int,
    ) -> None:
        """删除一个数据中心残留文件 (不在索引内, 仅删文件).

        Args:
            item: 待删除的残留文件快照.
            report: 执行结果报告, 原地更新.
            index: 当前进度序号 (从 1 开始).
            total: 待清理残留总数.
        """
        try:
            await self._client.delete_files(
                bailian_models.DeleteFilesRequest(file_ids=[item.file_id])
            )
            report.deleted.append(item.file_id)
            logger.info(
                '删除残留文件成功 [{}/{}] | {} | {}',
                index, total, item.file_id, item.file_name,
            )
        except Exception as exc:  # 单个失败不中断整体对齐
            logger.error(
                '删除残留文件失败 [{}/{}] | {} | {}',
                index, total, item.file_id, exc,
            )
            report.failed_deletes.append((item.file_id, str(exc)))

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
        """清空知识库: 删除索引全部文档及本应用管理的数据中心文件.

        数据中心删除集合仅含有本应用标签 (fileid_ 锚点或交易所裸来
        源标签) 的文件; 无本应用标签的外部文件 (如控制台手工上传)
        一律排除保留, 只统计数量并告警, 避免误删非本应用管理的文件.
        新体系下本应用文件均带标签, 「清库重建」场景不受影响.
        阿里云切片随索引文档删除而删除, 且不支持无文件过滤的
        全量切片列举, 因此不单独处理孤儿切片.

        Args:
            dry_run: 为 True 时只盘点数量不执行删除.

        Returns:
            清库执行结果报告.
        """
        report = AliyunPurgeReport(dry_run=dry_run)
        index_docs, data_files = await asyncio.gather(
            self.list_all_index_documents(),
            self._client.list_all_data_center_files(),
        )
        report.total_docs = len(index_docs)
        report.total_data_files = len(data_files)
        logger.info(
            '清库盘点 | 索引文档 {} 篇 | 数据中心文件 {} 个',
            report.total_docs, report.total_data_files,
        )

        # 数据中心文件按标签区分: 有本应用标签者纳入删除集合, 无标
        # 签的外部文件排除保留, 收敛破坏半径.
        managed_ids = {
            item.file_id
            for item in data_files
            if item.file_id and has_app_tags(item.tags)
        }
        external = [
            item for item in data_files if not has_app_tags(item.tags)
        ]
        report.excluded_external_files = len(external)
        if external:
            logger.warning(
                '清除范围内包含外部文件（无本应用标签）{} 个, '
                '已排除保留不删除 | {}',
                len(external),
                ', '.join(
                    f'{item.file_id}({item.file_name})'
                    for item in external[:10]
                ),
            )
        if dry_run:
            return report

        index_ids = [doc.id for doc in index_docs if doc.id]
        report.deleted_docs = await self._purge_index(index_ids, report)

        # 数据中心删除集合 = 索引内文件 并 有本应用标签的文件 (外部文件已排除)
        file_ids = set(index_ids) | managed_ids
        deleted_file_ids = await self._purge_data_files(
            sorted(file_ids), report,
        )
        report.deleted_files = len(deleted_file_ids)

        logger.info(
            '清库完成 | 索引删除 {} 篇 | 数据中心删除 {} 个 | '
            '排除外部文件 {} 个 | 失败 {} 项',
            report.deleted_docs, report.deleted_files,
            report.excluded_external_files, len(report.failed),
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
