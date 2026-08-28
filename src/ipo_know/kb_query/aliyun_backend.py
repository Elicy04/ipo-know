"""阿里云百炼知识库查询后端.

检索走 bailian SDK 的 Retrieve 接口 (经客户端现有限流通道);
问答走独立 REST + API-Key Bearer + SSE 链路
(``AliyunChatClient``, 协议见 docs/references/AliyunSDK/
ai_qa_API.md), 三阶段帧规整为统一的 ``ChatStreamEvent``
事件序列 (planning → reasoning_delta, tool_return docs →
references, generating → answer_delta, 尾帧 usage/done).
"""

import asyncio
import json
import threading
from collections.abc import AsyncIterator
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any

from alibabacloud_bailian20231229 import models as bailian_models
from loguru import logger

from ipo_know.clients.aliyun_knowledge.chat_client import AliyunChatClient
from ipo_know.clients.aliyun_knowledge.chat_client import AliyunChatError
from ipo_know.clients.aliyun_knowledge.chat_client import ChatSseEvent
from ipo_know.clients.aliyun_knowledge.client import AliyunKnowledgeClient
from ipo_know.kb_query.dto import ChatStreamEvent
from ipo_know.kb_query.dto import SearchHit


# DenseSimilarityTopK / SparseSimilarityTopK 单路取值上限.
_MAX_TOP_K = 100

# RerankTopN 取值上限 (官方范围 [1-20]).
_MAX_RERANK_TOP_N = 20


