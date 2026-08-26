"""监控面板: 账户余额 + 知识库监控 + 本月交易明细.

提供阿里云百炼与火山引擎两个平台的账户余额查询、
知识库存储监控与本月账单明细展示. 后台并行拉取三类
数据, 各自独立渲染到对应卡片区域.
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


# 账单表格列定义.
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


class MonitorPanel:
    """监控面板: 账户余额 + 知识库监控 + 本月交易明细.

    Attributes:
        _config_store: GUI 配置持久化存储实例.
        _platform: 当前目标平台标识 (aliyun/volc).
        _running: 后台刷新任务是否进行中.
        _run_id: 运行代次号, 防止旧任务渲染.
        _container: 面板根容器.
        _btn_refresh: 刷新按钮.
        _balance_col: 余额卡片内容容器.
        _monitor_col: 监控卡片内容容器.
        _bill_table: 账单表格组件.
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
        self._bill_table: ui.table | None = None
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
            self._btn_refresh = ui.button(
                '刷新监控数据',
                on_click=self._on_refresh,
                icon='refresh',
            ).classes('w-48')

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

            # 全宽账单表格卡片
            with ui.card().classes('w-full p-4 gap-2'):
                ui.label('本月交易明细').classes(
                    'text-base font-bold',
                )
                self._bill_table = ui.table(
                    columns=_BILL_COLUMNS,
                    rows=[],
                    row_key='record_id',
                ).classes('w-full')

        # 定时刷新按钮灰化状态
        ui.timer(0.5, self._refresh_btn_state)

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
        # 段四: 启动后台任务
        self._running = True
        self._run_id += 1
        run_id = self._run_id
        # 段五: 后台协程
        background_tasks.create(
            self._run_refresh(platform, run_id),
            name='monitor refresh',
        )

    async def _run_refresh(
        self,
        platform: str,
        run_id: int,
    ) -> None:
        """后台并行拉取三类监控数据并渲染.

        Args:
            platform: 目标平台标识快照.
            run_id: 启动时的运行代次号快照.
        """
        start_time = time.perf_counter()
        logger.info(
            '监控数据刷新开始 | platform={}', platform,
        )
        try:
            balance, monitor, bills = (
                await self._fetch_all(platform)
            )
            elapsed = time.perf_counter() - start_time
            logger.info(
                '监控数据刷新完成 | platform={} '
                '| 耗时 {:.1f}s',
                platform, elapsed,
            )
            # 代次校验
            if run_id != self._run_id:
                return
            self._render_balance(balance)
            self._render_monitor(monitor)
            self._render_bills(bills)
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
        """并行拉取余额、监控、账单三类数据.

        Args:
            platform: 目标平台标识.

        Returns:
            (余额信息, 监控摘要, 账单明细列表) 元组.
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
            (余额, 监控摘要, 账单明细) 元组.
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
            bills, doc_count,
        ) = results  # type: ignore[misc]
        monitor = self._parse_aliyun_monitor(
            monitor_raw, platform, doc_count,
        )
        return balance, monitor, bills

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
        kb_type_raw = data.get(
            'pipelineCommercialType', '',
        )
        kb_type = (
            '标准版' if kb_type_raw == 'standard'
            else '旗舰版' if kb_type_raw == 'enterprise'
            else str(kb_type_raw)
        )
        storage = data.get('storageMonitorData', {})
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

    def _render_bills(
        self, items: list[BillDetailItem],
    ) -> None:
        """渲染账单明细表格.

        Args:
            items: 账单明细 DTO 列表.
        """
        if self._bill_table is None:
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
        self._bill_table.rows = rows

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
        if self._bill_table is not None:
            self._bill_table.rows = []

    def _refresh_btn_state(self) -> None:
        """根据 _running 状态刷新按钮灰化."""
        if self._btn_refresh is None:
            return
        if self._running:
            self._btn_refresh.disable()
        else:
            self._btn_refresh.enable()
