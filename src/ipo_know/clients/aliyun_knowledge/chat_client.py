"""阿里云百炼知识问答 REST + SSE 流式客户端.

协议依据 ``docs/references/AliyunSDK/ai_qa_API.md``:
端点 ``POST https://{workspace_id}.{region_id}.maas.aliyuncs.com
/api/v2/apps/knowledge/chat``, ``Authorization: Bearer <百炼
API-Key>`` 鉴权, ``stream`` 必须为 true, 帧按
``message.extra.step`` 划分三阶段 (planning 规划文本流 →
tool_calling 工具调用/返回 → generating 最终回答增量),
错误以流内 ``event: error`` 帧返回 (鉴权失败为 HTTP 401).

与 AK/SK 管理 API 客户端完全独立: 问答专用 httpx 通道,
读取超时默认 120 秒 (长生成), 取消依赖调用方对异步任务
``task.cancel()``, 无需线程桥.
"""

import json
from collections.abc import AsyncIterator
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import Literal

import httpx
from loguru import logger


#: 问答流式中间事件类型.
ChatSseEventKind = Literal[
    'planning_delta', 'references', 'answer_delta',
    'usage', 'error', 'done',
]


@dataclass
class ChatSseEvent:
    """问答 SSE 流规整后的中间事件.

    Attributes:
        kind: 事件类型. ``planning_delta`` 规划阶段文本增量;
            ``references`` 工具返回的引用切片原始字典列表
            (tool_return 帧, 可能出现多次, 每次单独产出);
            ``answer_delta`` 最终回答文本增量; ``usage``
            token 用量结算; ``error`` 流内错误描述;
            ``done`` 流正常结束.
        payload: 事件携带数据, 结构随 kind 而定.
    """

    kind: ChatSseEventKind
    payload: Any = None


