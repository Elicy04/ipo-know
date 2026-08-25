"""实时日志面板组件.

将 loguru 日志流桥接到 NiceGUI ``ui.log`` 组件,
实现 GUI 内嵌的实时日志展示, 并按日志级别着色.
"""

import asyncio
from typing import TypedDict

from loguru import logger
from nicegui import ui


class LogEntry(TypedDict):
    """结构化日志条目, 由 sink 捕获后入队.

    Attributes:
        time: 时间戳文本, 格式为 ``HH:MM:SS``.
        level: 日志级别名, 如 ``INFO`` / ``ERROR``.
        message: 日志正文.
    """

    time: str
    level: str
    message: str


# 各级别对应的着色 (十六进制颜色值).
_LEVEL_COLORS: dict[str, str] = {
    'ERROR': '#ff6b6b',
    'CRITICAL': '#ff6b6b',
    'WARNING': '#ffb02e',
    'INFO': '#e0e0e0',
}
# DEBUG 及未知级别的默认着色.
_DEFAULT_COLOR = '#9e9e9e'
# 时间戳着色, 与正文区分.
_TIME_COLOR = '#808080'
# 行内分段样式: label 默认为 div, 需改为行内并保留空格.
_INLINE_STYLE = 'display: inline; white-space: pre-wrap'
# 允许鼠标选中文本: NiceGUI 页面默认禁用文本选择,
# 需在日志容器/行/label 各级显式覆盖 (含 !important 防继承).
_SELECT_STYLE = 'user-select: text !important'


class LogPanel:
    """实时日志面板, 将 loguru sink 桥接到 NiceGUI ui.log.

    通过 asyncio.Queue 缓存结构化日志条目, 由 ui.timer 定时
    批量推送到前端, 避免高频 UI 更新; 每条日志按级别着色,
    时间戳以淡灰色区分. 顶部工具行提供"清空日志"按钮,
    日志文本支持鼠标选中复制.

    Attributes:
        _queue: 结构化日志条目缓冲队列.
        _sink_id: 当前注册的 loguru sink ID, None 表示未注册.
        _log: NiceGUI ui.log 组件实例.
    """

    def __init__(self) -> None:
        """初始化日志面板, 创建 UI 组件并启动刷新定时器.

        根容器填满所在页签内容区 (h-full): 顶部工具行
        固定高度 (shrink-0), 日志滚动区 flex-1 填满剩余
        高度并内部滚动 (覆盖 nicegui-log 默认 16rem).
        """
        self._queue: asyncio.Queue[LogEntry] = asyncio.Queue()
        self._sink_id: int | None = None
        with ui.column().classes('w-full h-full gap-2'):
            with ui.row().classes(
                'w-full shrink-0 items-center '
                'justify-between gap-2'
            ):
                ui.label('运行日志').classes(
                    'text-base font-medium'
                )
                ui.button(
                    icon='delete',
                    on_click=self.clear,
                ).props('dense flat').classes('text-xs')
            self._log = (
                ui.log(max_lines=500)
                .classes('w-full flex-1 min-h-0 select-text')
                .style(_SELECT_STYLE)
            )
        ui.timer(0.1, self._flush)

    def _sink(self, message: object) -> None:
        """Loguru sink 回调, 将结构化条目压入队列.

        Args:
            message: loguru 格式化的日志消息对象,
                其 ``record`` 属性携带级别与时间信息.
        """
        record = getattr(message, 'record', None)
        if record is None:
            level = 'INFO'
            time_text = ''
        else:
            level = record['level'].name
            time_text = record['time'].strftime('%H:%M:%S')
        self._queue.put_nowait(
            LogEntry(
                time=time_text,
                level=level,
                message=str(message).rstrip(),
            )
        )

    async def _flush(self) -> None:
        """将队列中的日志条目批量推送到 ui.log 组件."""
        while not self._queue.empty():
            self._render(self._queue.get_nowait())

    def _render(self, entry: LogEntry) -> None:
        """渲染单条日志, 按级别着色并分段展示.

        在 ui.log 内构建单行容器, 时间戳/级别/正文分段着色,
        并复刻 push 的 max_lines 裁剪逻辑.

        Args:
            entry: 待渲染的结构化日志条目.
        """
        color = _LEVEL_COLORS.get(entry['level'], _DEFAULT_COLOR)
        separator = ' | '
        with self._log:
            line = ui.element('div').style(
                f'color: {color}; white-space: pre-wrap; {_SELECT_STYLE}'
            )
            with line:
                if entry['time']:
                    ui.label(entry['time'] + separator).style(
                        f'color: {_TIME_COLOR}; '
                        f'{_INLINE_STYLE}; {_SELECT_STYLE}'
                    )
                ui.label(f'{entry["level"]:<8}' + separator).style(
                    f'color: {color}; '
                    f'{_INLINE_STYLE}; {_SELECT_STYLE}'
                )
                ui.label(entry['message']).style(
                    f'color: {color}; '
                    f'{_INLINE_STYLE}; {_SELECT_STYLE}'
                )
        max_lines = self._log.max_lines
        children = self._log.default_slot.children
        while max_lines is not None and len(children) > max_lines:
            self._log.remove(0)

    def clear(self) -> None:
        """清空日志展示与未刷新缓冲.

        调用 ui.log 的 ``clear()`` 移除所有子元素
        (含自建行容器), 并排空内部队列中尚未渲染的
        日志条目, 防止清空后旧消息被定时器重新刷出.
        """
        self._log.clear()
        while not self._queue.empty():
            self._queue.get_nowait()

    def start_capture(self) -> None:
        """注册 loguru sink 开始捕获日志."""
        if self._sink_id is None:
            self._sink_id = logger.add(
                self._sink,
                level='INFO',
                format='{message}',
            )

    def stop_capture(self) -> None:
        """移除 loguru sink 停止捕获日志."""
        if self._sink_id is not None:
            logger.remove(self._sink_id)
            self._sink_id = None
