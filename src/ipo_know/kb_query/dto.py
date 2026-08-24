"""知识库检索与问答抽象层的数据传输对象."""

from dataclasses import dataclass
from typing import Any
from typing import Literal


@dataclass
class SearchHit:
    """归一化后的单条知识库检索命中结果.

    字段取阿里云百炼 Retrieve 与火山引擎 search_knowledge
    两平台实际返回的并集, 缺失字段保持空值.

    Attributes:
        content: 命中的文本切片内容.
        score: 相似度/重排序得分.
        doc_name: 来源文档名称.
        source: 来源标识 (火山为 doc_info.source,
            阿里云固定为 ``aliyun``).
        title: 切片标题或文档标题.
        doc_id: 文档 ID (阿里云 metadata 的 doc_id).
        point_id: 切片 ID (火山 PointInfo.point_id).
    """

    content: str = ''
    score: float = 0.0
    doc_name: str = ''
    source: str = ''
    title: str = ''
    doc_id: str = ''
    point_id: str = ''


#: 问答流式事件类型.
ChatStreamEventKind = Literal[
    'answer_delta', 'reasoning_delta', 'references',
    'usage', 'done', 'error',
]


@dataclass
class ChatStreamEvent:
    """问答流式管线的规整事件.

    Attributes:
        kind: 事件类型. ``answer_delta`` 回答增量文本;
            ``reasoning_delta`` 推理模型思考段增量文本
            (出现在回答之前, 可能很长);
            ``references`` 引用切片列表 (list[SearchHit]);
            ``usage`` token 用量; ``done`` 流正常结束;
            ``error`` 流内错误描述.
        payload: 事件携带的数据, 结构随 kind 而定.
    """

    kind: ChatStreamEventKind
    payload: Any = None