class AliyunChatError(RuntimeError):
    """阿里云知识问答调用失败 (HTTP 层错误归一异常).

    Attributes:
        status_code: HTTP 状态码, 传输层错误时为 None.
        code: 平台错误码 (如 InvalidApiKey), 可能为 None.
        request_id: 平台请求 ID, 可能为 None.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """初始化问答调用异常.

        Args:
            message: 可读错误描述.
            status_code: HTTP 状态码, 传输层错误时为 None.
            code: 平台错误码, 可能为 None.
            request_id: 平台请求 ID, 可能为 None.
        """
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.request_id = request_id


class SseFrameAssembler:
    """SSE 帧装配器: 逐行喂入, 产出完整 (event, data) 帧.

    同步与异步两条解析链路共用本装配器, 保证帧切分语义
    一致且可脱离网络单测.
    """

    def __init__(self) -> None:
        """初始化装配器, 帧间状态归零."""
        self._event = 'message'
        self._data_lines: list[str] = []

    def feed(self, line: str) -> tuple[str, str] | None:
        """喂入一行 (不含换行符), 帧完结时返回该帧.

        Args:
            line: 响应行文本.

        Returns:
            (事件名, data 原文); 帧未完结时返回 None.
        """
        if not line.strip():
            frame = self.flush()
            self._event = 'message'
            return frame
        if line.startswith(':'):
            return None
        if line.startswith('event:'):
            self._event = line[len('event:'):].strip()
        elif line.startswith('data:'):
            data = line[len('data:'):]
            self._data_lines.append(data.lstrip(' '))
        return None

    def flush(self) -> tuple[str, str] | None:
        """流结束时冲刷残留 data 行组成的末帧.

        Returns:
            (事件名, data 原文); 无残留时返回 None.
        """
        if not self._data_lines:
            return None
        frame = (self._event, '\n'.join(self._data_lines))
        self._data_lines = []
        return frame


def iter_sse_frames(
    lines: Iterable[str],
) -> Iterator[tuple[str, str]]:
    """按 SSE 规范把行序列切分为 (event, data) 帧.

    帧以空行分隔; ``event:`` 行决定事件名 (缺省 message);
    多条 ``data:`` 行以换行连接; 注释行 (``:`` 开头) 与
    未知字段忽略.

    Args:
        lines: 无换行符的响应行序列.

    Yields:
        (事件名, data 原文) 二元组.
    """
    assembler = SseFrameAssembler()
    for line in lines:
        frame = assembler.feed(line)
        if frame is not None:
            yield frame
    frame = assembler.flush()
    if frame is not None:
        yield frame


def interpret_frame(
    event: str, data: str
) -> list[ChatSseEvent]:
    """把单个 SSE 帧解析为规整中间事件列表.

    阶段路由按 ``message.extra.step`` 判定: ``planning``
    段 content 为规划增量; ``tool_calling`` 段的 tool_return
    帧提取 ``additional_kwargs.extra_json.docs`` 作为引用
    切片 (可能多次出现, 每次都产出 references);
    ``generating`` 段 content 为回答增量; 尾帧携带 usage
    时产出 usage; finish_reason=stop 后补 done.

    Args:
        event: SSE 事件名, ``error`` 表示流内错误帧.
        data: 帧 data 原文 (JSON 字符串).

    Returns:
        本帧产生的事件列表, 空帧或不可解析帧返回空列表.
    """
    if event == 'error':
        return [
            ChatSseEvent(kind='error', payload=_error_text(data))
        ]
    if not data.strip():
        return []
    try:
        payload = json.loads(data)
    except ValueError:
        logger.debug('问答 SSE 帧 data 非 JSON, 已忽略')
        return []
    if not isinstance(payload, dict):
        return []
    events: list[ChatSseEvent] = []
    # 兜底: 顶层 code 非成功且无 output 时视为错误帧
    code = str(payload.get('code') or '')
    if code and code not in ('200', 'Success') \
            and payload.get('output') is None:
        text = str(payload.get('message') or code)
        request_id = str(payload.get('request_id') or '')
        if request_id:
            text = f'{text} (request_id={request_id})'
        return [ChatSseEvent(kind='error', payload=text)]
    output = payload.get('output')
    choices = (
        output.get('choices') if isinstance(output, dict)
        else None
    )
    choice = (
        choices[0]
        if isinstance(choices, list) and choices
        else None
    )
    message = (
        choice.get('message') if isinstance(choice, dict)
        else None
    )
    if not isinstance(message, dict):
        message = {}
    extra = message.get('extra')
    step = str(extra.get('step') or '') \
        if isinstance(extra, dict) else ''
    content = message.get('content')
    text = _content_text(content)
    if step == 'planning' and text:
        events.append(
            ChatSseEvent(kind='planning_delta', payload=text)
        )
    elif step == 'tool_calling':
        docs = _extract_tool_docs(message)
        if docs:
            events.append(
                ChatSseEvent(kind='references', payload=docs)
            )
    elif step == 'generating' and text:
        events.append(
            ChatSseEvent(kind='answer_delta', payload=text)
        )
    usage = payload.get('usage')
    if isinstance(usage, dict) and usage:
        events.append(
            ChatSseEvent(kind='usage', payload=usage)
        )
    finish_reason = str(choice.get('finish_reason') or '') \
        if isinstance(choice, dict) else ''
    if finish_reason == 'stop':
        events.append(ChatSseEvent(kind='done', payload=usage))
    return events


def _content_text(content: object) -> str:
    """宽容提取帧 content 文本 (协议类型为 string|array).

    多模态 array 形态拼接其中 ``{'type': 'text', 'text':
    ...}`` 项的 text, 非 dict 项与无 text 项跳过.

    Args:
        content: 帧内 message.content 原始值.

    Returns:
        提取到的文本; 无有效文本时返回空字符串.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            str(item.get('text'))
            for item in content
            if isinstance(item, dict)
            and item.get('type') == 'text'
            and item.get('text') is not None
        ]
        return ''.join(parts)
    return ''


