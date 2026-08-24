"""操作面板: 数据源选择 + 行业参数 + 一键/分步调度.

提供 SSE/BSE/SZSE/全部数据源切换, 一键全自动与分步执行
两种运行模式, 以及完整的爬取-上传流水线后台调度.
目标平台由外部 (全局平台下拉) 经 set_platform 注入.
"""

import asyncio
from typing import Any
from typing import cast

from loguru import logger
from nicegui import background_tasks
from nicegui import run
from nicegui import ui

from ipo_know.clients.aliyun_knowledge.client import AliyunKnowledgeClient
from ipo_know.clients.viking_knowledge import VikingKnowledgeClient
from ipo_know.config.config import VikingKnowledgeSettings
from ipo_know.crawler import BSEIPOCrawler
from ipo_know.crawler import SSEIPOCrawler
from ipo_know.crawler import SZSEIPOCrawler
from ipo_know.kb_align import VolcKBAligner
from ipo_know.kb_align.aliyun_aligner import AliyunKBAligner
from ipo_know.ui.config_store import GUIConfigStore
from ipo_know.ui.log_panel import LogPanel
from ipo_know.ui.panel_helpers import error_summary
from ipo_know.ui.panel_helpers import safe_notify
from ipo_know.ui.platform import PLATFORM_OPTIONS
from ipo_know.ui.platform import missing_config_items


_SOURCE_OPTIONS: dict[str, str] = {
    'sse': 'SSE (上交所)',
    'bse': 'BSE (北交所)',
    'szse': 'SZSE (深交所)',
    'all': '全部 (ALL)',
}


