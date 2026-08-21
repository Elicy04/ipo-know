"""配置编辑面板 + 视频演示弹窗.

提供阿里云百炼知识库连接参数的可视化编辑界面,
支持保存到本地 JSON 配置、连通性测试以及视频演示播放.
"""

from collections.abc import Callable

from loguru import logger
from nicegui import background_tasks
from nicegui import ui

from ipo_know.clients.aliyun_knowledge.client import AliyunKnowledgeClient
from ipo_know.config.config import AliyunKnowledgeSettings
from ipo_know.ui.config_store import GUIConfigStore


# 连通性测试前必须填写的表单字段: (字段名, 展示名).
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


def _stripped_value(value: object) -> object:
    """清理表单值: 字符串去除首尾空白, 其他类型原样返回.

    粘贴自控制台的 AK/SK 等值可能带入空格、换行或
    制表符, 会导致 API 签名校验失败, 故统一清理.

    Args:
        value: 表单组件的当前值.

    Returns:
        字符串类型时返回去除首尾空白后的值, 其余
        类型(如数值)原样返回.
    """
    if isinstance(value, str):
        return value.strip()
    return value


class ConfigPanel:
    """阿里云知识库配置编辑面板.

    以 NiceGUI ui.card 为容器, 竖排展示 AK/SK 等
    常用表单字段, 低频配置项折叠在"高级配置"中,
    标题行右侧提供"连通性测试"按钮, 底部提供
    "保存配置"与"获取视频演示"两个操作按钮.

    Attributes:
        _store: GUI 配置持久化存储实例.
        _is_running: 判断是否有后台任务正在执行的回调.
        _fields: 表单输入组件字典, key 为配置字段名.
        _testing: 连通性测试后台任务是否进行中.
    """

    def __init__(
        self,
        config_store: GUIConfigStore,
        is_running: Callable[[], bool],
    ) -> None:
        """初始化配置面板.

        Args:
            config_store: 配置持久化存储实例.
            is_running: 判断后台任务是否运行中的回调函数.
        """
        self._store = config_store
        self._is_running = is_running
        self._fields: dict[str, ui.input | ui.number] = {}
        self._save_btn: ui.button | None = None
        self._test_btn: ui.button | None = None
        self._testing: bool = False
        self._build_ui()
        self._load_from_store()

    # --------------------------------------------------
    # UI 构建
    # --------------------------------------------------
    def _build_ui(self) -> None:
        """构建面板 UI 布局."""
        with ui.card().classes('w-full p-4 gap-2'):
            # 标题行: 左侧标题, 右侧连通性测试按钮
            with ui.row().classes(
                'w-full items-center mb-2 gap-2'
            ):
                ui.label('阿里云百炼配置').classes(
                    'text-lg font-bold'
                )
                self._test_btn = ui.button(
                    '连通性测试',
                    on_click=self._on_test_connection,
                    icon='network_check',
                ).props('dense outline').classes('ml-auto')

            self._fields['ak'] = (
                ui.input(label='AK (AccessKey ID)')
                .classes('w-full')
                .tooltip('阿里云 AccessKey ID')
            )
            self._fields['sk'] = (
                ui.input(label='SK (AccessKey Secret)', password=True)
                .classes('w-full')
                .tooltip('阿里云 AccessKey Secret')
            )
            self._fields['workspace_id'] = (
                ui.input(label='Workspace ID')
                .classes('w-full')
                .tooltip('百炼工作空间 ID')
            )
            self._fields['index_id'] = (
                ui.input(label='Index ID')
                .classes('w-full')
                .tooltip('知识库索引 ID')
            )

            # 低频配置项折叠到高级配置, 默认收起
            with ui.expansion('高级配置').classes('w-full'):
                self._fields['endpoint'] = (
                    ui.input(label='Endpoint')
                    .classes('w-full')
                    .tooltip('百炼 API 接入点地址')
                )
                self._fields['region_id'] = (
                    ui.input(label='Region ID')
                    .classes('w-full')
                    .tooltip('阿里云区域标识, 如 cn-beijing')
                )
                self._fields['category_id'] = (
                    ui.input(label='Category ID')
                    .classes('w-full')
                    .tooltip('文档类目 ID, 默认 default')
                )
                self._fields['parser'] = (
                    ui.input(label='Parser')
                    .classes('w-full')
                    .tooltip('文档解析器, 如 DASHSCOPE_DOCMIND')
                )
                self._fields['timeout'] = (
                    ui.number(label='Timeout (秒)', value=30, min=1)
                    .classes('w-full')
                    .tooltip('API 请求超时时间(秒)')
                )

            # 字符串输入框失焦/粘贴后即时去除首尾空白
            for field in self._fields.values():
                if isinstance(field, ui.input):
                    field.on('change', self._on_field_change)

            with ui.row().classes('w-full mt-2 gap-2'):
                self._save_btn = ui.button(
                    '保存配置',
                    on_click=self._on_save,
                    icon='save',
                ).classes('flex-1')

                ui.button(
                    '配置参数教程',
                    on_click=self._open_video_dialog,
                    icon='video_library',
                ).classes('flex-1')

        # 定时刷新保存/测试按钮的灰化状态
        ui.timer(0.5, self._refresh_btn_states)

    # --------------------------------------------------
    # 数据加载 / 保存
    # --------------------------------------------------
    def _load_from_store(self) -> None:
        """从 config_store 加载配置并填充表单."""
        data = self._store.load()
        ak_cfg: dict[str, object] = data.get(
            'aliyun_knowledge', {}
        )  # type: ignore[assignment]
        for key, field in self._fields.items():
            if key in ak_cfg:
                field.value = ak_cfg[key]

    def _collect_form_values(self) -> dict[str, object]:
        """收集表单当前值组成配置字典.

        字符串字段值统一去除首尾空白, 数值字段保持
        number 组件的原生类型.

        Returns:
            包含 aliyun_knowledge 全部字段的嵌套字典.
        """
        values: dict[str, object] = {}
        for key, field in self._fields.items():
            values[key] = _stripped_value(field.value)
        return {'aliyun_knowledge': values}

    def _on_field_change(self, event: object) -> None:
        """输入框变更事件回调: 回写去除首尾空白后的值.

        Args:
            event: NiceGUI 触发的事件对象, 其 ``sender``
                属性为触发事件的输入组件.
        """
        sender = getattr(event, 'sender', None)
        if not isinstance(sender, ui.input):
            return
        cleaned = _stripped_value(sender.value)
        if cleaned != sender.value:
            sender.value = cleaned

    async def _on_save(self) -> None:
        """保存配置按钮回调."""
        if self._is_running() or self._testing:
            return
        try:
            data = self._collect_form_values()
            self._store.save(data)
            ui.notify('配置已保存', type='positive')
        except Exception as exc:
            ui.notify(f'保存失败: {exc}', type='negative')

    # --------------------------------------------------
    # 连通性测试
    # --------------------------------------------------
    def _missing_required(self) -> list[str]:
        """检查表单中必填项, 返回缺失项的展示名列表.

        Returns:
            缺失的必填配置项展示名列表, 空列表表示均已填写.
        """
        missing: list[str] = []
        for key, label in _REQUIRED_FIELDS:
            field = self._fields.get(key)
            value = field.value if field is not None else None
            if not str(value or '').strip():
                missing.append(label)
        return missing

    def _on_test_connection(self) -> None:
        """连通性测试按钮回调: 校验后启动后台测试任务."""
        if self._is_running() or self._testing:
            return
        missing = self._missing_required()
        if missing:
            ui.notify(
                '请先填写必要配置项: ' + ', '.join(missing),
                type='warning',
            )
            return
        values = {
            key: _stripped_value(field.value)
            for key, field in self._fields.items()
        }
        self._testing = True
        if self._test_btn is not None:
            self._test_btn.props('loading')
        background_tasks.create(
            self._run_connection_test(values),
            name='aliyun connection test',
        )

    async def _run_connection_test(
        self, values: dict[str, object]
    ) -> None:
        """后台执行连通性测试并反馈结果.

        以当前表单值构造配置与客户端, 发起轻量只读
        API 调用; 成功/失败均通过弹窗与日志反馈.

        Args:
            values: 表单当前值组成的扁平配置字典.
        """
        try:
            cfg = AliyunKnowledgeSettings(**values)  # type: ignore[arg-type]
            client = AliyunKnowledgeClient(config=cfg)
            await client.check_connection()
        except Exception as exc:
            logger.exception('阿里云连通性测试失败')
            ui.notify(
                f'连接失败: {_error_summary(exc)}',
                type='negative',
            )
        else:
            logger.info('阿里云连通性测试成功')
            ui.notify('阿里云连接成功', type='positive')
        finally:
            self._testing = False
            if self._test_btn is not None:
                self._test_btn.props(remove='loading')

    # --------------------------------------------------
    # 按钮状态管理
    # --------------------------------------------------
    def _refresh_btn_states(self) -> None:
        """根据后台任务状态刷新保存/测试按钮灰化."""
        busy = self._is_running() or self._testing
        if self._save_btn is not None:
            if busy:
                self._save_btn.disable()
            else:
                self._save_btn.enable()
        if self._test_btn is not None:
            if busy:
                self._test_btn.disable()
            else:
                self._test_btn.enable()

    # --------------------------------------------------
    # 视频演示弹窗
    # --------------------------------------------------
    def _open_video_dialog(self) -> None:
        """打开视频演示弹窗."""
        with ui.dialog() as dlg, ui.card().classes('w-[640px]'):
            ui.label('操作演示视频').classes('text-lg font-bold')
            ui.video('/assets/demo.mp4').classes('w-full')
            ui.button('关闭', on_click=dlg.close).classes(
                'mt-2 self-end'
            )
        dlg.open()