def _extract_tool_docs(
    message: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """提取 tool_return 帧中的引用切片列表.

    切片位于 ``additional_kwargs.extra_json.docs``, 仅
    ``role=tool`` 的帧携带.

    Args:
        message: 帧内 choices[0].message 字典.

    Returns:
        引用切片原始字典列表, 无切片时为空列表.
    """
    if str(message.get('role') or '') != 'tool':
        return []
    kwargs = message.get('additional_kwargs')
    if not isinstance(kwargs, Mapping):
        return []
    extra_json = kwargs.get('extra_json')
    if not isinstance(extra_json, Mapping):
        return []
    docs = extra_json.get('docs')
    if not isinstance(docs, list):
        return []
    return [
        doc for doc in docs if isinstance(doc, dict)
    ]


def _error_text(data: str) -> str:
    """把 error 帧 data 归一为可读错误描述.

    Args:
        data: 错误帧 data 原文, 期望含 code / message /
            request_id 的 JSON.

    Returns:
        可读错误描述; JSON 解析失败时返回原文.
    """
    try:
        payload = json.loads(data)
    except ValueError:
        return data.strip() or '阿里云问答流内错误'
    if not isinstance(payload, dict):
        return str(payload)
    code = str(payload.get('code') or '')
    message = str(payload.get('message') or '')
    request_id = str(payload.get('request_id') or '')
    parts = [
        part for part in (code, message) if part
    ]
    text = ': '.join(parts) or data.strip() \
        or '阿里云问答流内错误'
    if request_id:
        text = f'{text} (request_id={request_id})'
    return text


class AliyunChatClient:
    """阿里云百炼知识问答 SSE 流式客户端.

    Attributes:
        _api_key: 百炼 API-Key, Bearer 鉴权.
        _workspace_id: 业务空间 ID, 嵌入 Host.
        _agent_id: 知识问答服务应用 ID (aid-xxx).
        _region_id: 服务地域, 用于拼接 Host.
        _timeout: 问答流读取超时秒数.
    """

    def __init__(
        self,
        api_key: str,
        workspace_id: str,
        agent_id: str,
        region_id: str = 'cn-beijing',
        timeout: float = 120.0,
    ) -> None:
        """初始化问答客户端.

        Args:
            api_key: 百炼 API-Key.
            workspace_id: 业务空间 ID.
            agent_id: 知识问答服务应用 ID (aid-xxx).
            region_id: 服务地域, 默认 cn-beijing.
            timeout: 读取超时秒数, 问答流专用, 默认 120,
                独立于管理 API 的 30 秒超时.
        """
        self._api_key = api_key.strip()
        self._workspace_id = workspace_id.strip()
        self._agent_id = agent_id.strip()
        self._region_id = region_id.strip() or 'cn-beijing'
        self._timeout = timeout

    def _chat_url(self) -> str:
        """拼接问答端点 URL, workspace_id 嵌入 Host."""
        host = (
            f'{self._workspace_id}.{self._region_id}'
            '.maas.aliyuncs.com'
        )
        return f'https://{host}/api/v2/apps/knowledge/chat'

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        session_files: Sequence[str] | None = None,
    ) -> AsyncIterator[ChatSseEvent]:
        """发起流式问答并产出规整中间事件.

        平台不保存会话状态, messages 需全量回传 (建议
        最近 10 轮). 取消支持: 原生异步, 调用方
        ``task.cancel()`` 后 async with 上下文自动关闭
        httpx 流.

        Args:
            messages: role/content 消息序列, role 仅
                user/assistant.
            session_files: 会话临时文件 ID 列表, 经 AddFile
                接口注册并解析完成的文件随本轮提问透传,
                为空时不携带.

        Yields:
            planning_delta / references / answer_delta /
            usage / error / done 事件.

        Raises:
            AliyunChatError: HTTP 非 2xx (401 InvalidApiKey
                等) 或请求体构造失败时抛出; 流内 error 帧
                不抛异常, 以 error 事件产出.
        """
        body = {
            'input': {
                'messages': [
                    {
                        'role': str(msg['role']),
                        'content': str(msg['content']),
                    }
                    for msg in messages
                ],
            },
            'parameters': {
                'agent_options': self._build_agent_options(
                    session_files=session_files,
                ),
            },
            'stream': True,
        }
        headers = {
            'Authorization': f'Bearer {self._api_key}',
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
        }
        timeout = httpx.Timeout(
            self._timeout, connect=10.0, write=10.0, pool=10.0
        )
        async with httpx.AsyncClient(
            http2=True, timeout=timeout
        ) as client, client.stream(
            'POST',
            self._chat_url(),
            headers=headers,
            json=body,
        ) as response:
            logger.debug(
                '阿里云问答 HTTP 请求发起 | url={} | agent_id={}',
                self._chat_url(), self._agent_id,
            )
            if response.status_code != 200:
                logger.error(
                    '阿里云问答 HTTP 错误 | status={}',
                    response.status_code,
                )
                raise await self._http_error(response)
            async for event in self._iter_events(response):
                yield event

    def _build_agent_options(
        self,
        *,
        session_files: Sequence[str] | None = None,
    ) -> dict:
        """构造 agent_options 请求参数.

        Args:
            session_files: 会话临时文件 ID 列表, 为空时
                不携带.

        Returns:
            agent_options 请求字典.
        """
        opts: dict = {'agent_id': self._agent_id}
        if session_files:
            opts['session_files'] = list(session_files)
        return opts

    @staticmethod
    async def _iter_events(
        response: httpx.Response,
    ) -> AsyncIterator[ChatSseEvent]:
        """消费响应行并按帧解析产出事件.

        Args:
            response: 已建立连接的流式响应.

        Yields:
            规整后的中间事件.
        """
        async for event, data in _line_frames(response):
            for item in interpret_frame(event, data):
                yield item

    @staticmethod
    async def _http_error(
        response: httpx.Response,
    ) -> AliyunChatError:
        """把 HTTP 非 2xx 响应归一为携带可读信息的异常.

        Args:
            response: 非 2xx 响应, 读取正文解析错误码.

        Returns:
            归一后的问答调用异常.
        """
        try:
            raw = await response.aread()
        except httpx.HTTPError:
            raw = b''
        code = ''
        message = ''
        request_id = ''
        try:
            payload = json.loads(raw.decode('utf-8', 'replace'))
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            code = str(payload.get('code') or '')
            message = str(payload.get('message') or '')
            request_id = str(payload.get('request_id') or '')
        status = response.status_code
        if status == 401:
            text = (
                '阿里云问答鉴权失败 (InvalidApiKey): '
                '百炼 API Key 无效或缺失, 请到平台配置页签'
                '的问答配置区检查'
            )
        else:
            text = f'阿里云问答请求失败 (HTTP {status})'
            if code or message:
                detail = ': '.join(
                    part for part in (code, message) if part
                )
                text = f'{text}: {detail}'
        if request_id:
            text = f'{text} (request_id={request_id})'
        return AliyunChatError(
            text,
            status_code=status,
            code=code or None,
            request_id=request_id or None,
        )


async def _line_frames(
    response: httpx.Response,
) -> AsyncIterator[tuple[str, str]]:
    """把流式响应的行异步切分为 SSE 帧.

    Args:
        response: 已建立连接的流式响应.

    Yields:
        (事件名, data 原文) 二元组.
    """
    assembler = SseFrameAssembler()
    async for line in response.aiter_lines():
        frame = assembler.feed(line)
        if frame is not None:
            yield frame
    frame = assembler.flush()
    if frame is not None:
        yield frame