class OperationPanel:
    """操作面板, 管理数据源选择、行业参数与任务调度.

    支持"一键全自动"与"分步执行"两种模式. 一键模式执行完整
    爬取-上传流水线; 分步模式将爬取与上传拆为两步, 中间结果
    缓存在 ``_cached_files`` 中. 上传目标平台由外部经
    ``set_platform`` 注入, 一次执行只对齐一个平台.

    Attributes:
        _store: GUI 配置持久化存储实例.
        _log_panel: 日志面板, 用于启停日志捕获.
        _running: 后台任务是否正在运行.
        _platform: 外部注入的目标平台标识 (aliyun/volc).
        _cached_files: 分步模式下爬取阶段缓存的文件清单.
        _container: 面板根容器, 供后台任务恢复 UI 上下文.
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
        self._platform: str = 'aliyun'
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
        self._spinner: ui.spinner | None = None
        self._container: ui.card | None = None

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

    def set_platform(self, platform: str) -> None:
        """由外部全局平台下拉注入目标平台标识.

        仅更新存值, 不影响运行中任务: 已启动任务的
        平台值在回调时快照传入, 不受后续切换影响.

        Args:
            platform: 平台标识 (aliyun/volc).
        """
        self._platform = platform

    # --------------------------------------------------
    # UI 构建
    # --------------------------------------------------
    def _build_ui(self) -> None:
        """构建操作面板 UI 布局."""
        container = ui.card().classes('w-full p-4 gap-2')
        self._container = container
        with container:
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
        # 平台值在回调时读取快照传入后台任务, 避免
        # 任务期间 UI 值变化影响本次执行.
        platform = self._current_platform()
        missing = missing_config_items(self._store, platform)
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
            self._run_pipeline(source, industry, platform),
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
        # 平台值在回调时读取快照传入后台任务.
        platform = self._current_platform()
        missing = missing_config_items(self._store, platform)
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
            self._run_upload_only(platform), name='upload only'
        )

    # --------------------------------------------------
    # 后台任务: 完整流水线
    # --------------------------------------------------
    async def _run_pipeline(
        self, source: str, industry: str, platform: str
    ) -> None:
        """执行完整爬取-上传流水线.

        Args:
            source: 数据源标识 (sse/bse/szse/all).
            industry: 行业参数.
            platform: 目标平台标识 (aliyun/volc) 快照值.
        """
        self._running = True
        # 确保日志捕获已启动 (幂等): 异常日志必须在
        # 任何可能失败的步骤之前已可被日志面板接收.
        self._log_panel.start_capture()
        try:
            if source == 'all':
                files_map = await self._crawl_all(industry)
                await self._upload_all(files_map, platform)
            else:
                files = await self._crawl_single(
                    source, industry
                )
                await self._upload_single(
                    source, files, platform
                )
            safe_notify(
                self._container, '执行完成', type='positive'
            )
        except Exception as exc:
            logger.exception('一键爬取上传执行失败')
            safe_notify(
                self._container,
                f'执行失败: {error_summary(exc)}',
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
            safe_notify(
                self._container,
                '采集完成, 可执行上传对齐',
                type='positive',
            )
        except Exception as exc:
            logger.exception('文件清单采集失败')
            safe_notify(
                self._container,
                f'采集失败: {error_summary(exc)}',
                type='negative',
            )
        finally:
            self._running = False

    # --------------------------------------------------
    # 后台任务: 分步上传
    # --------------------------------------------------
    async def _run_upload_only(self, platform: str) -> None:
        """分步模式: 使用缓存文件执行上传.

        Args:
            platform: 目标平台标识 (aliyun/volc) 快照值.
        """
        self._running = True
        self._log_panel.start_capture()
        try:
            await self._upload_all(self._cached_files, platform)
            safe_notify(
                self._container,
                '上传对齐完成',
                type='positive',
            )
        except Exception as exc:
            logger.exception('上传对齐执行失败')
            safe_notify(
                self._container,
                f'上传失败: {error_summary(exc)}',
                type='negative',
            )
        finally:
            self._running = False

    # --------------------------------------------------
    # 配置校验
    # --------------------------------------------------
    def _current_platform(self) -> str:
        """读取外部注入的目标平台标识.

        Returns:
            平台标识 (aliyun/volc).
        """
        return self._platform

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
    def _build_aligner(
        self, platform: str, source: str
    ) -> AliyunKBAligner | VolcKBAligner:
        """按目标平台构造对应的知识库对齐器.

        Args:
            platform: 目标平台标识 (aliyun/volc).
            source: 数据源标识 (sse/bse/szse).

        Returns:
            阿里云或火山引擎平台的对齐器实例.

        Raises:
            ValueError: 平台标识不受支持时抛出.
        """
        if platform == 'volc':
            client_kwargs = self._store.get_volc_client_kwargs()
            client = VikingKnowledgeClient(**client_kwargs)  # type: ignore[arg-type]
            volc_cfg = cast(
                VikingKnowledgeSettings, client_kwargs['config']
            )
            return VolcKBAligner(
                source=source,
                client=client,
                strategy_resource_id=volc_cfg.strategy_resource_id,
            )
        if platform == 'aliyun':
            client_kwargs = self._store.get_aliyun_client_kwargs()
            client_ak = AliyunKnowledgeClient(**client_kwargs)
            return AliyunKBAligner(
                source=source, client=client_ak
            )
        raise ValueError(f'不支持的目标平台: {platform}')

    async def _upload_all(
        self,
        files_map: dict[str, list[dict[str, Any]]],
        platform: str,
    ) -> None:
        """逐所串行上传对齐.

        Args:
            files_map: 以数据源标识为 key、文件清单为 value.
            platform: 目标平台标识 (aliyun/volc).
        """
        platform_name = PLATFORM_OPTIONS.get(platform, platform)
        for source, files in files_map.items():
            logger.info(
                '开始上传到 {} | 数据源: {}', platform_name, source
            )
            aligner = self._build_aligner(platform, source)
            await aligner.align(files)

    async def _upload_single(
        self,
        source: str,
        files: list[dict[str, Any]],
        platform: str,
    ) -> None:
        """单所上传对齐.

        Args:
            source: 数据源标识.
            files: 文件清单列表.
            platform: 目标平台标识 (aliyun/volc).
        """
        platform_name = PLATFORM_OPTIONS.get(platform, platform)
        logger.info(
            '开始上传到 {} | 数据源: {}', platform_name, source
        )
        aligner = self._build_aligner(platform, source)
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
            if self._spinner:
                self._spinner.visible = False
