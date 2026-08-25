"""火山引擎 VikingDB 知识库查询后端.

包装 ``VikingKnowledgeClient``: 检索走 ``search_knowledge``,
问答走 ``stream_service_chat``, 并把 SSE 帧规整为统一的
``ChatStreamEvent`` 事件序列 (首流 result_list → references,
中段 generated_answer → answer_delta, 尾流 token_usage →
usage/done).
"""

import asyncio
import threading
from collections.abc import AsyncIterator
from collections.abc import Mapping
from collections.abc import Sequence

from loguru import logger
from vikingdb.knowledge import ChatMessage
from vikingdb.knowledge import SearchKnowledgeRequest
from vikingdb.knowledge import ServiceChatRequest
from vikingdb.knowledge.models.point import PointInfo
from vikingdb.knowledge.models.service_chat import ServiceChatRetrieveItem

from ipo_know.clients.viking_knowledge import VikingKnowledgeClient
from ipo_know.kb_query.dto import ChatStreamEvent
from ipo_know.kb_query.dto import SearchHit


class VolcQueryBackend:
    """火山引擎 VikingDB 检索与问答后端.

    Attributes:
        _client: 火山知识库异步客户端.
        _service_resource_id: 知识服务 ID, 仅问答使用.
    """

    def __init__(
        self,
        client: VikingKnowledgeClient,
        service_resource_id: str = '',
    ) -> None:
        """初始化火山查询后端.

        Args:
            client: 火山知识库异步客户端实例.
            service_resource_id: 知识服务 ID, 问答必需.
        """
        self._client = client
        self._service_resource_id = service_resource_id.strip()

    @property
    def supports_search(self) -> bool:
        """火山引擎支持知识库检索."""
        return True

    @property
    def supports_chat(self) -> bool:
        """火山引擎支持知识问答."""
        return True

    # --------------------------------------------------
    # 检索
    # --------------------------------------------------
    async def search(
        self, query: str, limit: int
    ) -> list[SearchHit]:
        """调用 search_knowledge 并归一化 result_list.

        Args:
            query: 检索文本.
            limit: 期望返回的命中条数上限.

        Returns:
            归一化后的命中结果列表.
        """
        request = SearchKnowledgeRequest(
            query=query, limit=max(1, limit)
        )
        response = await self._client.search_knowledge(request)
        result = response.result
        items = result.result_list if result else []
        return [self._to_hit(item) for item in items]

    @staticmethod
    def _to_hit(
        item: PointInfo | ServiceChatRetrieveItem,
    ) -> SearchHit:
        """把火山检索/问答切片归一化为 SearchHit.

        Args:
            item: PointInfo (检索) 或 ServiceChatRetrieveItem
                (问答引用) 切片对象.

        Returns:
            归一化命中结果.
        """
        doc_info = item.doc_info
        return SearchHit(
            content=item.content or '',
            score=float(item.score or 0.0),
            doc_name=(
                doc_info.doc_name if doc_info else ''
            ) or '',
            source=(doc_info.source if doc_info else '') or '',
            title=item.chunk_title or '',
            point_id=str(item.point_id or ''),
        )

    # --------------------------------------------------
    # 流式问答
    # --------------------------------------------------
    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        stop_event: threading.Event | None = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        """调用 stream_service_chat 并规整 SSE 帧为事件流.

        Args:
            messages: role/content 消息序列, 全量回传.
            stop_event: 停止标志, 置位后立即停止产出.

        Yields:
            references (首流命中切片) / reasoning_delta (推理
            模型思考段增量, 出现在回答之前) / answer_delta
            (回答增量) / usage (token 用量) / done (结束) /
            error (流内异常描述).
        """
        if not self._service_resource_id:
            logger.warning(
                '火山问答前置校验失败 | reason=缺少 '
                'service_resource_id',
            )
            yield ChatStreamEvent(
                kind='error',
                payload=(
                    '火山问答需要 service_resource_id, '
                    '请到平台配置页签的问答配置区填写'
                ),
            )
            return
        chat_messages = [
            ChatMessage(
                role=str(msg['role']),
                content=str(msg['content']),
            )
            for msg in messages
        ]
        request = ServiceChatRequest(
            service_resource_id=self._service_resource_id,
            messages=chat_messages,
        )
        references_emitted = False
        usage: object = None
        try:
            stream = self._client.stream_service_chat(
                request, stop_event=stop_event
            )
            async for frame in stream:
                data = frame.result
                if data is None:
                    continue
                if not references_emitted and data.result_list:
                    references_emitted = True
                    yield ChatStreamEvent(
                        kind='references',
                        payload=[
                            self._to_hit(item)
                            for item in data.result_list
                        ],
                    )
                if data.generated_answer:
                    yield ChatStreamEvent(
                        kind='answer_delta',
                        payload=data.generated_answer,
                    )
                # 推理模型 (如 doubao-seed 系列) 先长时间流式
                # 输出 reasoning_content, 期间 generated_answer
                # 始终为空; 转发思考段增量, 供 UI 展示进行中
                # 状态, 避免回答前气泡长时间空白
                if data.reasoning_content:
                    yield ChatStreamEvent(
                        kind='reasoning_delta',
                        payload=data.reasoning_content,
                    )
                if data.token_usage:
                    usage = data.token_usage
                    yield ChatStreamEvent(
                        kind='usage', payload=usage
                    )
            yield ChatStreamEvent(kind='done', payload=usage)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception('火山知识问答流式调用失败')
            yield ChatStreamEvent(
                kind='error', payload=str(exc)
            )
