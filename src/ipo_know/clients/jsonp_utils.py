"""JSONP 响应解析与回调生成工具.

提供独立的 JSONP 格式响应解析和随机回调函数名生成能力,
供各交易所客户端 (东方财富 / 北交所 / 深交所等) 复用.
"""

import json
import random
import re
import string
import time

from loguru import logger


# 正则：匹配 JSONP 包裹格式 callbackName({...})
_JSONP_REGEX = re.compile(r'^[a-zA-Z0-9_]+\((.*)\)\s*;?\s*$', re.DOTALL)


def parse_jsonp(text: str) -> dict:
    """从 JSONP 响应文本中提取 JSON 数据.

    Args:
        text: JSONP 格式响应文本，如 ``jQuery123({...})``.

    Returns:
        解析后的 dict.

    Raises:
        ValueError: JSONP 格式不匹配或 JSON 解析失败.
    """
    match = _JSONP_REGEX.match(text.strip())
    if not match:
        logger.error(
            'JSONP 解析失败 | 响应长度: {} | 前 200 字符: {}',
            len(text), text[:200],
        )
        raise ValueError('响应内容不是合法的 JSONP 格式')

    json_content = match.group(1)
    try:
        return json.loads(json_content)
    except json.JSONDecodeError as exc:
        logger.error(
            'JSONP 内部 JSON 解析失败 | 错误: {} | 前 200 字符: {}',
            exc, json_content[:200],
        )
        raise ValueError(f'JSONP 内部 JSON 解析失败: {exc}') from exc


def generate_jsonp_callback() -> str:
    """生成随机 jQuery 风格 JSONP 回调名.

    Returns:
        格式如 ``jQuery_1690000000000_a1b2c3d4``.
    """
    rand_suffix = ''.join(
        random.choices(string.ascii_lowercase + string.digits, k=8)
    )
    return f'jQuery_{int(time.time() * 1000)}_{rand_suffix}'
