"""操作面板: 数据源选择 + 行业参数 + 一键/分步 + 后台任务调度.

提供 SSE/BSE/SZSE/全部数据源切换, 一键全自动与分步执行
两种运行模式, 以及完整的爬取-上传流水线后台调度.
"""

import asyncio
import webbrowser
from typing import Any

from loguru import logger
from nicegui import background_tasks
from nicegui import run
from nicegui import ui

from ipo_know.clients.aliyun_knowledge.client import AliyunKnowledgeClient
from ipo_know.crawler import BSEIPOCrawler
from ipo_know.crawler import SSEIPOCrawler
from ipo_know.crawler import SZSEIPOCrawler
from ipo_know.kb_align.aliyun_aligner import AliyunKBAligner
from ipo_know.ui.config_store import GUIConfigStore
from ipo_know.ui.log_panel import LogPanel


_SOURCE_OPTIONS: dict[str, str] = {
    'sse': 'SSE (上交所)',
    'bse': 'BSE (北交所)',
    'szse': 'SZSE (深交所)',
    'all': '全部 (ALL)',
}

# 启动上传流水线前必须已配置的字段: (字段名, 展示名).
_REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ('ak', 'AK'),
    ('sk', 'SK'),
    ('workspace_id', 'Workspace ID'),
    ('index_id', 'Index ID'),
)

# 错误摘要在弹窗中的最大展示长度.
_ERROR_SUMMARY_LIMIT = 100


def _error_summary(exc: Exception) -> str:
    """将异常压缩为适合弹窗展示的简短摘要.

    Args:
        exc: 捕获到的异常实例.

    Returns:
        截断到 ``_ERROR_SUMMARY_LIMIT`` 字符以内的错误描述.
    """
    text = str(exc) or exc.__class__.__name__
    text = ' '.join(text.split())
    if len(text) > _ERROR_SUMMARY_LIMIT:
        return text[:_ERROR_SUMMARY_LIMIT] + '…'
    return text


