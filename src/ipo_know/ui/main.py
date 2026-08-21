"""IPO Know GUI 桌面端入口.

启动 NiceGUI native 窗口, 组装配置面板、操作面板与日志面板.
"""

import ctypes
import logging
import sys
from pathlib import Path

from nicegui import ui

from ipo_know.config.logger import setup_logging
from ipo_know.ui.config_panel import ConfigPanel
from ipo_know.ui.config_store import GUIConfigStore
from ipo_know.ui.log_panel import LogPanel
from ipo_know.ui.operation_panel import OperationPanel


logger = logging.getLogger(__name__)

#: .NET Framework 4.6.2 对应的 NDP Release 值, 与 pywebview
#: winforms.py 的判定阈值一致
_DOTNET_MIN_RELEASE = 394802

#: WebView2 Evergreen Runtime 及各预览渠道的 EdgeUpdate 客户端
#: GUID, 与 pywebview winforms.py ``_is_chromium()`` 的判定列表
#: 保持一致
_WEBVIEW2_CLIENT_GUIDS: tuple[str, ...] = (
    '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',  # Runtime
    '{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}',  # Beta
    '{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}',  # Dev
    '{65C35B14-6C1D-4122-AC46-7148CC9D6497}',  # Canary
)

_MSGBOX_TITLE = 'IPO知识库爬虫工具'


def _show_message_box(message: str) -> None:
    r"""弹出系统级 MessageBox (MB_OK), 用于启动预检提示.

    Args:
        message: 弹窗正文, 支持 ``\n`` 换行.
    """
    ctypes.windll.user32.MessageBoxW(0, message, _MSGBOX_TITLE, 0)


def check_dotnet_framework() -> bool:
    r"""预检 .NET Framework 4.6.2+ 是否已安装.

    依次尝试 ``HKLM\SOFTWARE\Microsoft\NET Framework Setup\
    NDP\v4\Full`` 及其 ``WOW6432Node`` 重定向路径的 ``Release``
    值, ``>= 394802`` 视为满足 pywebview 要求. 预检自身读取异常
    不阻断启动.

    Returns:
        bool: 已安装且版本满足要求返回 True; 键缺失、版本不足或
        读取异常返回 False.
    """
    if sys.platform != 'win32':
        return True

    import winreg

    sub_keys = (
        r'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full',
        r'SOFTWARE\WOW6432Node\Microsoft'
        r'\NET Framework Setup\NDP\v4\Full',
    )
    for sub_key in sub_keys:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, sub_key
            ) as key:
                release, _ = winreg.QueryValueEx(key, 'Release')
        except OSError:
            continue
        if release >= _DOTNET_MIN_RELEASE:
            logger.info(
                '.NET Framework 预检通过 (Release=%s)', release
            )
            return True

    logger.error(
        '.NET Framework 缺失或版本过低, 需要 Release >= %s',
        _DOTNET_MIN_RELEASE,
    )
    return False


def _edge_browser_installed() -> bool:
    r"""检测 Microsoft Edge (Chromium) 浏览器是否已安装.

    通过 ``App Paths\msedge.exe`` 注册表键的默认值定位可执行
    文件. 现代 Edge 与 WebView2 Runtime 共享浏览器内核, pywebview
    的 edgechromium 渲染器可直接使用.

    Returns:
        bool: Edge 已安装返回 True; 否则返回 False.
    """
    import winreg

    sub_key = (
        r'SOFTWARE\Microsoft\Windows\CurrentVersion'
        r'\App Paths\msedge.exe'
    )
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, sub_key) as key:
                exe_path, _ = winreg.QueryValueEx(key, '')
        except OSError:
            continue
        if exe_path:
            logger.info('检测到 Microsoft Edge: %s', exe_path)
            return True

    return False


