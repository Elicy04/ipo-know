"""监控面板: 账户余额 + 知识库监控 + 账单与流水.

提供阿里云百炼与火山引擎两个平台的账户余额查询、
知识库存储监控与账单展示. 后台并行拉取各类数据,
各自独立渲染到对应卡片区域. 账单卡片含「消费明细」
(阿里云实例账单, 独立降级) 与「资金流水」双子页签.
"""

import asyncio
import json
import time
from datetime import datetime

from loguru import logger
from nicegui import background_tasks
from nicegui import ui

from ipo_know.clients.aliyun_knowledge.client import AliyunKnowledgeClient
from ipo_know.clients.monitor_dto import BalanceInfo
from ipo_know.clients.monitor_dto import BillDetailItem
from ipo_know.clients.monitor_dto import InstanceBillItem
from ipo_know.clients.monitor_dto import KbMonitorSummary
from ipo_know.clients.viking_knowledge import VikingKnowledgeClient
from ipo_know.ui.config_store import GUIConfigStore
from ipo_know.ui.panel_helpers import error_summary
from ipo_know.ui.panel_helpers import safe_notify
from ipo_know.ui.platform import PLATFORM_OPTIONS
from ipo_know.ui.platform import missing_config_items


def _format_ts(ts: object) -> str | None:
    """将 Unix 时间戳转换为可读日期字符串.

    Args:
        ts: Unix 时间戳 (int/str/None).

    Returns:
        'YYYY-MM-DD HH:MM:SS' 格式字符串,
        无法转换时返回 None.
    """
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(
            int(ts),
        ).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, OSError, OverflowError):
        return None


# 资金流水表格列定义.
_BILL_COLUMNS = [
    {'name': 'date', 'label': '日期',
     'field': 'date', 'align': 'left'},
    {'name': 'product', 'label': '交易类型',
     'field': 'product', 'align': 'left'},
    {'name': 'amount', 'label': '金额',
     'field': 'amount', 'align': 'right'},
    {'name': 'payment_method', 'label': '交易渠道',
     'field': 'payment_method', 'align': 'left'},
    {'name': 'remark', 'label': '备注',
     'field': 'remark', 'align': 'left'},
]

# 消费明细表格列定义 (实例级账单).
_INSTANCE_BILL_COLUMNS = [
    {'name': 'date', 'label': '日期',
     'field': 'date', 'align': 'left'},
    {'name': 'product', 'label': '产品明细',
     'field': 'product', 'align': 'left'},
    {'name': 'instance', 'label': '实例/计费项',
     'field': 'instance', 'align': 'left'},
    {'name': 'bill_type', 'label': '账单类型',
     'field': 'bill_type', 'align': 'left'},
    {'name': 'pretax', 'label': '应付金额',
     'field': 'pretax', 'align': 'right'},
    {'name': 'discount', 'label': '优惠',
     'field': 'discount', 'align': 'right'},
    {'name': 'payment', 'label': '现金支付',
     'field': 'payment', 'align': 'right'},
]

# 账单类型原始枚举 → 中文展示名.
_ITEM_TYPE_LABELS = {
    'SubscriptionOrder': '预付订单',
    'PayAsYouGoBill': '后付账单',
    'Refund': '退款',
    'Adjustment': '调账',
}

# 账期可选月数 (API 仅支持近 18 个月).
_BILL_CYCLE_MONTHS = 18

# 粒度切换选项: 接口枚举 → 展示文案 (NiceGUI dict 选项语义为 {值: 标签}).
_GRANULARITY_OPTIONS = {'MONTHLY': '按月', 'DAILY': '按日'}


