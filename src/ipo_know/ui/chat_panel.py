"""知识问答面板.

提供基于知识库的流式问答: 会话历史 GUI 侧维护 (平台不
保存状态, 请求时全量回传), 回答经 markdown 流式渲染
(timer 节流批量 flush), 支持停止生成、清空对话与平台切换
自动重置.

视觉为现代 AI 对话窗口风格: 会话区居中限宽, 用户消息为
右对齐圆角气泡, AI 消息为头像 + 全宽无框内容区, 消息行
由 row/column 自绘 (q-chat-message 样式钩子受限, 已核验
.venv 源码); markdown 正文经 Tailwind 任意变体约束标题/
列表/代码块/表格/引用排版; 消息滚动区禁用水平滚动
(overflow-x-hidden, 代码块内部仍可水平滚动).
"""

import asyncio
import threading
from collections import deque

import httpx
from loguru import logger
from nicegui import background_tasks
from nicegui import ui
from nicegui.events import ScrollEventArguments

from ipo_know.kb_query import SearchHit
from ipo_know.kb_query import create_query_backend
from ipo_know.ui.config_store import GUIConfigStore
from ipo_know.ui.log_panel import LogPanel
from ipo_know.ui.panel_helpers import error_summary
from ipo_know.ui.panel_helpers import safe_notify
from ipo_know.ui.platform import PLATFORM_OPTIONS
from ipo_know.ui.platform import missing_config_items


# 会话历史上限条数 (user + assistant 各计一条).
# 该上限即请求保留条数: 请求时会话历史全量回传, 无需裁剪.
_HISTORY_MAX_LENGTH = 20

# 提问文本长度上限 (字符).
_QUERY_MAX_LENGTH = 8000

# 流式渲染节流间隔 (秒): 每 tick 对 markdown 做一次原地更新.
_FLUSH_INTERVAL = 0.15

# 回答/思考累积字数上限, 超过后退化为纯文本 label 更新,
# 避免超长 markdown 反复重渲染卡顿 (正文与思考共用).
_PLAINTEXT_FALLBACK_LIMIT = 20000

# 引用区最多展示条数.
_REFERENCES_LIMIT = 10

# 智能跟随滚动的距底阈值 (像素): 用户上滑超过该距离后
# 停止自动拉底, 避免抢滚动.
_SCROLL_FOLLOW_BOTTOM_GAP = 120.0

# 智能跟随滚动的近底百分比容忍: 内容增长使缓存距底值
# 失真时, 末次事件百分比足够高仍视为在底部附近.
_SCROLL_FOLLOW_PERCENT = 0.99

# 会话区居中最大宽度 (现代对话界面惯例约 768px).
_CONTENT_MAX_WIDTH = 'max-w-3xl'

# 现代对话排版: markdown 正文样式. nicegui-markdown 把
# innerHTML 直接渲染在组件元素上 (已核验 .venv 源码),
# 经 Tailwind 任意变体选择器约束内部标题/段落/列表/
# 代码/表格/引用; 行内代码与代码块分别约束, pre 内 code
# 以 [_pre_code] 覆盖回透明底.
_MARKDOWN_CLASSES = (
    'w-full text-[15px] leading-7 '
    '[&_h1]:text-xl [&_h1]:font-bold [&_h1]:mt-5 [&_h1]:mb-2 '
    '[&_h2]:text-lg [&_h2]:font-semibold '
    '[&_h2]:mt-4 [&_h2]:mb-2 '
    '[&_h3]:text-base [&_h3]:font-semibold '
    '[&_h3]:mt-3 [&_h3]:mb-1 '
    '[&_p]:my-2 [&_p]:leading-7 '
    '[&_ul]:list-disc [&_ul]:pl-5 [&_ul]:my-2 '
    '[&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:my-2 '
    '[&_li]:my-1 '
    '[&_a]:text-sky-400 [&_a]:underline '
    '[&_blockquote]:border-l-4 '
    '[&_blockquote]:border-gray-600 [&_blockquote]:pl-3 '
    '[&_blockquote]:my-2 [&_blockquote]:text-gray-400 '
    '[&_code]:bg-gray-700/60 [&_code]:text-pink-300 '
    '[&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded '
    '[&_code]:text-[0.875em] [&_code]:font-mono '
    '[&_pre]:bg-[#0d1117] [&_pre]:text-gray-100 '
    '[&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:my-3 '
    '[&_pre]:overflow-x-auto [&_pre]:text-sm '
    '[&_pre]:leading-6 '
    '[&_pre_code]:bg-transparent [&_pre_code]:p-0 '
    '[&_pre_code]:text-inherit '
    '[&_table]:border-collapse [&_table]:w-full '
    '[&_table]:my-3 [&_table]:text-sm '
    '[&_th]:border [&_th]:border-gray-600 '
    '[&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-gray-800/60 '
    '[&_td]:border [&_td]:border-gray-700 '
    '[&_td]:px-3 [&_td]:py-1.5 '
)

