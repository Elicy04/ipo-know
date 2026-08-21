"""火山引擎 VikingDB 知识库异步客户端.

对官方 vikingdb-python-sdk 的高层知识库接口做薄封装, 对外暴露
async 接口, 内部通过 asyncio.to_thread 将同步 SDK 调用投递到线程池,
避免阻塞事件循环.

覆盖文档管理、切片 (Chunk) 管理、知识库检索与对话补全等接口.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping

from loguru import logger
from vikingdb import IAM
from vikingdb import KnowledgeCollection
from vikingdb import VikingKnowledge
from vikingdb.knowledge import AddDocV2Request
from vikingdb.knowledge import AddDocV2Response
from vikingdb.knowledge import AddPointRequest
from vikingdb.knowledge import ChatCompletionRequest
from vikingdb.knowledge import ChatCompletionResponse
from vikingdb.knowledge import DeletePointRequest
from vikingdb.knowledge import DocInfo
from vikingdb.knowledge import ListDocsRequest
from vikingdb.knowledge import ListDocsResponse
from vikingdb.knowledge import ListPointsRequest
from vikingdb.knowledge import ListPointsResponse
from vikingdb.knowledge import MetaItem
from vikingdb.knowledge import PointInfo
from vikingdb.knowledge import SearchKnowledgeRequest
from vikingdb.knowledge import SearchKnowledgeResponse
from vikingdb.knowledge import ServiceChatRequest
from vikingdb.knowledge import ServiceChatResponse
from vikingdb.knowledge import UpdatePointRequest
from vikingdb.knowledge.models.base import CommonResponse
from vikingdb.knowledge.models.point import PointAddResponse

from ipo_know.config.config import VikingKnowledgeSettings
from ipo_know.config.config import settings


class VikingKnowledgeClient:
    """火山引擎 VikingDB 知识库异步客户端.

    薄封装官方 SDK 的同步接口, 对外提供 async 方法. 底层 SDK
    (VikingKnowledge / KnowledgeCollection) 在首次调用时懒加载,
    鉴权采用 AK/SK (IAM).

    Attributes:
        _config: 知识库配置.
        _client: 底层 VikingKnowledge 同步客户端 (懒加载).
        _collection: 底层 KnowledgeCollection 同步集合 (懒加载).
    """

    def __init__(
        self,
        config: VikingKnowledgeSettings | None = None,
    ) -> None:
        """初始化火山知识库客户端.

        Args:
            config: 知识库配置, 为 None 时使用全局
                settings.viking_knowledge.
        """
        self._config = config or settings.viking_knowledge
        self._client: VikingKnowledge | None = None
        self._collection: KnowledgeCollection | None = None
        logger.info(
            '火山知识库客户端初始化 | host={} | region={} | scheme={}',
            self._config.host,
            self._config.region,
            self._config.scheme,
        )

    # ==================================================
    # 底层客户端懒加载
    # ==================================================
    def _get_client(self) -> VikingKnowledge:
        """懒加载底层 VikingKnowledge 同步客户端."""
        if self._client is None:
            if not self._config.ak or not self._config.sk:
                raise ValueError(
                    '火山知识库 AK/SK 未配置, 请在 .env 中设置 '
                    'IPO_KNOW_VIKING_KNOWLEDGE__AK 与 '
                    'IPO_KNOW_VIKING_KNOWLEDGE__SK'
                )
            auth = IAM(ak=self._config.ak, sk=self._config.sk)
            self._client = VikingKnowledge(
                host=self._config.host,
                region=self._config.region,
                auth=auth,
                scheme=self._config.scheme,
                timeout=self._config.timeout,
            )
        return self._client

    def _get_collection(self) -> KnowledgeCollection:
        """懒加载底层 KnowledgeCollection 同步集合."""
        if self._collection is None:
            self._collection = self._get_client().collection(
                resource_id=self._config.resource_id or None,
                collection_name=self._config.collection_name or None,
                project_name=self._config.project_name or None,
            )
        return self._collection

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

    async def _stream_in_thread(
        self,
        func: Callable[..., Iterable[object]],
        *args: object,
        **kwargs: object,
    ) -> AsyncIterator[object]:
        """把同步生成器桥接为异步迭代器."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _producer() -> None:
            try:
                for item in func(*args, **kwargs):
                    loop.call_soon_threadsafe(
                        queue.put_nowait, (item, None)
                    )
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, (None, exc))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        future = loop.run_in_executor(None, _producer)
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                item, exc = chunk
                if exc is not None:
                    raise exc
                yield item
        finally:
            await future

    @staticmethod
    def _is_stream(request: object) -> bool:
        """判断请求是否开启了流式输出."""
        if isinstance(request, Mapping):
            return bool(request.get('stream'))
        return bool(getattr(request, 'stream', False))

    @staticmethod
    def _normalize_stream_request(
        request: (
            Mapping[str, object]
            | ChatCompletionRequest
            | ServiceChatRequest
        ),
    ) -> dict[str, object]:
        """把请求规整为开启 stream 的字典."""
        if isinstance(request, Mapping):
            payload = dict(request)
        else:
            payload = request.model_dump(by_alias=True, exclude_none=True)
        payload['stream'] = True
        return payload

    # ==================================================
    # 连通性测试
    # ==================================================
    async def check_connection(self) -> None:
        """发起轻量只读调用以验证配置与网络连通性.

        前置校验 AK/SK 非空、resource_id 或 collection_name
        至少一个有效, 再调用列举文档接口 (offset=0, limit=1),
        一次调用即可覆盖 AK/SK 鉴权、host 可达性与知识库
        有效性的验证.

        Raises:
            ValueError: AK/SK 未配置, 或 resource_id 与
                collection_name 均未配置.
            Exception: 底层 SDK 返回的任何 API 错误.
        """
        if not self._config.ak or not self._config.sk:
            raise ValueError(
                '火山知识库 AK/SK 未配置, 请在 .env 中设置 '
                'IPO_KNOW_VIKING_KNOWLEDGE__AK 与 '
                'IPO_KNOW_VIKING_KNOWLEDGE__SK'
            )
        if not self._config.resource_id and not self._config.collection_name:
            raise ValueError(
                '火山知识库 resource_id 与 collection_name 均未配置, '
                '至少需要配置其中一项'
            )
        await self.list_docs(ListDocsRequest(offset=0, limit=1))

    # ==================================================
    # 文档管理
    # ==================================================
    async def add_doc_v2(
        self,
        request: AddDocV2Request | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> AddDocV2Response:
        """添加文档 (V2).

        Args:
            request: 添加文档请求.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            添加文档响应.
        """
        return await self._run_in_thread(
            self._get_collection().add_doc_v2,
            request,
            headers=headers,
            timeout=timeout,
        )

    async def delete_doc(
        self,
        doc_id: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> CommonResponse:
        """删除文档.

        Args:
            doc_id: 文档 ID.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            通用响应.
        """
        return await self._run_in_thread(
            self._get_collection().delete_doc,
            doc_id,
            headers=headers,
            timeout=timeout,
        )

    async def get_doc(
        self,
        doc_id: str,
        *,
        return_token_usage: bool = False,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> DocInfo:
        """获取文档详情.

        Args:
            doc_id: 文档 ID.
            return_token_usage: 是否返回 token 用量.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            文档详情.
        """
        return await self._run_in_thread(
            self._get_collection().get_doc,
            doc_id,
            return_token_usage=return_token_usage,
            headers=headers,
            timeout=timeout,
        )

    async def list_docs(
        self,
        request: ListDocsRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> ListDocsResponse:
        """分页列出文档.

        Args:
            request: 文档列表请求.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            文档列表响应.
        """
        return await self._run_in_thread(
            self._get_collection().list_docs,
            request,
            headers=headers,
            timeout=timeout,
        )

    async def update_doc(
        self,
        doc_id: str,
        doc_name: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> CommonResponse:
        """更新文档名称.

        Args:
            doc_id: 文档 ID.
            doc_name: 新文档名称.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            通用响应.
        """
        return await self._run_in_thread(
            self._get_collection().update_doc,
            doc_id,
            doc_name,
            headers=headers,
            timeout=timeout,
        )

    async def update_doc_meta(
        self,
        doc_id: str,
        meta: list[MetaItem],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> CommonResponse:
        """更新文档元数据.

        Args:
            doc_id: 文档 ID.
            meta: 元数据项列表.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            通用响应.
        """
        return await self._run_in_thread(
            self._get_collection().update_doc_meta,
            doc_id,
            meta,
            headers=headers,
            timeout=timeout,
        )

    # ==================================================
    # 切片管理
    # ==================================================
    async def add_point(
        self,
        request: AddPointRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> PointAddResponse:
        """添加切片 (Chunk).

        Args:
            request: 添加切片请求.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            添加切片响应.
        """
        return await self._run_in_thread(
            self._get_collection().add_point,
            request,
            headers=headers,
            timeout=timeout,
        )

    async def delete_point(
        self,
        request: DeletePointRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> CommonResponse:
        """删除切片.

        Args:
            request: 删除切片请求.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            通用响应.
        """
        return await self._run_in_thread(
            self._get_collection().delete_point,
            request,
            headers=headers,
            timeout=timeout,
        )

    async def get_point(
        self,
        point_id: str,
        *,
        get_attachment_link: bool = False,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> PointInfo:
        """获取切片详情.

        Args:
            point_id: 切片 ID.
            get_attachment_link: 是否返回附件下载链接.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            切片详情.
        """
        return await self._run_in_thread(
            self._get_collection().get_point,
            point_id,
            get_attachment_link=get_attachment_link,
            headers=headers,
            timeout=timeout,
        )

    async def list_points(
        self,
        request: ListPointsRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> ListPointsResponse:
        """分页列出切片.

        Args:
            request: 切片列表请求.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            切片列表响应.
        """
        return await self._run_in_thread(
            self._get_collection().list_points,
            request,
            headers=headers,
            timeout=timeout,
        )

    async def update_point(
        self,
        point_id: str,
        update: UpdatePointRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> CommonResponse:
        """更新切片.

        Args:
            point_id: 切片 ID.
            update: 切片更新请求.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            通用响应.
        """
        return await self._run_in_thread(
            self._get_collection().update_point,
            point_id,
            update,
            headers=headers,
            timeout=timeout,
        )

    # ==================================================
    # 知识库检索与对话
    # ==================================================
    async def search_knowledge(
        self,
        request: SearchKnowledgeRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> SearchKnowledgeResponse:
        """知识库检索.

        Args:
            request: 知识库检索请求.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            知识库检索响应.
        """
        return await self._run_in_thread(
            self._get_collection().search_knowledge,
            request,
            headers=headers,
            timeout=timeout,
        )

    async def chat_completion(
        self,
        request: ChatCompletionRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> ChatCompletionResponse:
        """非流式对话补全.

        Args:
            request: 对话补全请求.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            对话补全响应.

        Raises:
            ValueError: 请求开启 stream 时, 应改用
                stream_chat_completion.
        """
        if self._is_stream(request):
            raise ValueError('流式请求请改用 stream_chat_completion')
        return await self._run_in_thread(
            self._get_client().chat_completion,
            request,
            headers=headers,
            timeout=timeout,
        )

    async def service_chat(
        self,
        request: ServiceChatRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> ServiceChatResponse:
        """非流式服务对话.

        Args:
            request: 服务对话请求.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            服务对话响应.

        Raises:
            ValueError: 请求开启 stream 时, 应改用
                stream_service_chat.
        """
        if self._is_stream(request):
            raise ValueError('流式请求请改用 stream_service_chat')
        return await self._run_in_thread(
            self._get_client().service_chat,
            request,
            headers=headers,
            timeout=timeout,
        )

    def stream_chat_completion(
        self,
        request: ChatCompletionRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> AsyncIterator[ChatCompletionResponse]:
        """流式对话补全, 返回异步迭代器.

        Args:
            request: 对话补全请求, 内部会强制开启 stream.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            逐条产出对话补全响应的异步迭代器.
        """
        payload = self._normalize_stream_request(request)
        return self._stream_in_thread(
            self._get_client().chat_completion,
            payload,
            headers=headers,
            timeout=timeout,
        )

    def stream_service_chat(
        self,
        request: ServiceChatRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> AsyncIterator[ServiceChatResponse]:
        """流式服务对话, 返回异步迭代器.

        Args:
            request: 服务对话请求, 内部会强制开启 stream.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            逐条产出服务对话响应的异步迭代器.
        """
        payload = self._normalize_stream_request(request)
        return self._stream_in_thread(
            self._get_client().service_chat,
            payload,
            headers=headers,
            timeout=timeout,
        )