class MonitorPanel:
    """监控面板: 账户余额 + 知识库监控 + 账单与流水.

    Attributes:
        _config_store: GUI 配置持久化存储实例.
        _platform: 当前目标平台标识 (aliyun/volc).
        _running: 后台刷新任务是否进行中.
        _run_id: 运行代次号, 防止旧任务渲染.
        _container: 面板根容器.
        _btn_refresh: 刷新按钮.
        _refresh_spinner: 刷新加载转圈指示器.
        _balance_col: 余额卡片内容容器.
        _monitor_col: 监控卡片内容容器.
        _bill_cycle_select: 消费明细账期下拉.
        _bill_granularity: 消费明细粒度切换.
        _bill_summary_row: 消费明细汇总条容器.
        _bill_status_label: 消费明细状态文案行.
        _instance_table: 消费明细表格组件.
        _tx_table: 资金流水表格组件.
    """

    def __init__(
        self, config_store: GUIConfigStore,
    ) -> None:
        """初始化监控面板.

        Args:
            config_store: 配置持久化存储实例.
        """
        self._config_store = config_store
        self._platform: str = ''
        self._running: bool = False
        self._run_id: int = 0
        self._container: ui.card | None = None
        self._btn_refresh: ui.button | None = None
        self._balance_col: ui.column | None = None
        self._monitor_col: ui.column | None = None
        self._bill_cycle_select: ui.select | None = None
        self._bill_granularity: ui.toggle | None = None
        self._refresh_spinner: ui.spinner | None = None
        self._bill_summary_row: ui.row | None = None
        self._bill_status_label: ui.label | None = None
        self._instance_table: ui.table | None = None
        self._tx_table: ui.table | None = None
        self._build_ui()

    # --------------------------------------------------
    # 公开接口
    # --------------------------------------------------
    def set_platform(self, platform: str) -> None:
        """平台切换回调: 清空当前数据并触发刷新.

        Args:
            platform: 平台标识 (aliyun/volc).
        """
        self._platform = platform
        self._run_id += 1
        self._clear_all_cards()
        # 消费明细控件仅阿里云语义下生效, 火山平台隐藏.
        aliyun_only = platform == 'aliyun'
        if self._bill_cycle_select is not None:
            self._bill_cycle_select.set_visibility(aliyun_only)
        if self._bill_granularity is not None:
            self._bill_granularity.set_visibility(aliyun_only)
        platform_name = PLATFORM_OPTIONS.get(
            platform, platform,
        )
        safe_notify(
            self._container,
            f'监控面板已切换到 {platform_name}',
            type='info',
        )
        # 切换平台后自动触发数据拉取
        self._on_refresh()

    # --------------------------------------------------
    # UI 构建
    # --------------------------------------------------
    def _build_ui(self) -> None:
        """构建监控面板 UI 布局."""
        container = ui.card().classes('w-full p-4 gap-2')
        self._container = container
        with container:
            ui.label('监控面板').classes(
                'text-lg font-bold',
            )
            with ui.row().classes('items-center gap-2'):
                self._btn_refresh = ui.button(
                    '刷新监控数据',
                    on_click=self._on_refresh,
                    icon='refresh',
                ).classes('w-48')
                self._refresh_spinner = ui.spinner(
                    size='md',
                ).set_visibility(False)

            # 两列卡片行: 余额 + 监控
            with ui.row().classes(
                'w-full gap-4 items-stretch',
            ):
                with ui.card().classes(
                    'flex-1 p-4 gap-2',
                ):
                    ui.label('账户余额').classes(
                        'text-base font-bold',
                    )
                    self._balance_col = (
                        ui.column().classes('w-full gap-1')
                    )
                with ui.card().classes(
                    'flex-1 p-4 gap-2',
                ):
                    ui.label('知识库监控').classes(
                        'text-base font-bold',
                    )
                    self._monitor_col = (
                        ui.column().classes('w-full gap-1')
                    )

            # 全宽账单卡片: 消费明细 + 资金流水双子页签.
            with ui.card().classes('w-full p-4 gap-2'):
                ui.label('账单与流水').classes(
                    'text-base font-bold',
                )
                with ui.tabs().classes('w-full') as bill_tabs:
                    tab_consumption = ui.tab('消费明细')
                    tab_flow = ui.tab('资金流水')
                with ui.tab_panels(bill_tabs).classes('w-full'):
                    with ui.tab_panel(tab_consumption):
                        self._build_consumption_tab()
                    with ui.tab_panel(tab_flow):
                        self._tx_table = ui.table(
                            columns=_BILL_COLUMNS,
                            rows=[],
                            row_key='record_id',
                        ).classes('w-full')

        # 定时刷新按钮灰化状态
        ui.timer(0.5, self._refresh_btn_state)

    def _build_consumption_tab(self) -> None:
        """构建消费明细页签: 控件行 + 汇总条 + 表格."""
        cycles = self._bill_cycle_options()
        with ui.row().classes('items-end gap-3'):
            # 默认账期取本月 (列表首项); 当月含未出账盲区,
            # 由下方延迟提示小字说明.
            self._bill_cycle_select = ui.select(
                options=cycles,
                value=cycles[0],
                label='账期月份',
            ).classes('w-32')
            self._bill_granularity = ui.toggle(
                options=_GRANULARITY_OPTIONS,
                value='MONTHLY',
                on_change=self._on_granularity_change,
            )
        self._bill_summary_row = ui.row().classes(
            'w-full gap-4 text-sm',
        )
        self._bill_status_label = ui.label().classes(
            'text-xs text-negative',
        )
        self._instance_table = ui.table(
            columns=_INSTANCE_BILL_COLUMNS,
            rows=[],
            row_key='key',
        ).classes('w-full')
        # 退款/调账行金额列标色区分.
        self._instance_table.add_slot(
            'body-cell-bill_type',
            r'''
            <q-td :props="props">
                <div :class="['退款', '调账']
                    .includes(props.value)
                    ? 'text-green-600 font-medium' : ''">
                    {{ props.value }}
                </div>
            </q-td>
            ''',
        )
        ui.label(
            '账单数据延迟约 24 小时，当月数据仅供参考',
        ).classes('text-xs text-gray-400')

    @staticmethod
    def _bill_cycle_options() -> list[str]:
        """生成近 18 个可选账期月份列表 (按月降序).

        Returns:
            'YYYY-MM' 格式账期列表, 首项为当月.
        """
        now = datetime.now()
        options: list[str] = []
        for offset in range(_BILL_CYCLE_MONTHS):
            year = now.year
            month = now.month - offset
            while month <= 0:
                month += 12
                year -= 1
            options.append(f'{year:04d}-{month:02d}')
        return options

    # --------------------------------------------------
    # 刷新回调 (后台任务五段式)
    # --------------------------------------------------
    def _on_refresh(self) -> None:
        """刷新按钮回调: 校验后启动后台数据拉取."""
        # 段一: 防重入
        if self._running:
            return
        # 段二: 快照平台
        platform = self._platform
        # 段三: 校验
        if not platform:
            safe_notify(
                self._container,
                '请先选择目标平台',
                type='warning',
            )
            return
        missing = missing_config_items(
            self._config_store, platform,
        )
        if missing:
            safe_notify(
                self._container,
                '请先填写必要配置项: '
                + ', '.join(missing),
                type='warning',
            )
            return
        # 段四: 显示加载指示器
        if self._refresh_spinner is not None:
            self._refresh_spinner.set_visibility(True)
        # 段五: 快照消费明细查询参数 (账期/粒度)
        cycle, granularity = self._snapshot_bill_state()
        # 段六: 启动后台任务
        self._running = True
        self._run_id += 1
        run_id = self._run_id
        # 段七: 后台协程
        background_tasks.create(
            self._run_refresh(
                platform, run_id, cycle, granularity,
            ),
            name='monitor refresh',
        )

    def _snapshot_bill_state(self) -> tuple[str, str]:
        """快照当前消费明细查询参数.

        Returns:
            (账期 'YYYY-MM', 粒度 MONTHLY/DAILY) 元组;
            未设置时回退默认本月与按月粒度.
        """
        cycles = self._bill_cycle_options()
        cycle = (
            self._bill_cycle_select.value
            if self._bill_cycle_select is not None
            else None
        )
        granularity = (
            self._bill_granularity.value
            if self._bill_granularity is not None
            else None
        )
        return (
            cycle if cycle in cycles else cycles[0],
            granularity
            if granularity in _GRANULARITY_OPTIONS
            else 'MONTHLY',
        )

    async def _run_refresh(
        self,
        platform: str,
        run_id: int,
        bill_cycle: str,
        granularity: str,
    ) -> None:
        """后台拉取各类监控数据并渲染.

        消费明细单独拉取并独立降级, 失败不影响余额/监控/
        资金流水的展示.

        Args:
            platform: 目标平台标识快照.
            run_id: 启动时的运行代次号快照.
            bill_cycle: 消费明细账期快照.
            granularity: 消费明细粒度快照.
        """
        start_time = time.perf_counter()
        logger.info(
            '监控数据刷新开始 | platform={}', platform,
        )
        try:
            balance, monitor, txs = (
                await self._fetch_all(platform)
            )
            # 代次校验: 新刷新已启动则丢弃陈旧结果.
            if run_id != self._run_id:
                return
            self._render_balance(balance)
            self._render_monitor(monitor)
            self._render_transactions(txs)
            # 消费明细: 独立降级, 失败不影响已渲染区域.
            if platform == 'aliyun':
                await self._refresh_instance_bills(
                    run_id, bill_cycle, granularity,
                )
            elapsed = time.perf_counter() - start_time
            logger.info(
                '监控数据刷新完成 | platform={} '
                '| 耗时 {:.1f}s',
                platform, elapsed,
            )
            safe_notify(
                self._container,
                '监控数据刷新完成',
                type='positive',
            )
        except Exception as exc:
            logger.exception(
                '监控数据刷新失败 | platform={} | {}',
                platform, exc,
            )
            safe_notify(
                self._container,
                f'刷新失败: {error_summary(exc)}',
                type='negative',
            )
        finally:
            self._running = False
            if self._refresh_spinner is not None:
                self._refresh_spinner.set_visibility(False)

    async def _refresh_instance_bills(
        self,
        run_id: int,
        billing_cycle: str,
        granularity: str,
    ) -> None:
        """独立拉取并渲染消费明细, 失败降级展示.

        Args:
            run_id: 本次刷新的运行代次号.
            billing_cycle: 账期 'YYYY-MM'.
            granularity: 聚合粒度 (MONTHLY/DAILY).
        """
        try:
            kwargs = (
                self._config_store.get_aliyun_client_kwargs()
            )
            client = AliyunKnowledgeClient(
                **kwargs,  # type: ignore[arg-type]
            )
            if granularity == 'DAILY':
                items = await (
                    client.describe_instance_bill_daily_month(
                        billing_cycle,
                    )
                )
            else:
                items = await client.describe_instance_bill(
                    billing_cycle,
                )
            error: Exception | None = None
        except Exception as exc:
            logger.exception(
                '消费明细拉取失败 | cycle={} | granularity={}'
                ' | {}',
                billing_cycle, granularity, exc,
            )
            items, error = [], exc
        if run_id != self._run_id:
            return
        self._render_instance_bills(items, error)

    # --------------------------------------------------
    # 数据拉取
    # --------------------------------------------------
    async def _fetch_all(
        self, platform: str,
    ) -> tuple[
        BalanceInfo,
        KbMonitorSummary,
        list[BillDetailItem],
    ]:
        """并行拉取余额、监控、资金流水三类数据.

        Args:
            platform: 目标平台标识.

        Returns:
            (余额信息, 监控摘要, 资金流水列表) 元组.
        """
        if platform == 'volc':
            return await self._fetch_volc(platform)
        return await self._fetch_aliyun(platform)

    async def _fetch_aliyun(
        self, platform: str,
    ) -> tuple[
        BalanceInfo,
        KbMonitorSummary,
        list[BillDetailItem],
    ]:
        """阿里云平台: 并行拉取三类数据.

        Args:
            platform: 平台标识.

        Returns:
            (余额, 监控摘要, 资金流水) 元组.
        """
        kwargs = self._config_store.get_aliyun_client_kwargs()
        client = AliyunKnowledgeClient(
            **kwargs,  # type: ignore[arg-type]
        )
        now = datetime.now()
        month_start = now.replace(
            day=1, hour=0, minute=0,
            second=0, microsecond=0,
        )
        start_ts = int(month_start.timestamp())
        end_ts = int(now.timestamp())
        start_str = month_start.strftime('%Y-%m-%d')
        end_str = now.strftime('%Y-%m-%d')

        results = await asyncio.gather(
            client.query_account_balance(),
            client.get_index_monitor(
                start_ts, end_ts,
            ),
            client.query_account_transaction_details(
                start_str, end_str,
            ),
            client.get_index_doc_count(),
            return_exceptions=True,
        )
        # 检查各协程结果，首个异常即抛出
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(
                    '阿里云监控数据拉取失败'
                    ' | task_index={} | {}',
                    i, r,
                )
                raise r
        (
            balance, monitor_raw,
            txs, doc_count,
        ) = results  # type: ignore[misc]
        monitor = self._parse_aliyun_monitor(
            monitor_raw, platform, doc_count,
        )
        return balance, monitor, txs

    async def _fetch_volc(
        self, platform: str,
    ) -> tuple[
        BalanceInfo,
        KbMonitorSummary,
        list[BillDetailItem],
    ]:
        """火山引擎平台: 并行拉取三类数据.

        Args:
            platform: 平台标识.

        Returns:
            (余额, 监控摘要, 账单明细) 元组.
        """
        kwargs = (
            self._config_store.get_volc_client_kwargs()
        )
        client = VikingKnowledgeClient(
            **kwargs,  # type: ignore[arg-type]
        )
        bill_period = datetime.now().strftime('%Y-%m')

        results = await asyncio.gather(
            client.query_account_balance(),
            client.get_collection_info(),
            client.query_bill_details(bill_period),
            return_exceptions=True,
        )
        # 检查各协程结果，首个异常即抛出
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(
                    '火山引擎监控数据拉取失败'
                    ' | task_index={} | {}',
                    i, r,
                )
                raise r
        balance, coll_info, bills = results  # type: ignore[misc]
        monitor = self._parse_volc_monitor(
            coll_info, platform,
        )
        return balance, monitor, bills

    # --------------------------------------------------
    # 监控数据解析
    # --------------------------------------------------
    @staticmethod
    def _parse_aliyun_monitor(
        data: dict,
        platform: str,
        doc_count: int | Exception | None = None,
    ) -> KbMonitorSummary:
        """将阿里云 IndexMonitor 响应解析为监控摘要.

        Args:
            data: get_index_monitor 返回的 dict.
            platform: 平台标识.
            doc_count: 文档总数 (来自
                get_index_doc_count), 异常或 None
                时显示为 None.

        Returns:
            知识库监控摘要 DTO.
        """
        if not data:
            return KbMonitorSummary(
                platform=platform,  # type: ignore[arg-type]
                kb_type='未知',
                storage_limit_gb=0.0,
                storage_usage_gb=0.0,
                doc_num=(
                    doc_count if isinstance(doc_count, int)
                    else None
                ),
                point_num=None,
                create_time=None,
                update_time=None,
            )
        kb_type_raw = data.get(
            'pipelineCommercialType', '',
        )
        kb_type = (
            '标准版' if kb_type_raw == 'standard'
            else '旗舰版' if kb_type_raw == 'enterprise'
            else str(kb_type_raw)
        )
        storage = data.get('storageMonitorData') or {}
        if isinstance(storage, str):
            storage = json.loads(storage)
        limit_gb = float(
            storage.get('indexStorageLimit', 0)
        )
        usage_gb = float(
            storage.get('indexStorageUsage', 0)
        )
        # doc_count 可能为异常对象, 仅取 int
        resolved_doc = (
            doc_count if isinstance(doc_count, int)
            else None
        )
        return KbMonitorSummary(
            platform=platform,  # type: ignore[arg-type]
            kb_type=kb_type,
            storage_limit_gb=limit_gb,
            storage_usage_gb=usage_gb,
            doc_num=resolved_doc,
            point_num=None,
            create_time=None,
            update_time=None,
        )

    @staticmethod
    def _parse_volc_monitor(
        data: dict, platform: str,
    ) -> KbMonitorSummary:
        """将火山引擎 collection_info 解析为监控摘要.

        Args:
            data: get_collection_info 返回的 dict.
            platform: 平台标识.

        Returns:
            知识库监控摘要 DTO.
        """
        if not data:
            return KbMonitorSummary(
                platform=platform,  # type: ignore[arg-type]
                kb_type='未知',
                storage_limit_gb=0.0,
                storage_usage_gb=0.0,
                doc_num=None,
                point_num=None,
                create_time=None,
                update_time=None,
            )
        # 知识库规格: version 1=免费版, 2=标准版, 4=旗舰版
        version = data.get('version')
        version_map = {1: '免费版', 2: '标准版', 4: '旗舰版'}
        kb_type = version_map.get(
            version,
            str(version) if version else '未知',
        )
        # 文档数
        doc_num = data.get('doc_num')
        if doc_num is not None:
            doc_num = int(doc_num)
        # 切片数: 从 pipeline_list 首个 pipeline_stat 获取
        point_num: int | None = None
        pipelines = data.get('pipeline_list') or []
        if pipelines:
            stat = pipelines[0].get('pipeline_stat') or {}
            raw = stat.get('point_num')
            if raw is not None:
                point_num = int(raw)
        # 时间戳转可读日期
        create_time = _format_ts(data.get('create_time'))
        update_time = _format_ts(data.get('update_time'))
        return KbMonitorSummary(
            platform=platform,  # type: ignore[arg-type]
            kb_type=kb_type,
            storage_limit_gb=0.0,
            storage_usage_gb=0.0,
            doc_num=doc_num,
            point_num=point_num,
            create_time=create_time,
            update_time=update_time,
        )

    # --------------------------------------------------
    # 卡片渲染
    # --------------------------------------------------
    def _render_balance(
        self, info: BalanceInfo,
    ) -> None:
        """渲染账户余额卡片.

        Args:
            info: 账户余额 DTO.
        """
        if self._balance_col is None:
            return
        self._balance_col.clear()
        with self._balance_col:
            self._field_row(
                '可用额度',
                f'{info.available_amount} {info.currency}',
            )
            self._field_row(
                '现金余额',
                f'{info.cash_amount} {info.currency}',
            )
            self._field_row(
                '信控额度',
                f'{info.credit_amount} {info.currency}',
            )
            self._field_row('币种', info.currency)

    def _render_monitor(
        self,
        summary: KbMonitorSummary,
    ) -> None:
        """渲染知识库监控卡片.

        Args:
            summary: 知识库监控摘要 DTO.
        """
        if self._monitor_col is None:
            return
        self._monitor_col.clear()
        with self._monitor_col:
            self._field_row(
                '知识库规格', summary.kb_type or '-',
            )
            # 存储用量进度条
            if summary.storage_limit_gb > 0:
                ratio = (
                    summary.storage_usage_gb
                    / summary.storage_limit_gb
                )
                pct = min(ratio * 100, 100)
                self._field_row(
                    '存储用量',
                    f'{summary.storage_usage_gb:.2f} / '
                    f'{summary.storage_limit_gb:.1f} GB',
                )
                bar_color = (
                    'warning' if pct > 80 else 'primary'
                )
                ui.linear_progress(
                    value=pct / 100,
                    show_value=False,
                ).classes('w-full').props(
                    f'color={bar_color}'
                )
            elif summary.storage_usage_gb > 0:
                self._field_row(
                    '存储用量',
                    f'{summary.storage_usage_gb:.2f} GB',
                )
            else:
                self._field_row('存储用量', '-')
            # 文档数 / 切片数
            doc_text = (
                str(summary.doc_num)
                if summary.doc_num is not None
                else '-'
            )
            self._field_row('文档数', doc_text)
            point_text = (
                str(summary.point_num)
                if summary.point_num is not None
                else '-'
            )
            self._field_row('切片数', point_text)
            # 创建 / 更新时间
            self._field_row(
                '创建时间',
                summary.create_time or '-',
            )
            self._field_row(
                '更新时间',
                summary.update_time or '-',
            )

    def _render_transactions(
        self, items: list[BillDetailItem],
    ) -> None:
        """渲染资金流水表格.

        Args:
            items: 资金流水明细 DTO 列表.
        """
        if self._tx_table is None:
            return
        rows = [
            {
                'record_id': item.record_id,
                'date': item.date,
                'product': item.product,
                'amount': item.amount,
                'payment_method': item.payment_method,
                'remark': item.remark,
            }
            for item in items
        ]
        self._tx_table.rows = rows

    def _render_instance_bills(
        self,
        items: list[InstanceBillItem],
        error: Exception | None,
    ) -> None:
        """渲染消费明细汇总条、状态行与表格.

        Args:
            items: 账单条目列表, 失败时为空列表.
            error: 拉取异常, 为 None 表示成功.
        """
        if self._instance_table is None:
            return
        total_pretax = sum(i.pretax_amount for i in items)
        total_payment = sum(i.payment_amount for i in items)
        if self._bill_summary_row is not None:
            self._bill_summary_row.clear()
            with self._bill_summary_row:
                ui.label(
                    f'合计应付: {total_pretax:.2f}',
                ).classes('font-bold')
                ui.label(
                    f'合计现金支付: {total_payment:.2f}',
                )
                ui.label(f'条目数: {len(items)}')
        if self._bill_status_label is not None:
            self._bill_status_label.text = (
                f'消费明细拉取失败: {error_summary(error)}'
                if error else ''
            )
        rows = []
        for index, item in enumerate(items):
            instance = item.instance_id or '-'
            if item.billing_item:
                instance = (
                    f'{instance} / {item.billing_item}'
                )
            rows.append({
                'key': str(index),
                'date': (
                    item.billing_date or item.billing_cycle
                ),
                'product': item.product_detail,
                'instance': instance,
                'bill_type': _ITEM_TYPE_LABELS.get(
                    item.item_type, item.item_type,
                ),
                'pretax': f'{item.pretax_amount:.2f}',
                'discount': f'{item.invoice_discount:.2f}',
                'payment': f'{item.payment_amount:.2f}',
            })
        self._instance_table.rows = rows

    # --------------------------------------------------
    # 辅助渲染
    # --------------------------------------------------
    @staticmethod
    def _field_row(
        label: str, value: str,
    ) -> None:
        """渲染单行字段标签-值对.

        Args:
            label: 字段标签.
            value: 字段值.
        """
        with ui.row().classes('items-center gap-2'):
            ui.label(label).classes(
                'text-sm text-gray-400 w-20',
            )
            ui.label(value).classes('text-sm')

    # --------------------------------------------------
    # 清空与状态
    # --------------------------------------------------
    def _clear_all_cards(self) -> None:
        """清空所有卡片数据."""
        if self._balance_col is not None:
            self._balance_col.clear()
        if self._monitor_col is not None:
            self._monitor_col.clear()
        if self._tx_table is not None:
            self._tx_table.rows = []
        if self._instance_table is not None:
            self._instance_table.rows = []
        if self._bill_summary_row is not None:
            self._bill_summary_row.clear()
        if self._bill_status_label is not None:
            self._bill_status_label.text = ''

    def _on_granularity_change(self) -> None:
        """粒度切换回调: 先清空旧数据再触发刷新."""
        # 清空消费明细表格、汇总条与状态行,
        # 防止用户看到旧粒度的残留数据.
        if self._instance_table is not None:
            self._instance_table.rows = []
        if self._bill_summary_row is not None:
            self._bill_summary_row.clear()
        if self._bill_status_label is not None:
            self._bill_status_label.text = ''
        self._on_refresh()

    def _refresh_btn_state(self) -> None:
        """根据 _running 状态刷新按钮灰化."""
        if self._btn_refresh is None:
            return
        if self._running:
            self._btn_refresh.disable()
        else:
            self._btn_refresh.enable()
