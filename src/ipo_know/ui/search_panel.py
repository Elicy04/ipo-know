"""知识检索面板.

提供知识库检索入口: 查询文本 + 返回条数上限输入,
后台调用 kb_query 抽象层执行检索, 结果单批渲染为
可折叠切片列表.
"""

import time

from loguru import logger
from nicegui import background_tasks
from nicegui import ui

from ipo_know.kb_query import SearchHit
from ipo_know.kb_query import create_query_backend
from ipo_know.ui.config_store import GUIConfigStore
from ipo_know.ui.log_panel import LogPanel
from ipo_know.ui.panel_helpers import error_summary
from ipo_know.ui.panel_helpers import safe_notify
from ipo_know.ui.platform import PLATFORM_OPTIONS
from ipo_know.ui.platform import missing_config_items


# 查询文本长度上限 (字符).
_QUERY_MAX_LENGTH = 8000

# 结果区最多渲染的命中条数.
_RENDER_LIMIT = 20

# 阿里云 Retrieve rerank_top_n 官方上限 (后端静默钳制至此值).
_ALIYUN_SEARCH_LIMIT = 20

# 折叠头部展示的正文截断长度 (字符).
_HEADER_TRUNCATE_LENGTH = 300


class SearchPanel:
    """知识检索面板.

    Attributes:
        _store: GUI 配置持久化存储实例.
        _log_panel: 日志面板实例, 可为 None.
        _platform: 当前目标平台标识 (aliyun/volc).
        _running: 检索后台任务是否进行中.
        _run_id: 运行代次号, 启动检索与切换平台各自增,
            用于拦截旧代次任务的跨平台渲染.
        _query_input: 查询文本输入框.
        _limit_input: 返回条数上限数值框.
        _btn_search: 检索按钮.
        _result_label: 结果总数提示标签.
        _results_col: 结果列表容器 (位于滚动区内).
        _container: 面板根容器, 供后台任务恢复 UI 上下文.
    """

    def __init__(
        self,
        config_store: GUIConfigStore,
        log_panel: LogPanel | None = None,
    ) -> None:
        """初始化检索面板.

        Args:
            config_store: 配置持久化存储实例.
            log_panel: 日志面板实例, 用于启动日志捕获.
        """
        self._store = config_store
        self._log_panel = log_panel
        self._platform: str = 'aliyun'
        self._running: bool = False
        self._run_id: int = 0
        self._query_input: ui.textarea | None = None
        self._limit_input: ui.number | None = None
        self._btn_search: ui.button | None = None
        self._result_label: ui.label | None = None
        self._results_col: ui.column | None = None
        self._scroll_area: ui.scroll_area | None = None
        self._container: ui.card | None = None
        self._build_ui()

    # --------------------------------------------------
    # 公开接口
    # --------------------------------------------------
    def set_platform(self, platform: str) -> None:
        """切换目标平台: 清空结果区并提示.

        运行中的检索任务以快照平台执行, 不受影响;
        结果区属旧平台, 一律清空避免误导.

        Args:
            platform: 平台标识 (aliyun/volc).
        """
        self._platform = platform
        # 代次号作废: 在途检索任务完成后不再渲染旧平台结果
        self._run_id += 1
        self._clear_results()
        platform_name = PLATFORM_OPTIONS.get(platform, platform)
        safe_notify(
            self._container,
            f'知识检索已切换到 {platform_name}',
            type='info',
        )

    # --------------------------------------------------
    # UI 构建
    # --------------------------------------------------
    def _build_ui(self) -> None:
        """构建检索面板 UI 布局."""
        container = ui.card().classes('w-full p-4 gap-2')
        self._container = container
        with container:
            ui.label('知识检索').classes('text-lg font-bold')

            self._query_input = ui.textarea(
                label='查询内容',
                placeholder=(
                    f'输入检索文本 (不超过 {_QUERY_MAX_LENGTH} 字)'
                ),
            ).classes('w-full').props('autogrow rows=2')

            with ui.row().classes('w-full items-center gap-2'):
                self._limit_input = ui.number(
                    label='返回条数',
                    value=10,
                    min=1,
                    max=1000,
                ).classes('w-32')
                self._btn_search = ui.button(
                    '检索',
                    on_click=self._on_search,
                    icon='search',
                ).classes('flex-1')

            self._result_label = ui.label('').classes(
                'text-sm text-gray-400'
            )
            self._scroll_area = ui.scroll_area().classes(
                'w-full h-96'
            )
            with self._scroll_area:
                self._results_col = ui.column().classes(
                    'w-full gap-2'
                )

        # 定时刷新检索按钮灰化状态
        ui.timer(0.5, self._refresh_btn_state)

    # --------------------------------------------------
    # 检索执行 (后台任务五段式)
    # --------------------------------------------------
    def _on_search(self) -> None:
        """检索按钮回调: 前端校验后启动后台检索任务."""
        # 段一: 防重入
        if self._running:
            return
        # 段二: 快照当前输入与平台
        query = str(self._query_input.value or '').strip() \
            if self._query_input is not None else ''
        raw_limit = self._limit_input.value \
            if self._limit_input is not None else 10
        limit = int(raw_limit) if raw_limit else 10
        limit = max(1, min(limit, 1000))
        platform = self._platform
        # 段三: 校验
        if not query:
            safe_notify(
                self._container, '请输入查询内容', type='warning'
            )
            return
        if len(query) > _QUERY_MAX_LENGTH:
            safe_notify(
                self._container,
                f'查询内容过长, 请不超过 {_QUERY_MAX_LENGTH} 字',
                type='warning',
            )
            return
        missing = missing_config_items(self._store, platform)
        if missing:
            safe_notify(
                self._container,
                '请先填写必要配置项: ' + ', '.join(missing),
                type='warning',
            )
            return
        # 段四: 启动后台任务 (代次号自增, 供完成时校验)
        self._running = True
        self._run_id += 1
        run_id = self._run_id
        # 段五: try-finally 由后台协程承担
        background_tasks.create(
            self._run_search(query, limit, platform, run_id),
            name='kb search',
        )

    async def _run_search(
        self,
        query: str,
        limit: int,
        platform: str,
        run_id: int,
    ) -> None:
        """后台执行知识库检索并渲染结果.

        Args:
            query: 检索文本快照.
            limit: 返回条数上限快照.
            platform: 目标平台标识快照.
            run_id: 启动时的运行代次号快照.
        """
        if self._log_panel is not None:
            self._log_panel.start_capture()
        start_time = time.perf_counter()
        logger.info(
            '知识检索开始 | platform={} | limit={} | query_len={}',
            platform, limit, len(query),
        )
        try:
            backend = create_query_backend(platform, self._store)
            hits = await backend.search(query, limit)
            elapsed = time.perf_counter() - start_time
            logger.info(
                '知识检索完成 | platform={} | 命中 {} 条 | 耗时 {:.1f}s',
                platform, len(hits), elapsed,
            )
            # 代次校验: 期间切换平台或重新发起检索,
            # 旧代次结果不再渲染进当前结果区
            if run_id != self._run_id:
                return
            self._render_results(hits, platform, limit)
            safe_notify(
                self._container,
                f'检索完成, 命中 {len(hits)} 条',
                type='positive',
            )
        except Exception as exc:
            logger.exception(
                '知识检索失败 | platform={} | {}',
                platform, exc,
            )
            safe_notify(
                self._container,
                f'检索失败: {error_summary(exc)}',
                type='negative',
            )
        finally:
            self._running = False

    # --------------------------------------------------
    # 结果渲染
    # --------------------------------------------------
    def _render_results(
        self,
        hits: list[SearchHit],
        platform: str,
        limit: int,
    ) -> None:
        """单批渲染检索结果列表.

        展示上限 ``_RENDER_LIMIT`` 条, 每条由得分/文档名
        头部行与折叠正文组成.

        Args:
            hits: 归一化命中结果列表.
            platform: 本次检索的目标平台标识.
            limit: 本次请求的返回条数上限.
        """
        self._clear_results()
        if self._result_label is not None:
            shown = min(len(hits), _RENDER_LIMIT)
            text = (
                f'共命中 {len(hits)} 条, 展示前 {shown} 条'
                if hits else '未命中任何结果'
            )
            # 阿里云 Retrieve rerank_top_n 上限 20, 后端静默钳制,
            # 此处显式提示避免用户误以为可返回更多结果
            if platform == 'aliyun' and limit > _ALIYUN_SEARCH_LIMIT:
                text += (
                    f'（阿里云单次检索上限 {_ALIYUN_SEARCH_LIMIT} 条）'
                )
            self._result_label.text = text
        if self._results_col is None:
            return
        with self._results_col:
            for index, hit in enumerate(hits[:_RENDER_LIMIT]):
                self._render_hit(index, hit)

    def _render_hit(self, index: int, hit: SearchHit) -> None:
        """渲染单条命中结果.

        Args:
            index: 结果序号 (从 0 起).
            hit: 归一化命中结果.
        """
        doc_name = hit.doc_name or hit.title or '(未知文档)'
        with ui.card().classes('w-full p-2 gap-1'):
            with ui.row().classes('w-full items-center gap-2'):
                ui.label(f'#{index + 1}').classes(
                    'text-sm text-gray-400'
                )
                ui.label(f'得分 {hit.score:.4f}').classes(
                    'text-sm font-medium'
                )
                ui.label(doc_name).classes(
                    'text-sm text-gray-300 truncate'
                )
            header_text = hit.content[:_HEADER_TRUNCATE_LENGTH]
            with ui.expansion(header_text or '(空切片)').classes(
                'w-full'
            ):
                ui.label(hit.content).classes(
                    'w-full whitespace-pre-wrap text-sm'
                )

    def _clear_results(self) -> None:
        """清空结果区与总数提示."""
        if self._results_col is not None:
            self._results_col.clear()
        if self._result_label is not None:
            self._result_label.text = ''

    # --------------------------------------------------
    # UI 状态管理
    # --------------------------------------------------
    def _refresh_btn_state(self) -> None:
        """根据 _running 状态刷新检索按钮灰化."""
        if self._btn_search is None:
            return
        if self._running:
            self._btn_search.disable()
        else:
            self._btn_search.enable()
