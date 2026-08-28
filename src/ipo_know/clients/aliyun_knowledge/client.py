"""阿里云百炼知识库异步客户端.

对官方 alibabacloud-bailian20231229 SDK 做薄封装, 对外暴露 async
接口, 内部通过 asyncio.to_thread 将同步 SDK 调用投递到线程池,
避免阻塞事件循环.

覆盖数据中心文件管理 (租约上传/解析轮询)、知识库文档管理
(入索引任务/列举/删除) 等对齐流程所需接口.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass

import requests
from alibabacloud_bailian20231229 import models as bailian_models
from alibabacloud_bailian20231229.client import Client as BailianClient
from alibabacloud_bssopenapi20171214 import models as bss_models
from alibabacloud_bssopenapi20171214.client import Client as BssClient
from alibabacloud_tea_openapi import models as open_api_models
from loguru import logger

from ipo_know.clients.monitor_dto import BalanceInfo
from ipo_know.clients.monitor_dto import BillDetailItem
from ipo_know.config.config import AliyunKnowledgeSettings
from ipo_know.config.config import settings


# 轮询间隔: 文件解析与入索引任务均为异步, 需周期性查询状态.
POLL_INTERVAL_SECONDS = 5

# 单文件解析等待上限: 招股书 PDF 体积大, 解析可能耗时较长.
PARSE_POLL_TIMEOUT_SECONDS = 600

# 文件处理失败终态集合: 命中任一即终止等待并报错.
# 注意 IN_PARSE_QUEUE 为排队中间态, 不属于失败.
FILE_FAILED_STATUSES = frozenset({
    'PARSE_FAILED',
    'SAFE_CHECK_FAILED',
    'INDEX_BUILDING_FAILED',
    'FILE_EXPIRED',
})

# 入索引任务等待上限: 任务包含解析结果入库与向量化.
JOB_POLL_TIMEOUT_SECONDS = 1800

# 百炼 API 全局限流: 官方限流说明为 10 次/秒, 预留余量取 8.
API_RATE_LIMIT_PER_SECOND = 8

# ListFile 单页条数上限, 取接口允许的最大值减少分页次数.
LIST_FILE_PAGE_SIZE = 200

# 类目配置占位符: 需经 ListCategory 解析出默认类目真实 ID.
DEFAULT_CATEGORY_PLACEHOLDER = 'default'

# 非结构化数据中心的默认类目名称.
DEFAULT_CATEGORY_NAME = '默认类目'


@dataclass
class DataCenterFileItem:
    """数据中心文件轻量结构, 与 SDK 响应类型解耦.

    Attributes:
        file_id: 百炼数据中心文件 ID.
        status: 文件处理状态.
        tags: 文件标签列表.
        file_name: 文件名.
    """

    file_id: str
    status: str
    tags: list[str]
    file_name: str


class _ApiRateLimiter:
    """百炼 API 全局限流器.

    以固定间隔串行放行调用, 将全部 API 请求的总频率限制在
    每秒 rate_per_second 次以内, 避免触发官方限流.

    Attributes:
        _interval: 相邻两次调用的最小间隔, 单位秒.
        _lock: 异步锁, 保证放行串行计算.
        _next_time: 下一次允许调用的时间点 (事件循环时钟).
    """

    def __init__(self, rate_per_second: float) -> None:
        """初始化限流器.

        Args:
            rate_per_second: 每秒允许的最大调用次数.
        """
        self._interval = 1.0 / rate_per_second
        self._lock = asyncio.Lock()
        self._next_time = 0.0

    async def acquire(self) -> None:
        """等待直至获得一个调用放行时隙."""
        async with self._lock:
            now = asyncio.get_running_loop().time()
            if now < self._next_time:
                await asyncio.sleep(self._next_time - now)
                now = asyncio.get_running_loop().time()
            self._next_time = now + self._interval


class AliyunKnowledgeClient:
    """阿里云百炼知识库异步客户端.

    薄封装官方 SDK 的同步接口, 对外提供 async 方法. 底层
    BailianClient 在首次调用时懒加载, 鉴权采用 AK/SK.

    Attributes:
        _config: 百炼知识库配置.
        _client: 底层 BailianClient 同步客户端 (懒加载).
        _resolved_category_id: ListFile 用真实类目 ID 缓存,
            仅首次解析一次.
    """

    def __init__(
        self,
        config: AliyunKnowledgeSettings | None = None,
    ) -> None:
        """初始化百炼知识库客户端.

        Args:
            config: 百炼知识库配置, 为 None 时使用全局
                settings.aliyun_knowledge.
        """
        self._config = config or settings.aliyun_knowledge
        self._client: BailianClient | None = None
        self._bss_client: BssClient | None = None
        self._resolved_category_id: str | None = None
        self._rate_limiter = _ApiRateLimiter(API_RATE_LIMIT_PER_SECOND)
        logger.info(
            '百炼知识库客户端初始化 | endpoint={} | workspace={}',
            self._config.endpoint,
            self._config.workspace_id or '(未配置)',
        )

    # ==================================================
    # 底层客户端懒加载
    # ==================================================
    def _get_client(self) -> BailianClient:
        """懒加载底层 BailianClient 同步客户端."""
        if self._client is None:
            if not self._config.ak or not self._config.sk:
                raise ValueError(
                    '百炼知识库 AK/SK 未配置，请通过 GUI 配置填写'
                )
            open_api_config = open_api_models.Config(
                access_key_id=self._config.ak,
                access_key_secret=self._config.sk,
                endpoint=self._config.endpoint,
                region_id=self._config.region_id,
            )
            self._client = BailianClient(open_api_config)
        return self._client

    @property
    def _get_bss_client(self) -> BssClient:
        """懒加载 BSS 费用中心客户端."""
        if self._bss_client is None:
            if not self._config.ak or not self._config.sk:
                raise ValueError(
                    '百炼知识库 AK/SK 未配置，请通过 GUI 配置填写'
                )
            bss_config = open_api_models.Config(
                access_key_id=self._config.ak,
                access_key_secret=self._config.sk,
                endpoint='business.aliyuncs.com',
            )
            self._bss_client = BssClient(bss_config)
        return self._bss_client

    @property
    def workspace_id(self) -> str:
        """业务空间 ID, 未配置时抛出异常提示."""
        if not self._config.workspace_id:
            raise ValueError(
                '百炼业务空间未配置，请通过 GUI 配置填写'
            )
        return self._config.workspace_id

    @property
    def index_id(self) -> str:
        """知识库 ID, 未配置时抛出异常提示."""
        if not self._config.index_id:
            raise ValueError(
                '百炼知识库 ID 未配置，请通过 GUI 配置填写'
            )
        return self._config.index_id

    @property
    def category_id(self) -> str:
        """数据中心类目 ID, 配置总有默认值."""
        return self._config.category_id

    @property
    def region_id(self) -> str:
        """服务地域, 问答链路拼接 Host 使用, 总有默认值."""
        return self._config.region_id

    # ==================================================
    # 异步桥接
    # ==================================================
    async def _run_in_thread(
        self,
        func: Callable[..., object],
        *args: object,
        **kwargs: object,
    ) -> object:
        """在线程池中执行同步调用, 避免阻塞事件循环."""
        return await asyncio.to_thread(func, *args, **kwargs)

    async def _api_call(
        self,
        func: Callable[..., object],
        *args: object,
        **kwargs: object,
    ) -> object:
        """经全局限流后执行一次百炼 API 调用."""
        await self._rate_limiter.acquire()
        return await self._run_in_thread(func, *args, **kwargs)

    # ==================================================
    # 薄封装: 数据中心文件管理
    # ==================================================
    async def apply_file_upload_lease(
        self,
        request: bailian_models.ApplyFileUploadLeaseRequest,
    ) -> bailian_models.ApplyFileUploadLeaseResponse:
        """申请文件上传租约.

        Args:
            request: 租约申请请求, 含文件名/MD5/大小.

        Returns:
            租约响应, data 内含 FileUploadLeaseId 与预签名参数.
        """
        return await self._api_call(
            self._get_client().apply_file_upload_lease,
            self._config.category_id,
            self.workspace_id,
            request,
        )

    async def add_file(
        self,
        request: bailian_models.AddFileRequest,
    ) -> bailian_models.AddFileResponse:
        """向数据中心添加已上传文件.

        Args:
            request: 添加文件请求, 含租约 ID/解析器/分类/标签.

        Returns:
            添加文件响应, data 内含 FileId.
        """
        return await self._api_call(
            self._get_client().add_file,
            self.workspace_id,
            request,
        )

    async def describe_file(
        self,
        file_id: str,
    ) -> bailian_models.DescribeFileResponse:
        """查询数据中心文件详情 (含解析状态与标签).

        Args:
            file_id: 数据中心文件 ID.

        Returns:
            文件详情响应.
        """
        return await self._api_call(
            self._get_client().describe_file,
            self.workspace_id,
            file_id,
            bailian_models.DescribeFileRequest(),
        )

    async def list_file(
        self,
        request: bailian_models.ListFileRequest,
    ) -> bailian_models.ListFileResponse:
        """分页列出数据中心文件 (含标签).

        Args:
            request: 文件列表请求, 含分类 ID 与分页 token.

        Returns:
            文件列表响应.
        """
        return await self._api_call(
            self._get_client().list_file,
            self.workspace_id,
            request,
        )

    async def _resolve_list_category_id(self) -> str:
        """解析 ListFile 使用的真实类目 ID.

        ListFile 的 category_id 必须为真实类目 ID, 配置中的占位符
        'default' 需经 ListCategory 查询默认类目解析; 解析结果缓存,
        仅首次请求生效.

        Returns:
            可直接用于 ListFile 的类目 ID.

        Raises:
            RuntimeError: 业务空间下未找到任何非结构化类目.
        """
        if self._resolved_category_id:
            return self._resolved_category_id
        configured = self._config.category_id
        if configured and configured != DEFAULT_CATEGORY_PLACEHOLDER:
            self._resolved_category_id = configured
            return configured

        resp = await self._api_call(
            self._get_client().list_category,
            self.workspace_id,
            bailian_models.ListCategoryRequest(
                category_type='UNSTRUCTURED',
            ),
        )
        data = resp.body.data
        cats = data.category_list if data else None
        if cats:
            for cat in cats:
                if cat.category_name == DEFAULT_CATEGORY_NAME:
                    self._resolved_category_id = cat.category_id
                    logger.info(
                        '默认类目真实 ID 解析完成 | category_id={}',
                        cat.category_id,
                    )
                    return cat.category_id
            self._resolved_category_id = cats[0].category_id
            logger.info(
                '未找到默认类目, 退回首类目 | category_id={}',
                cats[0].category_id,
            )
            return cats[0].category_id
        raise RuntimeError('未找到任何非结构化类目')

    async def list_all_data_center_files(
        self,
    ) -> list[DataCenterFileItem]:
        """游标分页拉取数据中心全部文件.

        以 LIST_FILE_PAGE_SIZE 为单页上限按 next_token 翻页, 直到无后续页;
        分页中途的接口异常不吸收, 直接向上抛出由调用方 fail-fast.

        Returns:
            全部文件的轻量结构列表, 每条含 file_id / status /
            tags / file_name.
        """
        category_id = await self._resolve_list_category_id()
        files: list[DataCenterFileItem] = []
        next_token: str | None = None
        page = 0
        while True:
            page += 1
            request = bailian_models.ListFileRequest(
                category_id=category_id,
                max_results=LIST_FILE_PAGE_SIZE,
            )
            if next_token:
                request.next_token = next_token
            resp = await self.list_file(request)
            data = resp.body.data
            if data and data.file_list:
                for item in data.file_list:
                    files.append(
                        DataCenterFileItem(
                            file_id=item.file_id or '',
                            status=item.status or '',
                            tags=list(item.tags) if item.tags else [],
                            file_name=item.file_name or '',
                        ),
                    )
            logger.debug(
                '数据中心文件分页列举 | 页={} | 累计={} 个',
                page, len(files),
            )
            if data and data.has_next:
                if not data.next_token:
                    # has_next 但缺游标: 继续翻页不可能, 静默终止会产
                    # 生半量快照, 与 fail-fast 语义不符, 直接报错中止.
                    raise RuntimeError(
                        'ListFile 返回 has_next 但缺少 next_token, '
                        '中止以防半量快照',
                    )
                next_token = data.next_token
            else:
                break
        logger.info(
            '数据中心文件列举完成 | 共 {} 个', len(files),
        )
        return files

    async def delete_files(
        self,
        request: bailian_models.DeleteFilesRequest,
    ) -> bailian_models.DeleteFilesResponse:
        """批量删除数据中心文件.

        Args:
            request: 删除请求, 含文件 ID 列表.

        Returns:
            删除响应.
        """
        return await self._api_call(
            self._get_client().delete_files,
            self.workspace_id,
            request,
        )

    # ==================================================
    # 薄封装: 知识库文档管理
    # ==================================================
    async def list_index_documents(
        self,
        request: bailian_models.ListIndexDocumentsRequest,
    ) -> bailian_models.ListIndexDocumentsResponse:
        """分页列出知识库内文档.

        Args:
            request: 文档列表请求, 含知识库 ID 与页码参数.

        Returns:
            文档列表响应.
        """
        return await self._api_call(
            self._get_client().list_index_documents,
            self.workspace_id,
            request,
        )

    async def check_connection(self) -> None:
        """发起轻量只读调用以验证配置与网络连通性.

        使用列举知识库文档接口 (第 1 页, 每页 1 条),
        一次调用即可覆盖 AK/SK 鉴权、Endpoint 可达性、
        Workspace ID 与 Index ID 有效性的验证.

        Raises:
            ValueError: AK/SK、Workspace ID 或 Index ID 未配置.
            Exception: 底层 SDK 返回的任何 API 错误.
        """
        request = bailian_models.ListIndexDocumentsRequest(
            index_id=self.index_id,
            page_number=1,
            page_size=1,
        )
        await self.list_index_documents(request)

    async def delete_index_document(
        self,
        request: bailian_models.DeleteIndexDocumentRequest,
    ) -> bailian_models.DeleteIndexDocumentResponse:
        """从知识库中批量删除文档 (连带其切片).

        Args:
            request: 删除请求, 含知识库 ID 与文档 ID 列表.

        Returns:
            删除响应.
        """
        return await self._api_call(
            self._get_client().delete_index_document,
            self.workspace_id,
            request,
        )

    async def submit_index_add_documents_job(
        self,
        request: bailian_models.SubmitIndexAddDocumentsJobRequest,
    ) -> bailian_models.SubmitIndexAddDocumentsJobResponse:
        """提交文档入索引异步任务.

        Args:
            request: 入索引请求, 含知识库 ID 与文件 ID 列表.

        Returns:
            提交响应, data 内含任务 JobId.
        """
        return await self._api_call(
            self._get_client().submit_index_add_documents_job,
            self.workspace_id,
            request,
        )

    async def get_index_job_status(
        self,
        request: bailian_models.GetIndexJobStatusRequest,
    ) -> bailian_models.GetIndexJobStatusResponse:
        """查询入索引任务状态.

        Args:
            request: 状态查询请求, 含知识库 ID 与 JobId.

        Returns:
            任务状态响应.
        """
        return await self._api_call(
            self._get_client().get_index_job_status,
            self.workspace_id,
            request,
        )

    # ==================================================
    # 薄封装: 知识库检索
    # ==================================================
    async def retrieve(
        self,
        request: bailian_models.RetrieveRequest,
    ) -> bailian_models.RetrieveResponse:
        """在知识库中检索与查询相关的文本切片.

        Args:
            request: 检索请求, 含知识库 ID 与查询文本.

        Returns:
            检索响应, body.data.nodes 为命中的文本切片列表.
        """
        logger.debug(
            '百炼 Retrieve 调用 | workspace_id={} | index_id={}',
            self.workspace_id, request.index_id,
        )
        response = await self._api_call(
            self._get_client().retrieve,
            self.workspace_id,
            request,
        )
        logger.debug(
            '百炼 Retrieve 响应 | nodes={}',
            len(
                (response.body.data.nodes or [])
                if response.body and response.body.data
                else []
            ),
        )
        return response

    # ==================================================
    # 组合能力: 上传 → 解析 → 入索引
    # ==================================================
    async def upload_file(
        self,
        *,
        file_name: str,
        content: bytes,
        tags: list[str] | None = None,
        original_file_url: str | None = None,
    ) -> str:
        """上传文件到数据中心: 租约 + 预签名 PUT + AddFile.

        Args:
            file_name: 文件名, 必须含扩展名, 4~128 字符.
            content: 文件字节内容.
            tags: 文件标签列表, 最多 100 个且总长不超过 700.
            original_file_url: 源文件 URL, 记录后随检索结果返回.

        Returns:
            数据中心文件 ID (FileId).
        """
        md5 = hashlib.md5(content).hexdigest()
        lease_resp = await self.apply_file_upload_lease(
            bailian_models.ApplyFileUploadLeaseRequest(
                category_type='UNSTRUCTURED',
                file_name=file_name,
                md_5=md5,
                size_in_bytes=str(len(content)),
            )
        )
        lease_data = lease_resp.body.data
        if not lease_data or not lease_data.file_upload_lease_id:
            raise RuntimeError(
                f'申请上传租约失败: {lease_resp.body.message}'
            )

        await self._put_presigned(lease_data.param, content)

        add_resp = await self.add_file(
            bailian_models.AddFileRequest(
                category_id=self._config.category_id,
                lease_id=lease_data.file_upload_lease_id,
                parser=self._config.parser,
                tags=tags,
                original_file_url=original_file_url,
            )
        )
        if not add_resp.body.data or not add_resp.body.data.file_id:
            raise RuntimeError(f'添加文件失败: {add_resp.body.message}')
        file_id = add_resp.body.data.file_id
        return file_id

    async def _put_presigned(
        self,
        param: bailian_models.ApplyFileUploadLeaseResponseBodyDataParam,
        content: bytes,
    ) -> None:
        """按租约返回的预签名参数 PUT 上传文件字节.

        Args:
            param: 租约响应中的预签名参数 (method/url/headers).
            content: 文件字节内容.
        """
        if param is None or not param.url:
            raise RuntimeError('上传租约缺少预签名参数')
        headers = param.headers
        if isinstance(headers, str):
            headers = json.loads(headers)
        response = await self._run_in_thread(
            requests.put,
            param.url,
            data=content,
            headers=headers,
            timeout=self._config.timeout * 10,
        )
        if response.status_code >= 300:
            raise RuntimeError(
                f'预签名上传失败: HTTP {response.status_code} '
                f'{response.text[:200]}'
            )

    async def wait_file_parsed(self, file_id: str) -> None:
        """轮询等待文件解析完成.

        Args:
            file_id: 数据中心文件 ID.

        Raises:
            RuntimeError: 解析失败或等待超时.
        """
        elapsed = 0
        while elapsed < PARSE_POLL_TIMEOUT_SECONDS:
            resp = await self.describe_file(file_id)
            data = resp.body.data
            status = data.status if data else None
            if status == 'PARSE_SUCCESS':
                return
            if status == 'PARSE_FAILED':
                reason = data.parse_error_message if data else '未知'
                raise RuntimeError(f'文件解析失败: {reason}')
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS
        raise RuntimeError(
            f'等待文件解析超时 ({PARSE_POLL_TIMEOUT_SECONDS}s) | '
            f'FileId={file_id}'
        )

    async def add_documents_to_index(
        self,
        document_ids: list[str],
    ) -> list[str]:
        """提交文件入索引任务并轮询至完成.

        切片参数取配置项 ``chunk_mode`` / ``chunk_size``: ``chunk_mode``
        为空串时转 None 不下发, 由平台智能切分; ``chunk_size``
        始终下发 (控制切片字符数上限). 整批任务失败时抛出
        异常; 任务完成但个别文档失败时通过返回值告知.

        Args:
            document_ids: 数据中心文件 ID 列表.

        Returns:
            入索引失败的文档 FileId 列表, 空列表表示全部成功.

        Raises:
            RuntimeError: 任务提交失败、执行失败或等待超时.
        """
        chunk_mode = self._config.chunk_mode or None
        chunk_size = self._config.chunk_size
        logger.info(
            '提交入索引任务 | file_count={} | chunk_mode={} '
            '| chunk_size={}',
            len(document_ids), chunk_mode or '智能切分',
            chunk_size,
        )
        submit_resp = await self.submit_index_add_documents_job(
            bailian_models.SubmitIndexAddDocumentsJobRequest(
                index_id=self.index_id,
                document_ids=document_ids,
                source_type='DATA_CENTER_FILE',
                chunk_mode=chunk_mode,
                chunk_size=chunk_size,
            )
        )
        if not submit_resp.body.data or not submit_resp.body.data.id:
            raise RuntimeError(
                f'提交入索引任务失败: {submit_resp.body.message}'
            )
        job_id = submit_resp.body.data.id

        elapsed = 0
        while elapsed < JOB_POLL_TIMEOUT_SECONDS:
            resp = await self.get_index_job_status(
                bailian_models.GetIndexJobStatusRequest(
                    index_id=self.index_id,
                    job_id=job_id,
                )
            )
            data = resp.body.data
            status = (data.status or '').upper() if data else ''
            if status == 'COMPLETED':
                return self._collect_failed_documents(job_id, data)
            if status in {'FAILED', 'ERROR'}:
                raise RuntimeError(f'入索引任务失败 | JobId={job_id}')
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS
        raise RuntimeError(
            f'等待入索引任务超时 ({JOB_POLL_TIMEOUT_SECONDS}s) | '
            f'JobId={job_id}'
        )

    # ==================================================
    # 薄封装: 监控与账户
    # ==================================================
    async def get_index_doc_count(self) -> int:
        """获取知识库内文档总数.

        通过 list_index_documents 接口取第 1 页
        仅 1 条记录, 利用响应中的 total_count 字段
        获得文档总数, 避免拉取全量文档列表.

        Returns:
            知识库内文档总数.
        """
        logger.debug(
            '百炼 get_index_doc_count 调用 '
            '| index_id={}',
            self.index_id,
        )
        request = bailian_models.ListIndexDocumentsRequest(
            index_id=self.index_id,
            page_number=1,
            page_size=1,
        )
        response = await self.list_index_documents(request)
        data = (
            response.body.data
            if response.body else None
        )
        count = (
            data.total_count if data else 0
        ) or 0
        logger.debug(
            '百炼 get_index_doc_count 响应 '
            '| total_count={}',
            count,
        )
        return count

    async def get_index_monitor(
        self,
        start_timestamp: int,
        end_timestamp: int,
    ) -> dict:
        """获取知识库监控数据 (存储 + QPS).

        Args:
            start_timestamp: 查询起始时间 (秒级 Unix 时间戳).
            end_timestamp: 查询结束时间 (秒级 Unix 时间戳).

        Returns:
            解析后的监控数据 dict, 含存储与 QPS 监控信息.
        """
        logger.debug(
            '百炼 IndexMonitor 调用 | index_id={} | '
            'start={} | end={}',
            self.index_id, start_timestamp, end_timestamp,
        )
        request = bailian_models.GetIndexMonitorRequest(
            index_id=self.index_id,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )
        response = await self._api_call(
            self._get_client().get_index_monitor,
            self.workspace_id,
            request,
        )
        data = response.body.data
        if isinstance(data, str):
            data = json.loads(data)
        # 剥离外层信封，提取实际监控数据
        if isinstance(data, dict) and 'data' in data:
            data = data['data']
        logger.debug(
            '百炼 IndexMonitor 响应 | type={}',
            type(data).__name__,
        )
        return data

    async def query_account_balance(self) -> BalanceInfo:
        """查询阿里云账户余额.

        Returns:
            BalanceInfo DTO, platform='aliyun'.
        """
        logger.debug('百炼 账户余额 调用')
        response = await self._api_call(
            self._get_bss_client.query_account_balance,
        )
        d = response.body.data
        info = BalanceInfo(
            platform='aliyun',
            available_amount=d.available_amount or '',
            cash_amount=d.available_cash_amount or '',
            credit_amount=d.credit_amount or '',
            currency=d.currency or 'CNY',
        )
        logger.debug(
            '百炼 账户余额 响应 | available={} | currency={}',
            info.available_amount, info.currency,
        )
        return info

    async def query_account_transaction_details(
        self,
        create_time_start: str,
        create_time_end: str,
    ) -> list[BillDetailItem]:
        """查询阿里云收支明细 (自动翻页).

        循环调用直至 next_token 为空, 聚合全部
        BillDetailItem 后返回.

        Args:
            create_time_start: 创建时间起始 (如 '2026-01-01').
            create_time_end: 创建时间终止 (如 '2026-01-31').

        Returns:
            全部翻页的 BillDetailItem 列表.
        """
        all_items: list[BillDetailItem] = []
        next_token: str | None = None
        while True:
            logger.debug(
                '百炼 收支明细 调用 | start={} |'
                ' end={} | token={}',
                create_time_start,
                create_time_end,
                next_token,
            )
            request = (
                bss_models
                .QueryAccountTransactionDetailsRequest(
                    create_time_start=create_time_start,
                    create_time_end=create_time_end,
                    next_token=next_token,
                )
            )
            response = await self._api_call(
                self._get_bss_client
                .query_account_transaction_details,
                request,
            )
            data = response.body.data
            tx_list = (
                data.account_transactions_list
                .account_transactions_list
                if data and data.account_transactions_list
                else []
            )
            items = [
                BillDetailItem(
                    record_id=(
                        getattr(tx, 'record_id', '') or ''
                    ),
                    date=(
                        getattr(
                            tx, 'transaction_time', '',
                        ) or ''
                    ),
                    product=(
                        getattr(
                            tx,
                            'transaction_type',
                            '',
                        ) or ''
                    ),
                    amount=(
                        getattr(tx, 'amount', '') or ''
                    ),
                    payment_method=(
                        getattr(
                            tx,
                            'transaction_channel',
                            '',
                        ) or ''
                    ),
                    remark=(
                        getattr(tx, 'remarks', '') or ''
                    ),
                )
                for tx in (tx_list or [])
            ]
            all_items.extend(items)
            next_token = (
                getattr(data, 'next_token', None)
                if data else None
            )
            logger.debug(
                '百炼 收支明细 翻页 | count={} |'
                ' total={} | next_token={}',
                len(items),
                getattr(data, 'total_count', 0),
                next_token,
            )
            if not next_token:
                break
        logger.debug(
            '百炼 收支明细 完成 | total_items={}',
            len(all_items),
        )
        return all_items

    @staticmethod
    def _collect_failed_documents(
        job_id: str,
        data: bailian_models.GetIndexJobStatusResponseBodyData,
    ) -> list[str]:
        """收集任务内入索引失败的文档 ID 并逐条告警.

        Args:
            job_id: 入索引任务 ID.
            data: 任务状态响应数据.

        Returns:
            入索引失败的文档 FileId 列表.
        """
        documents = list(data.documents) if data.documents else []
        failed_ids: list[str] = []
        for doc in documents:
            if doc.status and doc.status.upper() not in {'FINISH', 'SUCCESS'}:
                if doc.doc_id:
                    failed_ids.append(doc.doc_id)
                logger.warning(
                    '入索引文档失败 | JobId={} | {} | {}',
                    job_id, doc.doc_name or doc.doc_id,
                    doc.message or doc.status,
                )
        return failed_ids
