"""配置编辑面板.

提供阿里云百炼与火山引擎 VikingDB 知识库连接参数的
可视化编辑界面, 支持保存到本地 JSON 配置、连通性测试,
并按操作面板的目标平台选择联动显隐对应配置卡片.
"""

import webbrowser
from collections.abc import Callable

from loguru import logger
from nicegui import background_tasks
from nicegui import ui

from ipo_know.clients.aliyun_knowledge.client import AliyunKnowledgeClient
from ipo_know.clients.viking_knowledge import VikingKnowledgeClient
from ipo_know.config.config import AliyunKnowledgeSettings
from ipo_know.config.config import VikingKnowledgeSettings
from ipo_know.ui.config_store import GUIConfigStore
from ipo_know.ui.panel_helpers import error_summary
from ipo_know.ui.panel_helpers import safe_notify


# 阿里云连通性测试前必须填写的表单字段: (字段名, 展示名).
_REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ('ak', 'AK'),
    ('sk', 'SK'),
    ('workspace_id', 'Workspace ID'),
    ('index_id', 'Index ID'),
)

# 火山引擎连通性测试前必须填写的凭证字段: (字段名, 展示名).
# 另需 Resource ID 与 Collection Name 至少其一, 单独校验.
_VOLC_REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ('ak', 'AK'),
    ('sk', 'SK'),
)

# timeout 数值框的缺省回退值, 与两个平台配置的默认值一致.
_DEFAULT_TIMEOUT = 30

# 阿里云百炼知识库控制台地址.
_ALIYUN_CONSOLE_URL = (
    'https://bailian.console.aliyun.com/cn-beijing'
    '?tab=app#/app-market/suggest'
)

# 火山引擎知识库控制台地址.
_VOLC_CONSOLE_URL = (
    'https://console.volcengine.com/ark/region:cn-beijing'
    '/knowledge/collection/list'
)


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


def _normalized_timeout(value: object) -> int:
    """规整 timeout 数值输入, 空值回退默认值.

    ``ui.number`` 清空后 value 为 None, 若原样落盘会在
    load 合并时以显式 None 覆盖默认值, 导致后续构造
    settings 对象报 ValidationError 且错误配置被持久化,
    故非数值一律回退 ``_DEFAULT_TIMEOUT``.

    Args:
        value: timeout 数值框的当前值.

    Returns:
        规整后的 int 超时秒数.
    """
    if isinstance(value, bool):
        return _DEFAULT_TIMEOUT
    if isinstance(value, (int, float)):
        return int(value)
    return _DEFAULT_TIMEOUT


