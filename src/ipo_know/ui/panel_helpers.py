"""UI 面板公共工具函数.

抽取自操作面板与配置面板的重复实现, 供各面板统一复用:

- ``error_summary``: 将异常压缩为适合弹窗展示的简短摘要.
- ``safe_notify``: 在后台任务上下文中安全调用 ``ui.notify``,
  供检索/问答等后续面板的后台任务复用.
"""

from loguru import logger
from nicegui import ui


# 错误摘要在弹窗中的最大展示长度.
_ERROR_SUMMARY_LIMIT = 100


def error_summary(exc: Exception) -> str:
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


def safe_notify(
    container: ui.element | None,
    message: str,
    type: str = 'info',
) -> None:
    """在后台任务上下文中安全调用 ``ui.notify``.

    ``ui.notify`` 依赖当前 asyncio 任务的槽位栈解析
    客户端, 而 ``background_tasks.create`` 启动的任务
    槽位栈为空, 直接调用会抛 RuntimeError. 此处先
    进入面板根容器槽位恢复客户端上下文; 通知本身
    失败时仅记录日志, 不掩盖业务结果.

    Args:
        container: 面板根容器, 用于恢复槽位上下文;
            为 None 时直接调用 ``ui.notify``.
        message: 通知正文.
        type: 通知类型 (positive/negative/warning 等).
    """
    try:
        if container is not None:
            with container:
                ui.notify(message, type=type)
        else:
            ui.notify(message, type=type)
    except Exception:
        logger.exception('界面通知发送失败: {}', message)