def check_webview2_runtime() -> bool:
    r"""预检 WebView2 渲染能力是否可用.

    与 pywebview ``winforms.py`` 的 ``_is_chromium()`` 判定对齐
    且更宽松, 满足任一条件即通过:

    1. EdgeUpdate 客户端注册表中存在 WebView2 Runtime (含 Beta/
       Dev/Canary 渠道) 的 ``pv`` 值, 覆盖 HKLM (含
       ``WOW6432Node`` 重定向) 与 HKCU 双蜂巢;
    2. Microsoft Edge (Chromium) 浏览器已安装.

    Returns:
        bool: 任一可用证据存在返回 True; 全部缺失返回 False.
    """
    if sys.platform != 'win32':
        return True

    import winreg

    hives: tuple = (
        (winreg.HKEY_LOCAL_MACHINE, 'HKLM', r'SOFTWARE\WOW6432Node'),
        (winreg.HKEY_LOCAL_MACHINE, 'HKLM', r'SOFTWARE'),
        (winreg.HKEY_CURRENT_USER, 'HKCU', r'SOFTWARE'),
    )
    for guid in _WEBVIEW2_CLIENT_GUIDS:
        for hive, hive_name, prefix in hives:
            sub_key = rf'{prefix}\Microsoft\EdgeUpdate\Clients\{guid}'
            try:
                with winreg.OpenKey(hive, sub_key) as key:
                    pv, _ = winreg.QueryValueEx(key, 'pv')
            except OSError:
                continue
            if pv:
                logger.info(
                    'WebView2 Runtime 预检通过 (%s pv=%s)',
                    hive_name,
                    pv,
                )
                return True

    if _edge_browser_installed():
        logger.info(
            'WebView2 预检通过: 已安装 Microsoft Edge, '
            '可提供 Chromium 渲染能力'
        )
        return True

    logger.warning('未检测到 WebView2 Runtime')
    return False


def precheck_runtime_environment() -> None:
    """启动预检: .NET Framework 缺失阻断, WebView2 缺失仅警告.

    仅 Windows 平台执行, 其他平台直接跳过.
    """
    if sys.platform != 'win32':
        return

    if not check_dotnet_framework():
        _show_message_box(
            '本程序需要 .NET Framework 4.6.2 或更高版本才能运行。\n\n'
            '请从微软官网下载安装 .NET Framework 4.8 后重试。'
        )
        sys.exit(1)

    if not check_webview2_runtime():
        _show_message_box(
            '未检测到 WebView2 Runtime，窗口可能无法正常显示。'
            '建议安装 Microsoft Edge WebView2 Runtime。'
        )


def main() -> None:
    """启动 IPO Know GUI 桌面端."""
    setup_logging()

    # 启动预检: .NET / WebView2 环境检测
    precheck_runtime_environment()

    # favicon 资源路径
    assets_dir = Path(__file__).parent / 'assets'
    favicon_path = assets_dir / 'spider.png'

    # 共享实例
    config_store = GUIConfigStore()

    @ui.page('/')
    def index() -> None:
        """主页面布局: 上方左右分栏 + 底部全宽日志."""
        # 全局深色模式, 须在任何 UI 元素创建之前启用
        ui.dark_mode(True)

        operation_panel_ref: list[OperationPanel] = []

        # 先创建容器骨架（保证 DOM 顺序正确）
        with ui.column().classes('w-full'):
            # wrap=False: w-1/3 + w-2/3 + gap 超过 100% 会触发
            # flex 换行, 导致右栏落到左栏下方
            with ui.row(wrap=False).classes(
                'w-full gap-4 items-start'
            ):
                left_col = ui.column().classes('w-1/3')
                right_col = ui.column().classes('w-2/3')
            bottom_col = ui.column().classes('w-full')

        # 填充底部: 日志面板（需要先创建供操作面板引用）
        with bottom_col:
            log_panel = LogPanel()
            log_panel.start_capture()

        # 填充左侧: 配置面板
        with left_col:
            config_panel = ConfigPanel(
                config_store=config_store,
                is_running=lambda: (
                    bool(operation_panel_ref)
                    and operation_panel_ref[0].is_running()
                ),
            )

        # 填充右侧: 操作面板
        with right_col:
            operation_panel = OperationPanel(
                config_store=config_store,
                log_panel=log_panel,
            )
        operation_panel_ref.append(operation_panel)

        # 联动: 目标平台切换时显隐对应平台配置卡片
        operation_panel.on_platform_change(config_panel.set_platform)

    # favicon 传本地 Path: NiceGUI 会以 FileResponse 挂载到
    # /favicon.ico; 传字符串路径会落入 data-URL 分支而失效
    ui.run(
        native=True,
        window_size=(1200, 800),
        title='IPO知识库爬虫工具',
        favicon=favicon_path,
        reload=False,
    )


if __name__ == '__main__':
    main()
