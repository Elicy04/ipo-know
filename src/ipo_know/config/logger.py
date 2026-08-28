"""日志系统配置模块.

基于 loguru 的全局日志配置, 提供双通道输出与文件轮转/归档/压缩.
项目启动时调用 setup_logging() 一次, 其余模块直接 from loguru import
logger 使用.
"""

import sys
from pathlib import Path

from loguru import logger as _logger

from ipo_know.config.config import app_root


def default_log_dir() -> Path:
    """计算默认日志目录.

    返回 ``app_root()/logs``, 与 GUIConfigStore 的存储根目录策略一致.
    这样在冻结产物从快捷方式/开始菜单启动、工作目录不可控时日志仍写入固定位置.

    Returns:
        Path: 默认日志目录路径 (尚未创建, 由调用方负责创建).
    """
    return app_root() / 'logs'


def setup_logging(
    log_dir: str | Path | None = None,
    console_level: str = 'INFO',
    rotation: str = '00:00',
    retention: str = '30 days',
    compression: str = 'zip',
    diagnose: bool = True,
) -> None:
    """配置 loguru 全局日志系统.

    仅在应用入口调用一次. 后续所有模块直接 from loguru import logger
    即可获得已配置好的单例.

    输出策略:
        - STDERR:  彩色人类可读格式, 默认 INFO 级以上
        - 文件:    纯文本格式全级别输出 (DEBUG+), 按天轮转,
                    30 天保留, 自动 zip 压缩

    Args:
        log_dir:        日志文件输出目录, 自动递归创建; 为 None 时
                        使用 ``app_root()/logs``, 开发模式
                        与冻结模式行为一致
        console_level:  控制台最低日志级别, 不影响文件通道
        rotation:       文件轮转策略: '00:00' 每天零点 /
                        '10 MB' 按大小
        retention:      日志保留时长: '30 days' / '1 week'
        compression:    归档压缩格式: 'zip' / 'gz'
        diagnose:       异常时是否附加变量诊断信息,
                        开发环境建议 True, 生产部署改为 False
    """
    # 1. 清空 loguru 默认 handler, 避免输出重复
    _logger.remove()

    # 2. STDERR 通道: 彩色人类可读, 控制台级别可配
    _logger.add(
        sys.stderr,
        level=console_level.upper(),
        format=(
            '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | '
            '<level>{level: <8}</level> | '
            '<cyan>{name}</cyan>:<cyan>{function}</cyan>:'
            '<cyan>{line}</cyan> | '
            '<level>{message}</level>'
        ),
        colorize=True,
        diagnose=diagnose,
        backtrace=True,
    )

    # 3. 文件通道: 全级别 + 轮转/保留/压缩
    if log_dir is None:
        log_dir = default_log_dir()
    log_path = Path(log_dir) / 'ipo_know_{time:YYYY-MM-DD}.log'
    log_dir_resolved = Path(log_dir).resolve()
    log_dir_resolved.mkdir(parents=True, exist_ok=True)

    _logger.add(
        str(log_path),
        level='DEBUG',
        format=(
            '{time:YYYY-MM-DD HH:mm:ss.SSS} | '
            '{level: <8} | '
            '{name}:{function}:{line} | '
            '{message}'
        ),
        rotation=rotation,
        retention=retention,
        compression=compression,
        enqueue=True,
        diagnose=diagnose,
        backtrace=False,
        encoding='utf-8',
    )

    _logger.info(
        '日志系统初始化完成 | 目录: {} | 控制台级别: {}',
        str(log_dir_resolved),
        console_level.upper(),
    )
