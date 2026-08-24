"""知识库查询后端 Protocol 定义.

以 Protocol 描述检索/问答后端的统一契约, 两平台实现
仅需满足该结构即可被工厂装配, 无需继承基类.
"""

import threading
from collections.abc import AsyncIterator
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Protocol
from typing import runtime_checkable

from ipo_know.kb_query.dto import ChatStreamEvent
from ipo_know.kb_query.dto import SearchHit


@runtime_checkable
class QueryBackend(Protocol):
    """知识库检索与问答后端契约.

    Attributes:
        supports_search: 是否支持知识库检索.
        supports_chat: 是否支持知识问答.
    """

    @property
    def supports_search(self) -> bool:
        """是否支持知识库检索."""
        ...

    @property
    def supports_chat(self) -> bool:
        """是否支持知识问答."""
        ...

    async def search(
        self, query: str, limit: int
    ) -> list[SearchHit]:
        """执行知识库检索.

        Args:
            query: 检索文本.
            limit: 期望返回的命中条数上限.

        Returns:
            归一化后的命中结果列表, 可能为空.
        """
        ...

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        stop_event: threading.Event | None = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        """发起流式知识问答, 返回异步事件迭代器.

        Args:
            messages: 会话历史与本次提问组成的 role/content
                消息序列, 平台不保存会话状态需全量回传.
            stop_event: 停止标志, 置位后尽快结束产出.

        Returns:
            逐条产出规整事件的异步迭代器.
        """
        ...