# 思考区内容排版: 低调小字浅灰, 不抢正文视觉.
_THINKING_MD_CLASSES = (
    'w-full text-xs text-gray-500 leading-5 '
    '[&_p]:my-1 [&_ul]:pl-4 [&_ol]:pl-4 '
)


class ChatPanel:
    """知识问答面板 (现代 AI 对话窗口风格).

    Attributes:
        _store: GUI 配置持久化存储实例.
        _log_panel: 日志面板实例, 可为 None.
        _platform: 当前目标平台标识 (aliyun/volc).
        _running: 问答后台任务是否进行中.
        _run_id: 问答代次号: 每次发送/重置递增, 后台任务
            持有发起时快照, 过期代次的残余渲染一律丢弃,
            防止旧任务写入新会话气泡.
        _history: 会话历史 (role/content 字典双端队列).
        _stop_event: 当前生成任务的停止标志.
        _task: 当前问答后台任务句柄.
        _buffer: 当前回答累积文本.
        _flushed_length: 已渲染到气泡的文本长度.
        _degraded: 当前回答是否已退化纯文本渲染.
        _thinking_buffer: 当前思考过程累积文本 (仅展示,
            不入会话历史).
        _thinking_flushed_length: 已渲染到思考区的文本长度.
        _thinking_degraded: 思考区是否已退化纯文本渲染.
        _thinking_expansion: 思考区可折叠容器 (懒创建).
        _thinking_md: 思考区内 markdown 组件引用.
        _thinking_label: 思考区退化模式纯文本 label 引用.
        _references_expansion: 引用来源折叠区 (懒创建,
            位于内容区顶部, 槽位恒为 0).
        _references_count: 引用来源累计接收条数 (多批
            tool_return 合并计数, 展示于折叠区标题).
        _references_shown: 引用来源已展示条数 (展示上限
            内实际渲染的条数).
        _scroll_top_offset: 末次滚动事件的距底像素缓存.
        _scroll_bottom_percent: 末次滚动事件的滚动百分比缓存.
        _scroll_event_seen: 是否已收到过滚动事件.
        _current_bubble: 当前 AI 回答内容区列容器
            (引用/思考/正文/stamp 的挂载与槽位单元).
        _current_md: 内容区内 markdown 组件引用.
        _current_label: 退化模式下的纯文本 label 引用.
        _usage: 本次回答的 token 用量 (尾流回传).
        _chat_supported: 当前平台问答能力位缓存.
        _empty_state: 空会话欢迎区, 有消息时隐藏.
        _container: 面板根容器, 供后台任务恢复 UI 上下文.
    """

    def __init__(
        self,
        config_store: GUIConfigStore,
        log_panel: LogPanel | None = None,
    ) -> None:
        """初始化问答面板.

        Args:
            config_store: 配置持久化存储实例.
            log_panel: 日志面板实例, 用于启动日志捕获.
        """
        self._store = config_store
        self._log_panel = log_panel
        self._platform: str = 'aliyun'
        self._running: bool = False
        self._run_id: int = 0
        self._history: deque[dict[str, str]] = deque(
            maxlen=_HISTORY_MAX_LENGTH
        )
        self._stop_event: threading.Event | None = None
        self._task: asyncio.Task | None = None
        self._buffer: str = ''
        self._flushed_length: int = 0
        self._degraded: bool = False
        self._thinking_buffer: str = ''
        self._thinking_flushed_length: int = 0
        self._thinking_degraded: bool = False
        self._thinking_expansion: ui.expansion | None = None
        self._thinking_md: ui.markdown | None = None
        self._thinking_label: ui.label | None = None
        self._references_expansion: ui.expansion | None = None
        self._references_count: int = 0
        self._references_shown: int = 0
        self._scroll_top_offset: float = 0.0
        self._scroll_bottom_percent: float = 1.0
        self._scroll_event_seen: bool = False
        self._usage: object = None
        self._current_bubble: ui.column | None = None
        self._current_md: ui.markdown | None = None
        self._current_label: ui.label | None = None
        self._query_input: ui.textarea | None = None
        self._btn_send: ui.button | None = None
        self._btn_stop: ui.button | None = None
        self._messages_col: ui.column | None = None
        self._scroll_area: ui.scroll_area | None = None
        self._empty_state: ui.column | None = None
        self._flush_timer: ui.timer | None = None
        self._container: ui.column | None = None
        # 平台问答能力位缓存 (None 表示尚未探测),
        # set_platform 时刷新, 仅变化时重建 tooltip 避免泄漏
        self._chat_supported: bool | None = None
        self._build_ui()
        self._refresh_chat_support()

    # --------------------------------------------------
    # 公开接口
    # --------------------------------------------------
    def set_platform(self, platform: str) -> None:
        """切换目标平台: 停止生成并清空会话与消息区.

        不同平台对应不同知识库, 混用历史会误导问答,
        故切换即重置.

        Args:
            platform: 平台标识 (aliyun/volc).
        """
        if platform == self._platform:
            return
        self._platform = platform
        self._refresh_chat_support()
        self._stop_generation()
        self._reset_conversation()
        platform_name = PLATFORM_OPTIONS.get(platform, platform)
        safe_notify(
            self._container,
            f'知识问答已切换到 {platform_name}, 会话已重置',
            type='info',
        )

    def _refresh_chat_support(self) -> None:
        """按当前平台刷新问答能力位缓存.

        以查询后端 ``supports_chat`` 能力位为准; 后端构造
        失败 (配置缺失等) 时保守置 False, 发送前置校验兜底.
        能力位变化时同步重建发送按钮 tooltip (避免重复
        挂载泄漏).
        """
        try:
            backend = create_query_backend(
                self._platform, self._store
            )
            supported = bool(backend.supports_chat)
        except Exception:
            logger.debug('问答能力位探测失败, 按不支持处理')
            supported = False
        if supported == self._chat_supported:
            return
        self._chat_supported = supported
        if self._btn_send is not None:
            if supported:
                self._btn_send.tooltip('发送提问')
            else:
                self._btn_send.tooltip(
                    '当前平台问答能力不可用'
                )

    # --------------------------------------------------
    # UI 构建
    # --------------------------------------------------
    def _build_ui(self) -> None:
        """构建问答面板 UI 布局 (现代对话窗口风格)."""
        container = ui.column().classes('w-full h-full gap-0')
        self._container = container
        with container:
            # 顶栏: 弱化的清空对话小图标 (右上角)
            with ui.row().classes('w-full items-center'):
                ui.label('知识问答').classes(
                    'text-sm font-medium text-gray-400'
                )
                ui.button(
                    icon='delete_sweep',
                    on_click=self._on_clear,
                ).props(
                    'flat round dense'
                ).classes(
                    'ml-auto text-gray-400'
                ).tooltip('清空对话')

            # 会话区：占满页签剩余高度，内容居中限宽；
            # overflow-x-hidden 禁用水平滚动 (q-scroll-area
            # 无专用 prop, CSS 覆盖最简洁; 代码块内部
            # 水平滚动由 _MARKDOWN_CLASSES 中 pre 的
            # overflow-x-auto 独立控制, 不受此处影响)
            self._scroll_area = ui.scroll_area(
                on_scroll=self._handle_scroll,
            ).classes('w-full flex-1 overflow-x-hidden')
            with self._scroll_area, ui.column().classes(
                f'w-full {_CONTENT_MAX_WIDTH} mx-auto '
                'gap-6 px-4 py-6'
            ):
                self._build_empty_state()
                self._messages_col = ui.column().classes(
                    'w-full gap-6'
                )

            # 输入区: 细线分隔 + 圆角大输入框 + 圆形按钮
            ui.separator().classes('w-full opacity-30')
            with ui.row().classes(
                'w-full items-end gap-2 pt-3'
            ):
                with ui.column().classes(
                    'flex-1 rounded-2xl border '
                    'border-gray-600/50 bg-white/5 px-4 py-1'
                ):
                    self._query_input = ui.textarea(
                        placeholder=(
                            '向知识库提问 '
                            f'(不超过 {_QUERY_MAX_LENGTH} 字)'
                        ),
                    ).props(
                        'autogrow borderless dense'
                    ).classes('w-full')
                # 停止与发送同位: 运行中显示停止图标,
                # 空闲显示发送图标
                self._btn_stop = ui.button(
                    icon='stop',
                    on_click=self._on_stop,
                ).props('round').classes('text-gray-300')
                self._btn_stop.tooltip('停止生成')
                self._btn_send = ui.button(
                    icon='send',
                    on_click=self._on_send,
                ).props('round').classes(
                    'bg-blue-600 text-white'
                )
            self._btn_stop.visible = False

        # 流式渲染节流定时器: 有增量时激活, 空闲时停用
        self._flush_timer = ui.timer(
            _FLUSH_INTERVAL, self._flush, active=False
        )
        # 定时刷新发送/停止按钮状态
        ui.timer(0.5, self._refresh_btn_state)

    def _build_empty_state(self) -> None:
        """构建空会话欢迎区: 居中引导文案."""
        empty = ui.column().classes(
            'w-full items-center gap-3 py-20'
        )
        self._empty_state = empty
        with empty:
            ui.icon('smart_toy', size='44px').classes(
                'text-gray-600'
            )
            ui.label('向知识库提问, 开始对话').classes(
                'text-base text-gray-300'
            )
            ui.label(
                '基于所选平台知识库的检索增强问答, '
                '回答附带引用来源'
            ).classes('text-xs text-gray-500')

    # --------------------------------------------------
    # 发送与停止
    # --------------------------------------------------
    def _on_send(self) -> None:
        """发送按钮回调: 校验后启动流式问答后台任务."""
        # 段一: 防重入
        if self._running:
            return
        # 段二: 快照当前输入与平台
        query = str(self._query_input.value or '').strip() \
            if self._query_input is not None else ''
        platform = self._platform
        # 段三: 校验
        if not query:
            logger.warning(
                '问答前置校验失败 | platform={} '
                '| reason=空提问',
                platform,
            )
            safe_notify(
                self._container, '请输入提问内容', type='warning'
            )
            return
        if len(query) > _QUERY_MAX_LENGTH:
            logger.warning(
                '问答前置校验失败 | platform={} '
                '| reason=提问过长',
                platform,
            )
            safe_notify(
                self._container,
                f'提问内容过长, 请不超过 {_QUERY_MAX_LENGTH} 字',
                type='warning',
            )
            return
        missing = missing_config_items(self._store, platform)
        if missing:
            logger.warning(
                '问答前置校验失败 | platform={} '
                '| reason=缺少配置项: {}',
                platform, ', '.join(missing),
            )
            safe_notify(
                self._container,
                '请先填写必要配置项: ' + ', '.join(missing),
                type='warning',
            )
            return
        if platform == 'volc':
            data = self._store.load()
            raw = data.get('viking_knowledge', {})
            volc_data = raw if isinstance(raw, dict) else {}
            service_id = str(
                volc_data.get('service_resource_id') or ''
            ).strip()
            if not service_id:
                logger.warning(
                    '问答前置校验失败 | platform=volc '
                    '| reason=缺少 service_resource_id',
                )
                safe_notify(
                    self._container,
                    '火山问答需要知识服务 ID, '
                    '请到平台配置页签的问答配置区填写',
                    type='warning',
                )
                return
            api_key = str(
                volc_data.get('api_key') or ''
            ).strip()
            if not api_key:
                logger.warning(
                    '问答前置校验失败 | platform=volc '
                    '| reason=缺少 api_key',
                )
                safe_notify(
                    self._container,
                    '火山问答需要 API Key, '
                    '请到平台配置页签的问答配置区填写',
                    type='warning',
                )
                return
        if platform == 'aliyun':
            data = self._store.load()
            raw = data.get('aliyun_knowledge', {})
            ak_data = raw if isinstance(raw, dict) else {}
            api_key = str(
                ak_data.get('api_key') or ''
            ).strip()
            if not api_key:
                logger.warning(
                    '问答前置校验失败 | platform=aliyun '
                    '| reason=缺少 api_key',
                )
                safe_notify(
                    self._container,
                    '阿里云问答需要 API Key, '
                    '请到平台配置页签的问答配置区填写',
                    type='warning',
                )
                return
            agent_id = str(
                ak_data.get('agent_id') or ''
            ).strip()
            if not agent_id:
                logger.warning(
                    '问答前置校验失败 | platform=aliyun '
                    '| reason=缺少 agent_id',
                )
                safe_notify(
                    self._container,
                    '阿里云问答需要知识问答服务 ID, '
                    '请到平台配置页签的问答配置区填写',
                    type='warning',
                )
                return
        # 会话历史全量回传 (历史上限即请求保留条数) + 本次提问
        messages: list[dict[str, str]] = list(self._history)
        messages.append({'role': 'user', 'content': query})
        self._prepare_bubbles(query)
        # 段四: 启动后台任务 (代次号先递增, 任务持快照)
        self._running = True
        self._stop_event = threading.Event()
        self._run_id += 1
        # 段五: try-finally 由后台协程承担
        self._task = background_tasks.create(
            self._run_chat(query, platform, messages),
            name='kb chat',
        )

    def _on_stop(self) -> None:
        """停止生成按钮回调: 置停止标志并取消后台任务."""
        self._stop_generation()

    def _stop_generation(self) -> None:
        """置位停止标志并取消当前问答任务 (幂等)."""
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()

    def _on_clear(self) -> None:
        """清空对话按钮回调: 重置历史与消息区."""
        self._stop_generation()
        self._reset_conversation()
        safe_notify(
            self._container, '对话已清空', type='info'
        )

    def _reset_conversation(self) -> None:
        """重置会话历史、消息区与当前气泡引用.

        代次号递增使在途旧任务的残余渲染全部失效; 空状态
        欢迎区恢复可见.
        """
        self._run_id += 1
        self._history.clear()
        if self._messages_col is not None:
            self._messages_col.clear()
        if self._empty_state is not None:
            self._empty_state.visible = True
        self._current_bubble = None
        self._current_md = None
        self._current_label = None
        self._thinking_expansion = None
        self._thinking_md = None
        self._thinking_label = None
        self._references_expansion = None
        self._references_count = 0
        self._references_shown = 0
        self._scroll_top_offset = 0.0
        self._scroll_bottom_percent = 1.0
        self._scroll_event_seen = False
        self._buffer = ''
        self._flushed_length = 0
        self._degraded = False
        self._thinking_buffer = ''
        self._thinking_flushed_length = 0
        self._thinking_degraded = False
        self._usage = None
        if self._flush_timer is not None:
            self._flush_timer.deactivate()

    # --------------------------------------------------
    # 消息行准备
    # --------------------------------------------------
    def _prepare_bubbles(self, query: str) -> None:
        """渲染用户消息行并创建空的 AI 回答消息行.

        用户消息为右对齐圆角气泡; AI 消息为头像 + 全宽
        无框内容区, 内容区列容器内嵌单个 markdown 组件
        持有引用, 供流式 flush 原地更新.

        Args:
            query: 用户提问文本.
        """
        if self._messages_col is None:
            return
        if self._empty_state is not None:
            self._empty_state.visible = False
        with self._messages_col:
            # 用户消息: 右对齐圆角气泡, 文字左对齐于气泡内
            with ui.row().classes('w-full justify-end'):
                ui.label(query).classes(
                    'max-w-[80%] whitespace-pre-wrap '
                    'rounded-2xl rounded-br-md bg-blue-600 '
                    'px-4 py-2.5 text-sm leading-6 text-white'
                )
            # AI 消息: 头像 + 标识 + 全宽内容区 (无边框底色)
            with ui.row().classes(
                'w-full items-start gap-3'
            ):
                with ui.column().classes(
                    'mt-0.5 h-8 w-8 flex-shrink-0 '
                    'items-center justify-center rounded-full '
                    'bg-indigo-500/15'
                ):
                    ui.icon('smart_toy').classes(
                        'text-indigo-400'
                    )
                with ui.column().classes(
                    'min-w-0 flex-1 gap-2'
                ):
                    ui.label('AI 助手').classes(
                        'text-xs text-gray-500'
                    )
                    bubble = ui.column().classes('w-full gap-2')
                    with bubble:
                        markdown = ui.markdown('').classes(
                            _MARKDOWN_CLASSES
                        )
        self._current_bubble = bubble
        self._current_md = markdown
        self._current_label = None
        # 思考区懒创建: 首个 reasoning_delta 到达时才建,
        # 非推理模型不产生多余组件
        self._thinking_expansion = None
        self._thinking_md = None
        self._thinking_label = None
        self._references_expansion = None
        self._references_count = 0
        self._references_shown = 0
        self._buffer = ''
        self._flushed_length = 0
        self._degraded = False
        self._thinking_buffer = ''
        self._thinking_flushed_length = 0
        self._thinking_degraded = False
        self._usage = None
        self._scroll_to_bottom()

    # --------------------------------------------------
    # 流式问答后台任务
    # --------------------------------------------------
    async def _run_chat(
        self,
        query: str,
        platform: str,
        messages: list[dict[str, str]],
    ) -> None:
        """后台消费问答事件流并驱动消息渲染.

        全程持发起时的代次号快照: 会话被清空/平台切换/
        新一轮提问后, 旧代次任务的一切渲染与状态回写均
        静默丢弃, 防止污染新会话.

        Args:
            query: 用户提问文本快照.
            platform: 目标平台标识快照.
            messages: 全量回传的消息序列快照.
        """
        run_id = self._run_id
        logger.info(
            '发起知识问答 | platform={} | messages={}轮 '
            '| query_len={}',
            platform, len(messages), len(query),
        )
        if self._log_panel is not None:
            self._log_panel.start_capture()
        try:
            backend = create_query_backend(platform, self._store)
            stream = backend.stream_chat(
                messages, stop_event=self._stop_event
            )
            first_event_seen = False
            async for event in stream:
                if run_id != self._run_id:
                    return
                if not first_event_seen:
                    first_event_seen = True
                    logger.info(
                        '问答首帧到达 | platform={} | kind={}',
                        platform, event.kind,
                    )
                if event.kind == 'answer_delta':
                    if not self._buffer:
                        # 首个回答增量: 思考区自动折叠
                        # (流结束后仍可手动展开查看)
                        self._collapse_thinking()
                    self._buffer += str(event.payload or '')
                    if self._flush_timer is not None:
                        self._flush_timer.activate()
                elif event.kind == 'reasoning_delta':
                    self._ensure_thinking_area()
                    self._thinking_buffer += str(
                        event.payload or ''
                    )
                    if self._flush_timer is not None:
                        self._flush_timer.activate()
                elif event.kind == 'references':
                    self._render_references(event.payload or [])
                elif event.kind == 'usage':
                    self._usage = event.payload
                elif event.kind == 'done':
                    # 流正常结束: 思考区保持折叠 (可手动展开)
                    self._collapse_thinking()
                elif event.kind == 'error':
                    raise RuntimeError(str(event.payload))
            if run_id != self._run_id:
                return
            # 竞态兜底: 停止标志已置位但流经残余帧自然结束,
            # CancelledError 未到达时, 强制走停止分支收尾
            if (
                self._stop_event is not None
                and self._stop_event.is_set()
            ):
                raise asyncio.CancelledError
            # 正常结束: flush 残余, 写 stamp, 追加历史
            self._flush()
            if self._usage:
                logger.info(
                    '知识问答完成 | platform={} | answer_len={} '
                    '| usage={}',
                    platform,
                    len(self._buffer),
                    self._usage,
                )
            else:
                logger.info(
                    '知识问答完成 | platform={} | answer_len={}',
                    platform, len(self._buffer),
                )
            self._finish_bubble(stopped=False)
            # 空回答不入历史: 避免空 content 全量回传给
            # 平台 API 误导后续轮次
            if self._buffer:
                self._history.append(
                    {'role': 'user', 'content': query}
                )
                self._history.append(
                    {'role': 'assistant', 'content': self._buffer}
                )
        except asyncio.CancelledError:
            # 用户点击"停止生成" (含竞态兜底强制转入):
            # flush 残余并标记已停止, 不追加会话历史,
            # 避免截断回答在后续轮次全量回传误导问答;
            # 已收到的思考内容保留在折叠的思考区内
            if run_id != self._run_id:
                return
            logger.info(
                '知识问答被用户取消 | platform={} '
                '| answered_len={}',
                platform, len(self._buffer),
            )
            self._flush()
            self._collapse_thinking()
            self._finish_bubble(stopped=True)
        except Exception as exc:
            if run_id != self._run_id:
                return
            if isinstance(
                exc,
                (httpx.ReadTimeout, httpx.ConnectTimeout,
                 asyncio.TimeoutError),
            ):
                logger.error(
                    '知识问答超时 | platform={}',
                    platform,
                )
            logger.exception('知识问答执行失败')
            self._flush()
            self._mark_bubble_failed(error_summary(exc))
            safe_notify(
                self._container,
                f'问答失败: {error_summary(exc)}',
                type='negative',
            )
        finally:
            # 过期代次不回写运行状态, 避免清掉新任务标志
            if run_id == self._run_id:
                self._running = False
                self._stop_event = None
                self._task = None
                if self._flush_timer is not None:
                    self._flush_timer.deactivate()

    # --------------------------------------------------
    # 流式渲染
    # --------------------------------------------------
    def _ensure_thinking_area(self) -> None:
        """懒创建可折叠"思考过程"区 (幂等).

        首个 reasoning_delta 到达时在当前 AI 内容区内、
        正文 markdown 之上创建: ``ui.expansion`` 构造参数
        ``value=True`` 默认展开 (已核验 .venv 源码);
        收敛为低调折叠条: 小字浅灰标题, 内容小字号浅灰,
        不抢正文视觉.
        """
        if (
            self._thinking_expansion is not None
            or self._current_bubble is None
        ):
            return
        bubble = self._current_bubble
        with bubble:
            expansion = ui.expansion(
                '思考过程', icon='psychology', value=True
            ).props('dense').classes(
                'w-full text-xs text-gray-500'
            )
            with expansion:
                thinking_md = ui.markdown('').classes(
                    _THINKING_MD_CLASSES
                )
        # 正文 markdown 先创建, 将思考区移动到内容区前缀位:
        # 引用区未建时占槽位 0, 已建时让位到引用之后,
        # 保证顺序恒为 引用来源 → 思考 → 正文 (流式正文
        # 始终位于底部, 与自动滚动锚点一致)
        slot = 1 if self._references_expansion is not None else 0
        expansion.move(bubble, slot)
        self._thinking_expansion = expansion
        self._thinking_md = thinking_md
        self._scroll_to_bottom()

    def _collapse_thinking(self) -> None:
        """折叠思考区 (幂等).

        编程折叠用 ``Expansion.close()`` 置 value=False
        (已核验 .venv 源码), 用户事后仍可手动展开.
        """
        if self._thinking_expansion is not None:
            self._thinking_expansion.close()

    def _flush(self) -> None:
        """把累积的思考/回答增量批量渲染到消息区.

        正文与思考共用同一 flush timer: 每 tick 分别对两处
        markdown 做一次原地更新 (set_content 全文); 两者均
        无新增量时停用定时器; 任一累积超过
        ``_PLAINTEXT_FALLBACK_LIMIT`` 字各自退化为纯文本
        label.
        """
        if self._current_bubble is None:
            return
        self._flush_thinking()
        if len(self._buffer) != self._flushed_length:
            if (
                not self._degraded
                and len(self._buffer) > _PLAINTEXT_FALLBACK_LIMIT
            ):
                self._degrade_to_plain_text()
            if self._degraded:
                if self._current_label is not None:
                    self._current_label.text = self._buffer
            elif self._current_md is not None:
                self._current_md.set_content(self._buffer)
            self._flushed_length = len(self._buffer)
            self._scroll_to_bottom()
        if (
            len(self._buffer) == self._flushed_length
            and len(self._thinking_buffer)
            == self._thinking_flushed_length
            and self._flush_timer is not None
        ):
            self._flush_timer.deactivate()

    def _flush_thinking(self) -> None:
        """把思考累积原地更新到思考区 markdown.

        无新增量时直接返回; 超过
        ``_PLAINTEXT_FALLBACK_LIMIT`` 字退化为纯文本 label.
        """
        if (
            self._thinking_expansion is None
            or len(self._thinking_buffer)
            == self._thinking_flushed_length
        ):
            return
        if (
            not self._thinking_degraded
            and len(self._thinking_buffer)
            > _PLAINTEXT_FALLBACK_LIMIT
        ):
            self._degrade_thinking_to_plain_text()
        if self._thinking_degraded:
            if self._thinking_label is not None:
                self._thinking_label.text = self._thinking_buffer
        elif self._thinking_md is not None:
            self._thinking_md.set_content(self._thinking_buffer)
        self._thinking_flushed_length = len(self._thinking_buffer)

    def _degrade_thinking_to_plain_text(self) -> None:
        """超长思考内容退化为纯文本 label 渲染.

        先在思考区内追加 label, 再移除 markdown 组件,
        避免内容闪空.
        """
        expansion = self._thinking_expansion
        if expansion is None:
            return
        with expansion:
            label = ui.label(self._thinking_buffer).classes(
                'w-full whitespace-pre-wrap '
                'text-xs leading-5 text-gray-500'
            )
        if self._thinking_md is not None:
            self._thinking_md.delete()
            self._thinking_md = None
        self._thinking_label = label
        self._thinking_degraded = True
        logger.warning(
            '思考内容超过 {} 字, 已退化为纯文本渲染',
            _PLAINTEXT_FALLBACK_LIMIT,
        )

    def _degrade_to_plain_text(self) -> None:
        """超长回答退化为纯文本 label 渲染.

        先在内容区内追加 label, 再移除 markdown 组件,
        避免内容闪空.
        """
        bubble = self._current_bubble
        if bubble is None:
            return
        with bubble:
            label = ui.label(self._buffer).classes(
                'w-full whitespace-pre-wrap '
                'text-[15px] leading-7'
            )
        if self._current_md is not None:
            self._current_md.delete()
            self._current_md = None
        self._current_label = label
        self._degraded = True
        logger.warning(
            '回答超过 {} 字, 已退化为纯文本渲染',
            _PLAINTEXT_FALLBACK_LIMIT,
        )

    def _render_references(self, hits: list[SearchHit]) -> None:
        """在当前内容区顶部渲染默认折叠的引用来源区.

        多批 tool_return 合并进同一折叠区 (标题累计总数,
        条目按展示上限追加), 不新建多个. 槽位恒为 0:
        首次创建 move 到内容区最前, 若思考区已存在则思考
        区后移让位, 保证 DOM 顺序恒为 引用 → 思考 → 正文.

        Args:
            hits: 规整后的引用切片列表.
        """
        bubble = self._current_bubble
        if bubble is None or not hits:
            return
        self._references_count += len(hits)
        if self._references_expansion is not None:
            self._append_reference_labels(
                self._references_expansion, hits
            )
            # set_text 更新标题 (TextElement 混入, 已核验)
            self._references_expansion.set_text(
                f'引用来源 ({self._references_count} 条)'
            )
            return
        with bubble:
            expansion = ui.expansion(
                f'引用来源 ({self._references_count} 条)',
                icon='fact_check',
                value=False,
            ).props('dense').classes(
                'w-full text-xs text-gray-400'
            )
            self._append_reference_labels(expansion, hits)
        # 引用区槽位恒为 0 (永远置顶); 思考区已存在则
        # 重 move 到引用之后, 维持 引用 → 思考 → 正文
        expansion.move(bubble, 0)
        if self._thinking_expansion is not None:
            self._thinking_expansion.move(bubble, 1)
        self._references_expansion = expansion

    def _append_reference_labels(
        self,
        expansion: ui.expansion,
        hits: list[SearchHit],
    ) -> None:
        """在引用折叠区内追加本批切片的展示条目.

        每条引用为浅色卡片行; 展示总数受
        ``_REFERENCES_LIMIT`` 钳制, 超额部分仅计入标题
        累计条数不渲染.

        Args:
            expansion: 引用来源折叠区.
            hits: 本批规整后的引用切片列表.
        """
        budget = _REFERENCES_LIMIT - self._references_shown
        if budget <= 0:
            return
        with expansion:
            for hit in hits[:budget]:
                doc_name = (
                    hit.doc_name or hit.title or '(未命名)'
                )
                ui.label(
                    f'{doc_name} (得分 {hit.score:.4f})'
                ).classes(
                    'w-full rounded-md bg-white/5 px-3 py-1.5 '
                    'text-xs text-gray-400'
                )
        self._references_shown += min(budget, len(hits))

    def _finish_bubble(self, stopped: bool) -> None:
        """结束当前回答: 停止标记 + 弱化用量小灰字.

        Args:
            stopped: 是否由用户主动停止生成.
        """
        if stopped and self._buffer:
            marker = '\n\n（已停止）'
            if self._degraded:
                if self._current_label is not None:
                    self._current_label.text = (
                        self._buffer + marker
                    )
            elif self._current_md is not None:
                self._current_md.set_content(
                    self._buffer + marker
                )
        elif stopped and self._thinking_expansion is not None:
            # 思考阶段即被停止, 无回答正文: 思考内容保留在
            # 折叠的思考区, 正文区仅标记已停止
            if self._current_md is not None:
                self._current_md.set_content('（已停止）')
        stamp = self._format_usage()
        if stamp and self._current_bubble is not None:
            # 自绘消息行无 q-chat-message stamp, 以弱化
            # 小灰字 label 追加在内容区末尾呈现
            with self._current_bubble:
                ui.label(stamp).classes(
                    'mt-1 text-xs text-gray-500'
                )
        self._scroll_to_bottom()

    def _mark_bubble_failed(self, summary: str) -> None:
        """在当前消息标记生成失败.

        Args:
            summary: 错误摘要文本.
        """
        marker = f'\n\n（生成失败: {summary}）'
        if self._degraded:
            if self._current_label is not None:
                self._current_label.text = (
                    self._buffer + marker
                )
        elif self._current_md is not None:
            self._current_md.set_content(self._buffer + marker)
        self._scroll_to_bottom()

    def _format_usage(self) -> str:
        """把尾流 token 用量格式化为 stamp 文本.

        Returns:
            用量摘要文本, 无量信息时返回空字符串.
        """
        usage = self._usage
        if not isinstance(usage, dict) or not usage:
            return ''
        parts = [
            f'{key}={value}' for key, value in usage.items()
            if isinstance(value, (int, float, str))
        ]
        if not parts:
            return ''
        return '用量: ' + ', '.join(parts)

    def _scroll_to_bottom(self) -> None:
        """智能跟随滚动: 仅在用户位于底部附近时拉底.

        用户上滑查看历史时停止拉动, 避免抢滚动.
        """
        if (
            self._scroll_area is not None
            and self._should_follow_scroll()
        ):
            self._scroll_area.scroll_to(percent=1.0)

    def _handle_scroll(
        self, event: ScrollEventArguments
    ) -> None:
        """缓存浏览器侧滚动状态, 供跟随判断使用.

        ScrollArea 无同步读取滚动位置的服务端 API (已核验
        .venv 源码), 仅能经 on_scroll 事件缓存末次状态.

        Args:
            event: 滚动事件, 携带垂直位置与内容尺寸.
        """
        self._scroll_top_offset = max(
            0.0,
            event.vertical_size
            - event.vertical_container_size
            - event.vertical_position,
        )
        self._scroll_bottom_percent = event.vertical_percentage
        self._scroll_event_seen = True

    def _should_follow_scroll(self) -> bool:
        """判断当前是否应跟随滚动到底部.

        Returns:
            True: 尚未收到滚动事件 (默认跟随), 或末次事件
            距底不足 ``_SCROLL_FOLLOW_BOTTOM_GAP`` 像素;
            内容增长会使缓存距底值失真, 故末次百分比不低于
            ``_SCROLL_FOLLOW_PERCENT`` 时亦视为在底部附近.
        """
        if not self._scroll_event_seen:
            return True
        if self._scroll_top_offset <= _SCROLL_FOLLOW_BOTTOM_GAP:
            return True
        return self._scroll_bottom_percent >= _SCROLL_FOLLOW_PERCENT

    # --------------------------------------------------
    # UI 状态管理
    # --------------------------------------------------
    def _refresh_btn_state(self) -> None:
        """刷新发送/停止按钮可见性与灰化.

        发送与停止同位互斥: 空闲显示发送图标, 运行中替换
        为停止图标. 能力位取 ``_chat_supported`` 缓存
        (set_platform 时按后端 ``supports_chat`` 刷新),
        避免每次 tick 构造 backend.
        """
        if self._btn_send is not None:
            self._btn_send.visible = not self._running
            if self._running or not self._chat_supported:
                self._btn_send.disable()
            else:
                self._btn_send.enable()
        if self._btn_stop is not None:
            self._btn_stop.visible = self._running