class OperationPanel:
    """操作面板, 管理数据源选择、行业参数与后台任务调度.

    支持"一键全自动"与"分步执行"两种模式. 一键模式执行完整
    爬取-上传流水线; 分步模式将爬取与上传拆为两步, 中间结果
    缓存在 ``_cached_files`` 中.

    Attributes:
        _store: GUI 配置持久化存储实例.
        _log_panel: 日志面板, 用于启停日志捕获.
        _running: 后台任务是否正在运行.
        _cached_files: 分步模式下爬取阶段缓存的文件清单.
    """

    def __init__(
        self,
        config_store: GUIConfigStore,
        log_panel: LogPanel,
    ) -> None:
        """初始化操作面板.

        Args:
            config_store: 配置持久化存储实例.
            log_panel: 日志面板实例.
        """
        self._store = config_store
        self._log_panel = log_panel
        self._running: bool = False
        self._cached_files: dict[str, list[dict[str, Any]]] = {}

        # UI 引用 (在 _build_ui 中赋值)
        self._source_select: ui.select | None = None
        self._industry_input: ui.input | None = None
        self._mode_toggle: ui.toggle | None = None
        self._auto_row: ui.row | None = None
        self._step_row: ui.row | None = None
        self._btn_run: ui.button | None = None
        self._btn_crawl: ui.button | None = None
        self._btn_upload: ui.button | None = None
        self._btn_console: ui.button | None = None
        self._spinner: ui.spinner | None = None

        self._build_ui()

    # --------------------------------------------------
    # 公开接口
    # --------------------------------------------------
    def is_running(self) -> bool:
        """返回后台任务是否正在运行.

        Returns:
            True 表示任务运行中.
        """
        return self._running

    # --------------------------------------------------
    # UI 构建
    # --------------------------------------------------
    def _build_ui(self) -> None:
        """构建操作面板 UI 布局."""
        with ui.card().classes('w-full p-4 gap-2'):
            ui.label('操作面板').classes(
                'text-lg font-bold mb-2'
            )

            # 数据源选择
            self._source_select = ui.select(
                options=_SOURCE_OPTIONS,
                label='数据源',
                value='sse',
                on_change=self._on_source_change,
            ).classes('w-full')

            # 行业参数
            self._industry_input = ui.input(
                label='行业代码',
                value='C36',
            ).classes('w-full').tooltip(
                'SSE 使用行业代码(如 C36),'
                ' BSE/SZSE 使用行业名称'
            )

            # 模式切换
            self._mode_toggle = ui.toggle(
                {'auto': '一键全自动', 'step': '分步执行'},
                value='auto',
                on_change=self._on_mode_change,
            ).classes('w-full')

            # 一键模式按钮行
            with ui.row().classes('w-full mt-2 gap-2') as auto_row:
                self._auto_row = auto_row
                self._btn_run = ui.button(
                    '一键爬取上传',
                    on_click=self._on_auto_run,
                    icon='play_arrow',
                ).classes('flex-1')

            # 分步模式按钮行
            with ui.row().classes('w-full mt-2 gap-2') as step_row:
                self._step_row = step_row
                self._btn_crawl = ui.button(
                    '采集文件清单',
                    on_click=self._on_step_crawl,
                    icon='download',
                ).classes('flex-1')
                self._btn_upload = ui.button(
                    '上传对齐',
                    on_click=self._on_step_upload,
                    icon='cloud_upload',
                ).classes('flex-1').disable()

            self._step_row.visible = False

            # 底部按钮行
            with ui.row().classes('w-full mt-2 gap-2'):
                self._btn_console = ui.button(
                    '打开知识库控制台',
                    on_click=self._open_console,
                    icon='open_in_new',
                ).classes('flex-1')

            # 运行中 spinner (默认隐藏)
            self._spinner = ui.spinner(
                size='lg',
            ).classes('self-center mt-2')
            self._spinner.visible = False

        # 定时刷新按钮灰化状态
        ui.timer(0.5, self._refresh_ui_state)

    # --------------------------------------------------
    # UI 事件回调
    # --------------------------------------------------
    def _on_source_change(
        self,
        e: ui.select,  # type: ignore[name-defined]
    ) -> None:
        """数据源切换时更新行业参数标签和默认值.

        Args:
            e: NiceGUI 选择事件对象.
        """
        source = e.value
        if self._industry_input is None:
            return
        if source == 'sse':
            self._industry_input.label = '行业代码'
            self._industry_input.value = 'C36'
        else:
            self._industry_input.label = '行业名称'
            self._industry_input.value = '汽车制造业'

    def _on_mode_change(
        self,
        e: ui.toggle,  # type: ignore[name-defined]
    ) -> None:
        """模式切换时显隐对应按钮行.

        Args:
            e: NiceGUI toggle 事件对象.
        """
        is_auto = e.value == 'auto'
        if self._auto_row:
            self._auto_row.visible = is_auto
        if self._step_row:
            self._step_row.visible = not is_auto

    # --------------------------------------------------
    # 一键模式
    # --------------------------------------------------
    def _on_auto_run(self) -> None:
        """一键模式: 校验配置后启动完整爬取-上传流水线."""
        if self._running:
            return
        missing = self._missing_config_items()
        if missing:
            logger.warning(
                '一键执行被拦截: 缺少配置项 {}', missing
            )
            ui.notify(
                '请先填写必要配置项: ' + ', '.join(missing),
                type='warning',
            )
            return
        source = self._source_select.value  # type: ignore[union-attr]
        industry = (
            self._industry_input.value  # type: ignore[union-attr]
        )
        background_tasks.create(
            self._run_pipeline(source, industry),
            name='one-click pipeline',
        )

    # --------------------------------------------------
    # 分步模式
    # --------------------------------------------------
    def _on_step_crawl(self) -> None:
        """分步模式: 仅执行爬取阶段."""
        if self._running:
            return
        source = self._source_select.value  # type: ignore[union-attr]
        industry = (
            self._industry_input.value  # type: ignore[union-attr]
        )
        background_tasks.create(
            self._run_crawl_only(source, industry),
            name='crawl only',
        )

    def _on_step_upload(self) -> None:
        """分步模式: 校验配置后使用缓存文件执行上传."""
        if self._running or not self._cached_files:
            return
        missing = self._missing_config_items()
        if missing:
            logger.warning(
                '上传对齐被拦截: 缺少配置项 {}', missing
            )
            ui.notify(
                '请先填写必要配置项: ' + ', '.join(missing),
                type='warning',
            )
            return
        background_tasks.create(
            self._run_upload_only(), name='upload only'
        )

    # --------------------------------------------------
    # 控制台
    # --------------------------------------------------
    @staticmethod
    def _open_console() -> None:
        """用默认浏览器打开阿里云百炼控制台."""
        webbrowser.open(
            'https://bailian.console.aliyun.com/cn-beijing'
            '?tab=app#/app-market/suggest'
        )

    # --------------------------------------------------
    # 后台任务: 完整流水线
    # --------------------------------------------------
    async def _run_pipeline(
        self, source: str, industry: str
    ) -> None:
        """执行完整爬取-上传流水线.

        Args:
            source: 数据源标识 (sse/bse/szse/all).
            industry: 行业参数.
        """
        self._running = True
        # 确保日志捕获已启动 (幂等): 异常日志必须在
        # 任何可能失败的步骤之前已可被日志面板接收.
        self._log_panel.start_capture()
        try:
            if source == 'all':
                files_map = await self._crawl_all(industry)
                await self._upload_all(files_map)
            else:
                files = await self._crawl_single(
                    source, industry
                )
                await self._upload_single(source, files)
            ui.notify('执行完成', type='positive')
        except Exception as exc:
            logger.exception('一键爬取上传执行失败')
            ui.notify(
                f'执行失败: {_error_summary(exc)}',
                type='negative',
            )
        finally:
            self._running = False
            # 注意: 不调用 stop_capture(). 日志捕获由页面
            # 启动时全局注册, 此处停止会导致日志面板
            # 在首次运行后永久静默, 错误信息不可见.

    # --------------------------------------------------
    # 后台任务: 分步爬取
    # --------------------------------------------------
    async def _run_crawl_only(
        self, source: str, industry: str
    ) -> None:
        """分步模式: 仅爬取并将结果缓存.

        Args:
            source: 数据源标识.
            industry: 行业参数.
        """
        self._running = True
        self._log_panel.start_capture()
        try:
            if source == 'all':
                self._cached_files = await self._crawl_all(
                    industry
                )
            else:
                files = await self._crawl_single(
                    source, industry
                )
                self._cached_files = {source: files}
            ui.notify(
                '采集完成, 可执行上传对齐', type='positive'
            )
        except Exception as exc:
            logger.exception('文件清单采集失败')
            ui.notify(
                f'采集失败: {_error_summary(exc)}',
                type='negative',
            )
        finally:
            self._running = False

    # --------------------------------------------------
    # 后台任务: 分步上传
    # --------------------------------------------------
    async def _run_upload_only(self) -> None:
        """分步模式: 使用缓存文件执行上传."""
        self._running = True
        self._log_panel.start_capture()
        try:
            await self._upload_all(self._cached_files)
            ui.notify('上传对齐完成', type='positive')
        except Exception as exc:
            logger.exception('上传对齐执行失败')
            ui.notify(
                f'上传失败: {_error_summary(exc)}',
                type='negative',
            )
        finally:
            self._running = False

    # --------------------------------------------------
    # 配置校验
    # --------------------------------------------------
    def _missing_config_items(self) -> list[str]:
        """检查已保存配置中的必填项, 返回缺失项列表.

        Returns:
            缺失的必填配置项展示名列表, 空列表表示均已配置.
        """
        data = self._store.load()
        raw = data.get('aliyun_knowledge', {})
        ak_data = raw if isinstance(raw, dict) else {}
        missing: list[str] = []
        for key, label in _REQUIRED_FIELDS:
            value = ak_data.get(key)
            if not str(value or '').strip():
                missing.append(label)
        return missing

    # --------------------------------------------------
    # 爬取逻辑
    # --------------------------------------------------
    async def _crawl_all(
        self, industry: str
    ) -> dict[str, list[dict[str, Any]]]:
        """并行爬取三所数据.

        Args:
            industry: BSE/SZSE 使用的行业名称.

        Returns:
            以数据源标识为 key、文件清单为 value 的字典.
        """
        sse_files, bse_files, szse_files = (
            await asyncio.gather(
                run.io_bound(
                    SSEIPOCrawler().collect,
                    csrc_code='C36',
                    issue_market_type='1,2',
                ),
                run.io_bound(
                    BSEIPOCrawler().collect,
                    csrc_industry=industry,
                ),
                run.io_bound(
                    SZSEIPOCrawler().collect,
                    industry=industry,
                ),
            )
        )
        return {
            'sse': sse_files,
            'bse': bse_files,
            'szse': szse_files,
        }

    async def _crawl_single(
        self, source: str, industry: str
    ) -> list[dict[str, Any]]:
        """单所爬取.

        Args:
            source: 数据源标识 (sse/bse/szse).
            industry: 行业参数.

        Returns:
            文件清单列表.
        """
        if source == 'sse':
            return await run.io_bound(
                SSEIPOCrawler().collect,
                csrc_code=industry,
                issue_market_type='1,2',
            )
        if source == 'bse':
            return await run.io_bound(
                BSEIPOCrawler().collect,
                csrc_industry=industry,
            )
        return await run.io_bound(
            SZSEIPOCrawler().collect,
            industry=industry,
        )

    # --------------------------------------------------
    # 上传逻辑
    # --------------------------------------------------
    async def _upload_all(
        self, files_map: dict[str, list[dict[str, Any]]]
    ) -> None:
        """逐所串行上传对齐.

        Args:
            files_map: 以数据源标识为 key、文件清单为 value.
        """
        client_kwargs = self._store.get_aliyun_client_kwargs()
        for source, files in files_map.items():
            client = AliyunKnowledgeClient(**client_kwargs)
            aligner = AliyunKBAligner(
                source=source, client=client
            )
            await aligner.align(files)

    async def _upload_single(
        self, source: str, files: list[dict[str, Any]]
    ) -> None:
        """单所上传对齐.

        Args:
            source: 数据源标识.
            files: 文件清单列表.
        """
        client_kwargs = self._store.get_aliyun_client_kwargs()
        client = AliyunKnowledgeClient(**client_kwargs)
        aligner = AliyunKBAligner(
            source=source, client=client
        )
        await aligner.align(files)

    # --------------------------------------------------
    # UI 状态管理
    # --------------------------------------------------
    def _refresh_ui_state(self) -> None:
        """根据 _running 状态刷新所有操作按钮灰化."""
        if self._running:
            if self._btn_run:
                self._btn_run.disable()
            if self._btn_crawl:
                self._btn_crawl.disable()
            if self._btn_upload:
                self._btn_upload.disable()
            if self._btn_console:
                self._btn_console.disable()
            if self._spinner:
                self._spinner.visible = True
        else:
            if self._btn_run:
                self._btn_run.enable()
            if self._btn_crawl:
                self._btn_crawl.enable()
            # 上传按钮: 有缓存才启用
            if self._btn_upload:
                if self._cached_files:
                    self._btn_upload.enable()
                else:
                    self._btn_upload.disable()
            if self._btn_console:
                self._btn_console.enable()
            if self._spinner:
                self._spinner.visible = False