class ConfigPanel:
    """知识库平台配置编辑面板 (阿里云 + 火山引擎).

    以 NiceGUI ui.card 为容器, 竖排展示两个平台的配置卡片,
    卡片内部按功能分区 (基本配置/同步配置/检索配置/问答
    配置): 基本配置收纳各功能共有项, 阿里云的 endpoint/
    region_id 低频项折叠在基本配置内的"高级配置"中;
    各卡片标题行右侧提供独立的"连通性测试"按钮, 卡片
    底部提供一个"保存配置"按钮 (整卡全分区一次保存,
    仅保存本平台段), 保存按钮下方提供"打开知识库控制台"
    快捷跳转按钮 (与后台任务无关, 始终可用). 两卡片按
    全局目标平台联动显隐.

    Attributes:
        _store: GUI 配置持久化存储实例.
        _is_running: 判断是否有后台任务正在执行的回调.
        _fields: 阿里云表单输入组件字典, key 为配置字段名.
        _volc_fields: 火山引擎表单输入组件字典.
        _aliyun_card: 阿里云配置卡片根容器.
        _volc_card: 火山引擎配置卡片根容器.
        _testing: 阿里云连通性测试后台任务是否进行中.
        _volc_testing: 火山引擎连通性测试后台任务是否进行中.
        _container: 面板根容器, 供后台任务恢复 UI 上下文.
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
        self._volc_fields: dict[str, ui.input | ui.number] = {}
        self._aliyun_save_btn: ui.button | None = None
        self._volc_save_btn: ui.button | None = None
        self._test_btn: ui.button | None = None
        self._volc_test_btn: ui.button | None = None
        self._aliyun_card: ui.card | None = None
        self._volc_card: ui.card | None = None
        self._testing: bool = False
        self._volc_testing: bool = False
        self._container: ui.card | None = None
        self._build_ui()
        self._load_from_store()
        # 默认与操作平台下拉缺省值一致: 仅显示阿里云卡片
        self.set_platform('aliyun')

    # --------------------------------------------------
    # 公开接口
    # --------------------------------------------------
    def set_platform(self, platform: str) -> None:
        """按目标平台联动显隐两个平台的配置卡片.

        卡片内部折叠区展开状态随容器整体隐藏保留, 切回
        平台时不重置.

        Args:
            platform: 平台标识 (aliyun/volc). 值为 'aliyun'
                时显示阿里云卡片, 否则显示火山引擎卡片.
        """
        show_aliyun = platform != 'volc'
        if self._aliyun_card is not None:
            self._aliyun_card.visible = show_aliyun
        if self._volc_card is not None:
            self._volc_card.visible = not show_aliyun

    # --------------------------------------------------
    # UI 构建
    # --------------------------------------------------
    @staticmethod
    def _section_header(title: str) -> None:
        """渲染功能分区标题: 分隔线 + 分区名.

        Args:
            title: 分区标题文本.
        """
        ui.separator().classes('mt-3')
        ui.label(title).classes('text-base font-medium mt-1')

    def _build_ui(self) -> None:
        """构建面板 UI 布局."""
        container = ui.card().classes('w-full p-4 gap-2')
        self._container = container
        self._aliyun_card = container
        with container:
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

            # 分区一: 基本配置 (各功能共有项)
            self._section_header('基本配置')
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
            self._fields['timeout'] = (
                ui.number(label='Timeout (秒)', value=30, min=1)
                .classes('w-full')
                .tooltip('API 请求超时时间(秒)')
            )

            # 低频连接参数折叠到高级配置, 默认收起
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

            # 分区二: 同步配置
            self._section_header('同步配置')
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

            # 分区三: 检索配置 (本期无专属项, 文案占位)
            self._section_header('检索配置')
            ui.label(
                '检索参数在知识检索页签查询时指定'
            ).classes('text-sm text-gray-400')

            # 分区四: 问答配置
            self._section_header('问答配置')
            self._fields['api_key'] = (
                ui.input(label='API Key', password=True)
                .classes('w-full')
                .tooltip(
                    '百炼 API-Key,'
                    ' 仅知识问答使用,'
                    ' 在百炼控制台 API Key 页面获取'
                )
            )
            self._fields['agent_id'] = (
                ui.input(label='知识问答服务 ID')
                .classes('w-full')
                .tooltip(
                    '知识问答服务应用 ID (aid-xxx),'
                    ' 仅知识问答使用,'
                    ' 在百炼控制台知识问答页面创建并发布后获取'
                )
            )

            # 字符串输入框失焦/粘贴后即时去除首尾空白
            for field in self._fields.values():
                if isinstance(field, ui.input):
                    field.on('change', self._on_field_change)

            with ui.row().classes('w-full mt-2 gap-2'):
                self._aliyun_save_btn = ui.button(
                    '保存配置',
                    on_click=self._on_save_aliyun,
                    icon='save',
                ).classes('flex-1')

            ui.button(
                '打开知识库控制台',
                on_click=self._open_aliyun_console,
                icon='open_in_new',
            ).props('outline').classes('w-full')

        self._build_volc_ui()

        # 定时刷新保存/测试按钮的灰化状态
        ui.timer(0.5, self._refresh_btn_states)

    def _build_volc_ui(self) -> None:
        """构建火山引擎 VikingDB 配置卡片."""
        volc_card = ui.card().classes('w-full p-4 gap-2')
        self._volc_card = volc_card
        with volc_card:
            # 标题行: 左侧标题, 右侧连通性测试按钮
            with ui.row().classes(
                'w-full items-center mb-2 gap-2'
            ):
                ui.label('火山引擎 VikingDB 配置').classes(
                    'text-lg font-bold'
                )
                self._volc_test_btn = ui.button(
                    '连通性测试',
                    on_click=self._on_test_volc_connection,
                    icon='network_check',
                ).props('dense outline').classes('ml-auto')

            # 分区一: 基本配置 (各功能共有项)
            self._section_header('基本配置')
            self._volc_fields['ak'] = (
                ui.input(label='AK (Access Key)')
                .classes('w-full')
                .tooltip('火山引擎 Access Key')
            )
            self._volc_fields['sk'] = (
                ui.input(label='SK (Secret Key)', password=True)
                .classes('w-full')
                .tooltip('火山引擎 Secret Key')
            )
            self._volc_fields['host'] = (
                ui.input(label='Host')
                .classes('w-full')
                .tooltip('知识库服务域名')
            )
            self._volc_fields['region'] = (
                ui.input(label='Region')
                .classes('w-full')
                .tooltip('服务地域, 如 cn-beijing')
            )
            self._volc_fields['scheme'] = (
                ui.input(label='Scheme')
                .classes('w-full')
                .tooltip('请求协议, http 或 https, 默认 https')
            )
            self._volc_fields['timeout'] = (
                ui.number(label='Timeout (秒)', value=30, min=1)
                .classes('w-full')
                .tooltip('API 请求超时时间(秒)')
            )
            self._volc_fields['resource_id'] = (
                ui.input(label='Resource ID')
                .classes('w-full')
                .tooltip(
                    '知识库唯一 ID, 与 Collection Name 二选一'
                )
            )
            self._volc_fields['collection_name'] = (
                ui.input(label='Collection Name')
                .classes('w-full')
                .tooltip(
                    '知识库名称, 与 Resource ID 二选一'
                )
            )

            # 分区二: 同步配置
            self._section_header('同步配置')
            self._volc_fields['project_name'] = (
                ui.input(label='Project Name')
                .classes('w-full')
                .tooltip('项目名称, 默认 default')
            )
            self._volc_fields['strategy_resource_id'] = (
                ui.input(label='切片策略 ID')
                .classes('w-full')
                .tooltip(
                    '可选, 留空使用知识库默认切片策略,'
                    ' 如 kb-strategy-xxxx'
                )
            )

            # 分区三: 检索配置 (本期无专属项, 文案占位)
            self._section_header('检索配置')
            ui.label(
                '检索参数在知识检索页签查询时指定'
            ).classes('text-sm text-gray-400')

            # 分区四: 问答配置
            self._section_header('问答配置')
            self._volc_fields['service_resource_id'] = (
                ui.input(label='知识服务 ID')
                .classes('w-full')
                .tooltip(
                    '知识服务 resource_id,'
                    ' 仅知识问答使用'
                )
            )
            self._volc_fields['api_key'] = (
                ui.input(label='API Key', password=True)
                .classes('w-full')
                .tooltip(
                    '仅知识问答使用,'
                    ' 在火山方舟控制台获取'
                )
            )

            # 字符串输入框失焦/粘贴后即时去除首尾空白
            for field in self._volc_fields.values():
                if isinstance(field, ui.input):
                    field.on('change', self._on_field_change)

            with ui.row().classes('w-full mt-2 gap-2'):
                self._volc_save_btn = ui.button(
                    '保存配置',
                    on_click=self._on_save_volc,
                    icon='save',
                ).classes('flex-1')

            ui.button(
                '打开知识库控制台',
                on_click=self._open_volc_console,
                icon='open_in_new',
            ).props('outline').classes('w-full')

    # --------------------------------------------------
    # 数据加载 / 保存
    # --------------------------------------------------
    def _load_from_store(self) -> None:
        """从 config_store 加载配置并填充两个平台的表单."""
        data = self._store.load()
        ak_cfg: dict[str, object] = data.get(
            'aliyun_knowledge', {}
        )  # type: ignore[assignment]
        for key, field in self._fields.items():
            if key in ak_cfg:
                field.value = ak_cfg[key]
        volc_cfg: dict[str, object] = data.get(
            'viking_knowledge', {}
        )  # type: ignore[assignment]
        for key, field in self._volc_fields.items():
            if key in volc_cfg:
                field.value = volc_cfg[key]

    def _collect_section_values(
        self,
        fields: dict[str, ui.input | ui.number],
    ) -> dict[str, object]:
        """收集单个平台段表单当前值组成配置字典.

        字符串字段值统一去除首尾空白, timeout 非数值
        回退缺省值, 其余字段保持 number 组件原生类型.

        Args:
            fields: 平台表单输入组件字典, key 为配置字段名.

        Returns:
            该平台段全部字段组成的扁平字典.
        """
        values: dict[str, object] = {}
        for key, field in fields.items():
            value = _stripped_value(field.value)
            if key == 'timeout':
                value = _normalized_timeout(value)
            values[key] = value
        return values

    def _collect_aliyun_values(self) -> dict[str, object]:
        """收集阿里云段表单当前值.

        Returns:
            阿里云段全部字段组成的扁平字典.
        """
        return self._collect_section_values(self._fields)

    def _collect_volc_values(self) -> dict[str, object]:
        """收集火山引擎段表单当前值.

        Returns:
            火山引擎段全部字段组成的扁平字典.
        """
        return self._collect_section_values(self._volc_fields)

    def _save_section(
        self,
        section: str,
        values: dict[str, object],
    ) -> None:
        """保存单个平台段配置, 保留另一段现有值.

        ``GUIConfigStore.save`` 为整文件替换, 故先 load
        完整配置、仅替换目标段后再整份落盘, 避免丢失
        另一平台已保存的配置.

        Args:
            section: 配置段键名 (aliyun_knowledge /
                viking_knowledge).
            values: 该平台段收集到的新值.
        """
        data = self._store.load()
        data[section] = values
        self._store.save(data)

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

    def _on_save_aliyun(self) -> None:
        """阿里云保存按钮回调: 仅保存阿里云段配置."""
        if self._is_running() or self._testing or self._volc_testing:
            return
        try:
            self._save_section(
                'aliyun_knowledge', self._collect_aliyun_values()
            )
            ui.notify('配置已保存', type='positive')
        except Exception as exc:
            ui.notify(f'保存失败: {exc}', type='negative')

    def _on_save_volc(self) -> None:
        """火山引擎保存按钮回调: 仅保存火山引擎段配置."""
        if self._is_running() or self._testing or self._volc_testing:
            return
        try:
            self._save_section(
                'viking_knowledge', self._collect_volc_values()
            )
            ui.notify('配置已保存', type='positive')
        except Exception as exc:
            ui.notify(f'保存失败: {exc}', type='negative')

    # --------------------------------------------------
    # 控制台跳转
    # --------------------------------------------------
    def _open_aliyun_console(self) -> None:
        """用默认浏览器打开阿里云百炼知识库控制台."""
        webbrowser.open(_ALIYUN_CONSOLE_URL)

    def _open_volc_console(self) -> None:
        """用默认浏览器打开火山引擎知识库控制台."""
        webbrowser.open(_VOLC_CONSOLE_URL)

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
        """阿里云连通性测试按钮回调: 校验后启动后台测试任务."""
        if self._is_running() or self._testing or self._volc_testing:
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
            safe_notify(
                self._container,
                f'连接失败: {error_summary(exc)}',
                type='negative',
            )
        else:
            logger.info('阿里云连通性测试成功')
            safe_notify(
                self._container, '阿里云连接成功', type='positive'
            )
        finally:
            self._testing = False
            if self._test_btn is not None:
                self._test_btn.props(remove='loading')

    # --------------------------------------------------
    # 火山引擎连通性测试
    # --------------------------------------------------
    def _missing_volc_required(self) -> list[str]:
        """检查火山引擎表单必填项, 返回缺失项展示名列表.

        除 AK/SK 外, Resource ID 与 Collection Name
        至少需填写其一.

        Returns:
            缺失的必填配置项展示名列表, 空列表表示均已填写.
        """
        missing: list[str] = []
        for key, label in _VOLC_REQUIRED_FIELDS:
            field = self._volc_fields.get(key)
            value = field.value if field is not None else None
            if not str(value or '').strip():
                missing.append(label)
        resource_id = self._volc_fields.get('resource_id')
        collection = self._volc_fields.get('collection_name')
        rid = str(_stripped_value(resource_id.value) or '').strip() \
            if resource_id is not None else ''
        cname = str(_stripped_value(collection.value) or '').strip() \
            if collection is not None else ''
        if not rid and not cname:
            missing.append('Resource ID 或 Collection Name')
        return missing

    def _on_test_volc_connection(self) -> None:
        """火山引擎连通性测试按钮回调: 校验后启动后台测试任务."""
        if self._is_running() or self._testing or self._volc_testing:
            return
        missing = self._missing_volc_required()
        if missing:
            ui.notify(
                '请先填写必要配置项: ' + ', '.join(missing),
                type='warning',
            )
            return
        values = {
            key: _stripped_value(field.value)
            for key, field in self._volc_fields.items()
        }
        self._volc_testing = True
        if self._volc_test_btn is not None:
            self._volc_test_btn.props('loading')
        background_tasks.create(
            self._run_volc_connection_test(values),
            name='volc connection test',
        )

    async def _run_volc_connection_test(
        self, values: dict[str, object]
    ) -> None:
        """后台执行火山引擎连通性测试并反馈结果.

        以当前表单值构造配置与客户端, 发起轻量只读
        API 调用; 成功/失败均通过弹窗与日志反馈.

        Args:
            values: 火山引擎表单当前值组成的扁平配置字典.
        """
        try:
            cfg = VikingKnowledgeSettings(**values)  # type: ignore[arg-type]
            client = VikingKnowledgeClient(config=cfg)
            await client.check_connection()
        except Exception as exc:
            logger.exception('火山引擎连通性测试失败')
            safe_notify(
                self._container,
                f'连接失败: {error_summary(exc)}',
                type='negative',
            )
        else:
            logger.info('火山引擎连通性测试成功')
            safe_notify(
                self._container, '火山引擎连接成功', type='positive'
            )
        finally:
            self._volc_testing = False
            if self._volc_test_btn is not None:
                self._volc_test_btn.props(remove='loading')

    # --------------------------------------------------
    # 按钮状态管理
    # --------------------------------------------------
    def _refresh_btn_states(self) -> None:
        """根据后台任务状态刷新保存/测试按钮灰化.

        控制台跳转按钮与后台任务无关, 不参与灰化,
        始终保持可用.
        """
        busy = (
            self._is_running()
            or self._testing
            or self._volc_testing
        )
        if self._aliyun_save_btn is not None:
            if busy:
                self._aliyun_save_btn.disable()
            else:
                self._aliyun_save_btn.enable()
        if self._volc_save_btn is not None:
            if busy:
                self._volc_save_btn.disable()
            else:
                self._volc_save_btn.enable()
        if self._test_btn is not None:
            if busy:
                self._test_btn.disable()
            else:
                self._test_btn.enable()
        if self._volc_test_btn is not None:
            if busy:
                self._volc_test_btn.disable()
            else:
                self._volc_test_btn.enable()
