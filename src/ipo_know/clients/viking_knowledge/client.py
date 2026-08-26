"""火山引擎 VikingDB 知识库异步客户端.

对官方 vikingdb-python-sdk 的高层知识库接口做薄封装, 对外暴露
async 接口, 内部通过 asyncio.to_thread 将同步 SDK 调用投递到线程池,
避免阻塞事件循环.

覆盖文档管理、切片 (Chunk) 管理、知识库检索与对话补全等接口.
流式接口支持通过 threading.Event 停止标志即时中止生成.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterator
from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Mapping

import requests as _requests
from loguru import logger
from vikingdb import IAM
from vikingdb import APIKey
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
from volcengine.auth.SignerV4 import SignerV4
from volcengine.base.Request import Request
from volcengine.Credentials import Credentials

from ipo_know.clients.monitor_dto import BalanceInfo
from ipo_know.clients.monitor_dto import BillDetailItem
from ipo_know.config.config import VikingKnowledgeSettings
from ipo_know.config.config import settings


# 问答链路 (API Key 实例) 超时秒数: 推理模型长思考静默期
# 可能超过管理链路默认 30s, 单独放宽并与阿里云问答链路
# 120s 对齐. 已核验 .venv 中 VikingKnowledge 构造的
# timeout 为单一 int 数值 (同时作为 connect 与 socket
# 超时), 故整体取值.
_CHAT_TIMEOUT_SECONDS = 120


class VikingKnowledgeClient:
    """火山引擎 VikingDB 知识库异步客户端.

    薄封装官方 SDK 的同步接口, 对外提供 async 方法. 底层 SDK
    (VikingKnowledge / KnowledgeCollection) 在首次调用时懒加载,
    文档/切片/检索链路的鉴权采用 AK/SK (IAM); 知识问答
    (service_chat) 接口强制 API Key 鉴权, 使用独立的
    API Key 实例, 两个实例互不影响.

    Attributes:
        _config: 知识库配置.
        _client: 底层 VikingKnowledge 同步客户端 (IAM 鉴权,
            懒加载).
        _api_key_client: 底层 VikingKnowledge 同步客户端
            (API Key 鉴权, 懒加载, 仅知识问答使用).
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
        self._api_key_client: VikingKnowledge | None = None
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
                    '火山知识库 AK/SK 未配置，请通过 GUI 配置填写'
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

    def _get_api_key_client(self) -> VikingKnowledge:
        """懒加载 API Key 鉴权的 VikingKnowledge 客户端.

        仅供知识问答 (service_chat) 链路使用: 该接口强制
        API Key 鉴权, IAM AK/SK 会报 apikey is empty.
        连接参数 host/region/scheme 复用同一配置, 超时
        单独放宽到 ``_CHAT_TIMEOUT_SECONDS`` (推理模型长
        思考静默期保护); 无需 ak/sk; 问答依赖请求体中的
        service_resource_id, 与知识库 resource_id 无关.

        Raises:
            ValueError: api_key 未配置.
        """
        if self._api_key_client is None:
            if not self._config.api_key:
                raise ValueError(
                    '问答需要 API Key, 请到平台配置页签的'
                    '问答配置区填写 (或设置环境变量 '
                    'IPO_KNOW_VIKING_KNOWLEDGE__API_KEY)'
                )
            auth = APIKey(api_key=self._config.api_key)
            self._api_key_client = VikingKnowledge(
                host=self._config.host,
                region=self._config.region,
                auth=auth,
                scheme=self._config.scheme,
                timeout=_CHAT_TIMEOUT_SECONDS,
            )
        return self._api_key_client

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
        func: Callable[..., Iterator[object]],
        *args: object,
        stop_event: threading.Event | None = None,
        **kwargs: object,
    ) -> AsyncIterator[object]:
        """把同步生成器桥接为可取消的异步迭代器.

        生产者线程逐片检查停止标志, 置位后丢弃剩余分片快速
        退出; 消费端取消 (aclose / 提前跳出迭代) 时置位标志,
        且不再等待生产者线程结束, 保证取消即时返回.

        Warning:
            取消/提前退出即时返回不代表底层 HTTP 流已关闭:
            生产者线程可能仍在阻塞读取下一分片, 资源释放依赖
            SDK 生成器自身在迭代终止后的清理行为.

        Args:
            func: 返回同步迭代器的工厂, 如 SDK 的流式接口.
            *args: 透传给 func 的位置参数.
            stop_event: 外部停止标志, 置位后停止产出; 为 None
                时使用内部标志, 取消时自动置位. 外部传入时
                本方法不会改写其置位状态.
            **kwargs: 透传给 func 的关键字参数.

        Yields:
            同步生成器逐条产出的分片.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        # 仅自持标志可在收尾时置位; 外部传入的 stop_event
        # 生命周期归调用方所有, 误置位会污染复用同一 Event
        # 的后续请求 (第二次请求会被立即中止)
        owns_stop = stop_event is None
        internal_stop = stop_event or threading.Event()
        finished = False

        def _producer() -> None:
            try:
                for item in func(*args, **kwargs):
                    if internal_stop.is_set():
                        break
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
                    finished = True
                    break
                item, exc = chunk
                if exc is not None:
                    raise exc
                if internal_stop.is_set():
                    break
                yield item
        finally:
            if owns_stop:
                internal_stop.set()
            if finished:
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
                '火山知识库 AK/SK 未配置，请通过 GUI 配置填写'
            )
        if not self._config.resource_id and not self._config.collection_name:
            raise ValueError(
                '火山知识库 resource_id 与 collection_name 均未配置, '
                '至少需要配置其中一项'
            )
        await self.list_docs(ListDocsRequest(offset=0, limit=1))

    # ==================================================
    # 监控 / 余额 / 账单
    # ==================================================
    def _request_billing(
        self,
        action: str,
        params: dict[str, object] | None = None,
        *,
        method: str = 'GET',
    ) -> dict:
        """发送火山引擎 billing 开放平台签名请求.

        使用 volcengine V4 签名 (service=billing),
        目标 Host 为 open.volcengineapi.com.
        GET 请求参数放 query; POST 请求参数放 JSON body.

        Args:
            action: API Action 名称.
            params: 业务参数.
            method: HTTP 方法, 默认 GET.

        Returns:
            响应中的 Result 字典.

        Raises:
            RuntimeError: HTTP 状态码非 200 或响应中
                包含错误信息.
        """
        credentials = Credentials(
            self._config.ak,
            self._config.sk,
            'billing',
            self._config.region,
        )
        req = Request()
        req.set_schema(self._config.scheme)
        req.set_method(method)
        req.set_host('open.volcengineapi.com')
        req.set_path('/')
        # Action/Version 始终放 query
        query = {
            'Action': action,
            'Version': '2022-01-01',
        }
        req.set_query(query)
        body_bytes = b''
        if method == 'POST' and params:
            # POST: 业务参数放 JSON body, 保持原始类型
            body_str = json.dumps(params)
            body_bytes = body_str.encode('utf-8')
            req.headers['Content-Type'] = 'application/json'
            req.set_body(body_str)
        elif params:
            # GET: 业务参数放 query
            req.set_query({
                **query,
                **{
                    k: str(v) for k, v in params.items()
                },
            })
        SignerV4.sign(req, credentials)
        url = req.build()
        if method == 'POST':
            resp = _requests.post(
                url,
                headers=req.headers,
                data=body_bytes,
                timeout=self._config.timeout,
            )
        else:
            resp = _requests.get(
                url,
                headers=req.headers,
                timeout=self._config.timeout,
            )
        if resp.status_code != 200:
            logger.error(
                '火山 billing 请求失败'
                ' | action={} | status={} | body={}',
                action,
                resp.status_code,
                resp.text,
            )
            raise RuntimeError(
                f'火山 billing 请求失败'
                f' | status={resp.status_code}'
            )
        data = resp.json()
        meta = data.get('ResponseMetadata', {})
        if meta.get('Error'):
            err = meta['Error']
            logger.error(
                '火山 billing 响应错误'
                ' | action={} | code={} | msg={} | body={}',
                action,
                err.get('Code', ''),
                err.get('Message', ''),
                resp.text,
            )
            raise RuntimeError(
                f'火山 billing 响应错误 | '
                f"code={err.get('Code', '')} | "
                f"message={err.get('Message', '')}"
            )
        return data.get('Result', {})

    async def get_collection_info(self) -> dict:
        """获取知识库详情信息.

        通过 POST /api/knowledge/collection/info 接口
        获取知识库描述、版本、文档数等详细信息.
        复用现有 IAM 鉴权签名机制.

        Returns:
            知识库信息字典, 包含 collection_name,
            doc_num, create_time 等字段.
        """
        logger.debug(
            '火山 get_collection_info 调用 | '
            'resource_id={}',
            self._config.resource_id,
        )

        def _call() -> dict:
            client = self._get_client()
            api_info = client.api_info['SearchCollection']
            from volcengine.ApiInfo import ApiInfo
            info_api = ApiInfo(
                'POST',
                '/api/knowledge/collection/info',
                {}, {}, api_info.header,
            )
            req = client.prepare_request(info_api, {})
            payload = {}
            if self._config.resource_id:
                payload['resource_id'] = (
                    self._config.resource_id
                )
            if self._config.project_name:
                payload['project'] = (
                    self._config.project_name
                )
            req.body = json.dumps(payload)
            client.auth_provider.sign_request(req)
            url = req.build()
            resp = _requests.post(
                url,
                headers=req.headers,
                data=req.body.encode('utf-8'),
                timeout=(
                    client.service_info.connection_timeout,
                    client.service_info.socket_timeout,
                ),
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f'火山 collection_info 请求失败'
                    f' | status={resp.status_code}'
                )
            result = resp.json()
            if result.get('code', 0) != 0:
                raise RuntimeError(
                    f'火山 collection_info 响应错误'
                    f" | code={result.get('code')}"
                    f" | message={result.get('message', '')}"
                )
            return result.get('data', {})

        data = await self._run_in_thread(_call)
        logger.debug(
            '火山 get_collection_info 响应 | '
            'collection_name={} | doc_num={}',
            data.get('collection_name', ''),
            data.get('doc_num', 0),
        )
        return data

    async def query_account_balance(self) -> BalanceInfo:
        """查询火山引擎账户余额.

        通过 GET open.volcengineapi.com
        ?Action=QueryBalanceAcct&Version=2022-01-01
        查询账户可用余额、现金余额、信控额度等信息.

        Returns:
            BalanceInfo DTO, platform='volc'.
        """
        logger.debug('火山 query_account_balance 调用')

        def _call() -> BalanceInfo:
            result = self._request_billing(
                'QueryBalanceAcct',
            )
            return BalanceInfo(
                platform='volc',
                available_amount=str(
                    result.get(
                        'AvailableBalance', '0',
                    )
                ),
                cash_amount=str(
                    result.get('CashBalance', '0')
                ),
                credit_amount=str(
                    result.get('CreditLimit', '0')
                ),
                currency='CNY',
            )

        info = await self._run_in_thread(_call)
        logger.debug(
            '火山 query_account_balance 响应 | '
            'available={}',
            info.available_amount,
        )
        return info

    async def query_bill_details(
        self,
        bill_period: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BillDetailItem]:
        """查询火山引擎账单明细.

        通过 GET open.volcengineapi.com
        ?Action=ListBillDetail&Version=2022-01-01
        获取指定账期的消费明细列表.

        Args:
            bill_period: 账期, YYYY-MM 格式.
            limit: 每页记录数, 上限 300.
            offset: 分页偏移量.

        Returns:
            BillDetailItem DTO 列表.
        """
        logger.debug(
            '火山 query_bill_details 调用 | '
            'bill_period={} | limit={} | offset={}',
            bill_period, limit, offset,
        )

        def _call() -> list[BillDetailItem]:
            result = self._request_billing(
                'ListBillDetail',
                {
                    'BillPeriod': bill_period,
                    'Limit': limit,
                    'Offset': offset,
                },
                method='POST',
            )
            items: list[BillDetailItem] = []
            for item in result.get('List', []):
                items.append(
                    BillDetailItem(
                        record_id=str(
                            item.get(
                                'BillDetailId', '',
                            )
                        ),
                        date=str(
                            item.get(
                                'ExpenseDate', '',
                            )
                        ),
                        product=str(
                            item.get(
                                'ProductZh', '',
                            )
                        ),
                        amount=str(
                            item.get(
                                'PayableAmount', '0',
                            )
                        ),
                        payment_method=str(
                            item.get(
                                'BillingMode', '',
                            )
                        ),
                        remark=str(
                            item.get(
                                'BillCategory', '',
                            )
                        ),
                    )
                )
            return items

        details = await self._run_in_thread(_call)
        logger.debug(
            '火山 query_bill_details 响应 | '
            'count={}',
            len(details),
        )
        return details

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
        resource_id = (
            request.get('service_resource_id', '')
            if isinstance(request, Mapping)
            else getattr(request, 'service_resource_id', '')
        )
        logger.debug(
            '火山 search_knowledge 调用 | service_resource_id={}',
            resource_id,
        )
        response = await self._run_in_thread(
            self._get_collection().search_knowledge,
            request,
            headers=headers,
            timeout=timeout,
        )
        _result = response.result
        logger.debug(
            '火山 search_knowledge 响应 | results={}',
            len(_result.result_list if _result else []),
        )
        return response

    async def chat_completion(
        self,
        request: ChatCompletionRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> ChatCompletionResponse:
        """非流式对话补全 (IAM AK/SK 鉴权).

        该接口当前不支持 API Key 作为知识库 SDK 鉴权,
        故保持使用 IAM 实例.

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
        """非流式服务对话 (API Key 鉴权).

        Args:
            request: 服务对话请求.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.

        Returns:
            服务对话响应.

        Raises:
            ValueError: 请求开启 stream 时, 应改用
                stream_service_chat; 或 api_key 未配置.
        """
        if self._is_stream(request):
            raise ValueError('流式请求请改用 stream_service_chat')
        return await self._run_in_thread(
            self._get_api_key_client().service_chat,
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
        stop_event: threading.Event | None = None,
    ) -> AsyncIterator[ChatCompletionResponse]:
        """流式对话补全 (IAM AK/SK 鉴权), 返回异步迭代器.

        该接口当前不支持 API Key 作为知识库 SDK 鉴权,
        故保持使用 IAM 实例.

        Args:
            request: 对话补全请求, 内部会强制开启 stream.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.
            stop_event: 停止标志, 置位后立即停止产出分片,
                用于实现 "停止生成"; 为 None 时仅支持通过
                取消迭代 (aclose) 停止.

        Returns:
            逐条产出对话补全响应的异步迭代器.
        """
        payload = self._normalize_stream_request(request)
        return self._stream_in_thread(
            self._get_client().chat_completion,
            payload,
            headers=headers,
            timeout=timeout,
            stop_event=stop_event,
        )

    def stream_service_chat(
        self,
        request: ServiceChatRequest | Mapping[str, object],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> AsyncIterator[ServiceChatResponse]:
        """流式服务对话 (API Key 鉴权), 返回异步迭代器.

        Args:
            request: 服务对话请求, 内部会强制开启 stream.
            headers: 额外请求头.
            timeout: 请求超时时间, 覆盖配置默认值.
            stop_event: 停止标志, 置位后立即停止产出分片,
                用于实现 "停止生成"; 为 None 时仅支持通过
                取消迭代 (aclose) 停止.

        Returns:
            逐条产出服务对话响应的异步迭代器.

        Raises:
            ValueError: api_key 未配置.
        """
        payload = self._normalize_stream_request(request)
        return self._stream_in_thread(
            self._get_api_key_client().service_chat,
            payload,
            headers=headers,
            timeout=timeout,
            stop_event=stop_event,
        )
