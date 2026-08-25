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

import requests
from alibabacloud_bailian20231229 import models as bailian_models
from alibabacloud_bailian20231229.client import Client as BailianClient
from alibabacloud_tea_openapi import models as open_api_models
from loguru import logger

from ipo_know.config.config import AliyunKnowledgeSettings
from ipo_know.config.config import settings


# 轮询间隔: 文件解析与入索引任务均为异步, 需周期性查询状态.
POLL_INTERVAL_SECONDS = 5

# 单文件解析等待上限: 招股书 PDF 体积大, 解析可能耗时较长.
PARSE_POLL_TIMEOUT_SECONDS = 600

# 入索引任务等待上限: 任务包含解析结果入库与向量化.
JOB_POLL_TIMEOUT_SECONDS = 1800

# 百炼 API 全局限流: 官方限流说明为 10 次/秒, 预留余量取 8.
API_RATE_LIMIT_PER_SECOND = 8


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
        return await self._api_call(
            self._get_client().retrieve,
            self.workspace_id,
            request,
        )

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

        不传切片参数, 使用平台智能切片. 整批任务失败时抛出
        异常; 任务完成但个别文档失败时通过返回值告知.

        Args:
            document_ids: 数据中心文件 ID 列表.

        Returns:
            入索引失败的文档 FileId 列表, 空列表表示全部成功.

        Raises:
            RuntimeError: 任务提交失败、执行失败或等待超时.
        """
        submit_resp = await self.submit_index_add_documents_job(
            bailian_models.SubmitIndexAddDocumentsJobRequest(
                index_id=self.index_id,
                document_ids=document_ids,
                source_type='DATA_CENTER_FILE',
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