class AliyunQueryBackend:
    """阿里云百炼检索与问答后端.

    Attributes:
        _client: 百炼知识库异步客户端 (AK/SK 管理链路).
        _api_key: 百炼 API-Key, 仅问答使用.
        _agent_id: 知识问答服务应用 ID (aid-xxx), 仅问答使用.
    """

    def __init__(
        self,
        client: AliyunKnowledgeClient,
        api_key: str = '',
        agent_id: str = '',
    ) -> None:
        """初始化阿里云查询后端.

        Args:
            client: 百炼知识库异步客户端实例.
            api_key: 百炼 API-Key, 问答必需.
            agent_id: 知识问答服务应用 ID, 问答必需.
        """
        self._client = client
        self._api_key = api_key.strip()
        self._agent_id = agent_id.strip()

    @property
    def supports_search(self) -> bool:
        """阿里云支持知识库检索."""
        return True

    @property
    def supports_chat(self) -> bool:
        """阿里云支持知识问答."""
        return True

    # --------------------------------------------------
    # 检索
    # --------------------------------------------------
    async def search(
        self, query: str, limit: int
    ) -> list[SearchHit]:
        """调用 Retrieve 接口并归一化 Data.Nodes.

        Args:
            query: 检索文本.
            limit: 期望返回的命中条数上限, 按官方参数
                范围裁剪 (TopK ≤ 100, RerankTopN ≤ 20).

        Returns:
            归一化后的命中结果列表.
        """
        limit = max(1, limit)
        request = bailian_models.RetrieveRequest(
            index_id=self._client.index_id,
            query=query,
            dense_similarity_top_k=min(limit, _MAX_TOP_K),
            sparse_similarity_top_k=min(limit, _MAX_TOP_K),
            rerank_top_n=min(limit, _MAX_RERANK_TOP_N),
        )
        logger.debug(
            '阿里云检索发起 | index_id={} | top_k={} | rerank_top_n={}',
            self._client.index_id,
            min(limit, _MAX_TOP_K),
            min(limit, _MAX_RERANK_TOP_N),
        )
        response = await self._client.retrieve(request)
        body = response.body
        nodes = (
            body.data.nodes
            if body is not None and body.data is not None
            else None
        )
        logger.debug(
            '阿里云检索返回 | nodes={} 条',
            len(nodes or []),
        )
        return [self._to_hit(node) for node in nodes or []]

    @staticmethod
    def _to_hit(
        node: bailian_models.RetrieveResponseBodyDataNodes,
    ) -> SearchHit:
        """把百炼检索节点归一化为 SearchHit.

        Metadata 官方返回可能为 JSON 字符串或字典, 统一
        解析后提取文档信息.

        Args:
            node: 检索响应中的文本切片节点.

        Returns:
            归一化命中结果.
        """
        meta = AliyunQueryBackend._parse_metadata(node.metadata)
        return SearchHit(
            content=node.text or '',
            score=float(node.score or 0.0),
            doc_name=str(meta.get('doc_name') or ''),
            source='aliyun',
            title=str(meta.get('title') or ''),
            doc_id=str(meta.get('doc_id') or ''),
        )

    @staticmethod
    def _parse_metadata(metadata: object) -> dict[str, object]:
        """解析节点 Metadata, 兼容 JSON 字符串与字典.

        Args:
            metadata: 节点元数据, 可能为 str/dict/None.

        Returns:
            元数据字典, 解析失败返回空字典.
        """
        if isinstance(metadata, dict):
            return metadata
        if isinstance(metadata, str) and metadata.strip():
            try:
                parsed = json.loads(metadata)
            except ValueError:
                logger.debug('检索节点 Metadata 解析失败, 已忽略')
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}

    # --------------------------------------------------
    # 流式问答
    # --------------------------------------------------
    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        stop_event: threading.Event | None = None,
        session_files: Sequence[str] | None = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        """调用知识问答 SSE 接口并规整三阶段帧为事件流.

        协议见 docs/references/AliyunSDK/ai_qa_API.md:
        planning 段规划文本映射 reasoning_delta (供思考区
        展示); tool_return 帧 docs 映射 references (可能
        多次出现, 每次都产出); generating 段回答映射
        answer_delta; 尾帧 usage/done 对齐火山实现.

        Args:
            messages: role/content 消息序列, 全量回传.
            stop_event: 停止标志, 置位后尽快停止产出
                (停止路径不补发 done).
            session_files: 会话临时文件 ID 列表, 经 AddFile
                接口注册并解析完成, 为空时不携带.

        Yields:
            reasoning_delta (规划段增量) / references (引用
            切片) / answer_delta (回答增量) / usage (token
            用量) / done (结束) / error (流内异常描述).
        """
        missing: list[str] = []
        if not self._api_key:
            missing.append('API Key')
        if not self._agent_id:
            missing.append('知识问答服务 ID')
        if missing:
            logger.warning(
                '阿里云问答前置校验失败 | missing={}',
                ' 与 '.join(missing),
            )
            yield ChatStreamEvent(
                kind='error',
                payload=(
                    '阿里云问答需要 '
                    + ' 与 '.join(missing)
                    + ', 请到平台配置页签的问答配置区填写'
                ),
            )
            return
        chat_client = AliyunChatClient(
            api_key=self._api_key,
            workspace_id=self._client.workspace_id,
            agent_id=self._agent_id,
            region_id=self._client.region_id,
        )
        usage: object = None
        error_seen = False
        stopped = False
        try:
            stream = chat_client.stream_chat(
                messages, session_files=session_files
            )
            async for event in stream:
                if (
                    stop_event is not None
                    and stop_event.is_set()
                ):
                    stopped = True
                    break
                if event.kind == 'error':
                    logger.warning(
                        '阿里云问答流内错误帧 | payload={}',
                        event.payload,
                    )
                    error_seen = True
                if event.kind == 'usage':
                    usage = event.payload
                for item in self._map_event(event):
                    yield item
            # 停止路径不补发 done, 与火山桥语义对齐
            if not error_seen and not stopped:
                yield ChatStreamEvent(
                    kind='done', payload=usage
                )
        except asyncio.CancelledError:
            raise
        except AliyunChatError as exc:
            logger.error('阿里云知识问答调用失败 | {}', exc)
            yield ChatStreamEvent(
                kind='error', payload=str(exc)
            )
        except Exception as exc:
            logger.exception('阿里云知识问答流式调用失败')
            yield ChatStreamEvent(
                kind='error', payload=str(exc)
            )

    @staticmethod
    def _map_event(
        event: ChatSseEvent,
    ) -> list[ChatStreamEvent]:
        """把客户端中间事件映射为归一问答事件.

        done 由消费循环在流结束后统一补发, 此处不转发,
        避免重复.

        Args:
            event: 客户端产出的中间事件.

        Returns:
            映射后的归一事件列表, 可能为空.
        """
        if event.kind == 'planning_delta':
            return [
                ChatStreamEvent(
                    kind='reasoning_delta', payload=event.payload
                )
            ]
        if event.kind == 'references':
            docs = event.payload if isinstance(
                event.payload, list
            ) else []
            hits = [AliyunQueryBackend._doc_to_hit(d) for d in docs]
            return [
                ChatStreamEvent(kind='references', payload=hits)
            ] if hits else []
        if event.kind == 'answer_delta':
            return [
                ChatStreamEvent(
                    kind='answer_delta', payload=event.payload
                )
            ]
        if event.kind == 'usage':
            return [
                ChatStreamEvent(kind='usage', payload=event.payload)
            ]
        if event.kind == 'error':
            return [
                ChatStreamEvent(kind='error', payload=event.payload)
            ]
        return []

    @staticmethod
    def _doc_to_hit(doc: Mapping[str, Any]) -> SearchHit:
        """把 tool_return 帧引用切片归一化为 SearchHit.

        官方 docs 字段名未完全固定 (含正文与多维得分),
        对常见候选键宽容取值.

        Args:
            doc: 引用切片原始字典.

        Returns:
            归一化命中结果.
        """
        content = doc.get('content') or doc.get('text') or ''
        score = doc.get('score')
        if isinstance(score, Mapping):
            # 多维得分字典: 取首个数值项作展示得分
            score = next(
                (v for v in score.values()
                 if isinstance(v, (int, float))),
                0.0,
            )
        doc_name = str(
            doc.get('doc_name') or doc.get('file_name') or ''
        )
        return SearchHit(
            content=str(content),
            score=float(score or 0.0),
            doc_name=doc_name,
            source='aliyun',
            title=str(doc.get('title') or doc_name),
            doc_id=str(doc.get('doc_id') or doc.get('file_id') or ''),
        )
