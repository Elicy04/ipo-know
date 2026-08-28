"""导出摘要模块 (llm_summary) 单元测试.

覆盖 ``ipo_know.export.llm_summary`` 的 base_url 归一化与
摘要调用降级语义, 通过 mock ``AsyncOpenAI`` 客户端实现零网络
依赖, 可直接作为脚本执行.

用法:
    uv run python tests/unit/test_llm_summary.py

说明: 项目未引入 pytest 依赖, 沿用纯 ``assert`` 脚本惯例.
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import httpx
from loguru import logger
from openai import APIStatusError


# 将项目 src 目录加入 sys.path, 确保可以直接运行脚本
_SRC_DIR = Path(__file__).resolve().parent.parent.parent / 'src'
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from ipo_know.export import llm_summary  # noqa: E402
from ipo_know.export.llm_summary import _normalize_base_url  # noqa: E402
from ipo_know.export.llm_summary import _parse_summary  # noqa: E402
from ipo_know.export.llm_summary import summarize_and_name  # noqa: E402


_EXPECTED_BASE = (
    'https://ws-test.cn-beijing.maas.aliyuncs.com'
    '/compatible-mode/v1'
)


def _fake_completion(content: str) -> SimpleNamespace:
    """构造仿 chat.completions.create 返回对象.

    Args:
        content: 模拟的模型输出文本。

    Returns:
        含 choices[0].message.content 的命名空间对象。
    """
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _mock_client(content: str) -> MagicMock:
    """构造可替换 AsyncOpenAI 的 mock 客户端.

    Args:
        content: 模拟的模型输出文本。

    Returns:
        chat.completions.create 为 AsyncMock 的 MagicMock。
    """
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=_fake_completion(content),
    )
    return client


def test_normalize_base_url_workspace_id() -> None:
    """业务空间 ID 按模板拼装为完整 base_url."""
    assert (
        _normalize_base_url('ws-test', 'cn-beijing')
        == _EXPECTED_BASE
    )


def test_normalize_base_url_full_url_variants() -> None:
    """完整 URL 各写法均归一化为 /compatible-mode/v1 结尾."""
    variants = [
        _EXPECTED_BASE,
        _EXPECTED_BASE + '/',
        (
            'https://ws-test.cn-beijing.maas.aliyuncs.com'
            '/compatible-mode/v1/chat/completions'
        ),
        (
            'https://ws-test.cn-beijing.maas.aliyuncs.com'
            '/compatible-mode'
        ),
        'https://dashscope.aliyuncs.com',
    ]
    expected = [
        _EXPECTED_BASE,
        _EXPECTED_BASE,
        _EXPECTED_BASE,
        (
            'https://ws-test.cn-beijing.maas.aliyuncs.com'
            '/compatible-mode/v1'
        ),
        'https://dashscope.aliyuncs.com/compatible-mode/v1',
    ]
    for raw, want in zip(variants, expected, strict=True):
        assert _normalize_base_url(raw, 'cn-beijing') == want


def test_parse_summary_plain_json() -> None:
    """纯 JSON 输出可正常解析."""
    name, summary = _parse_summary(
        '{"file_name": "标题", "summary": "摘要"}',
    )
    assert name == '标题'
    assert summary == '摘要'


def test_parse_summary_code_fence() -> None:
    """带代码围栏的 JSON 输出可容错解析."""
    name, summary = _parse_summary(
        '```json\n{"file_name": "标题", "summary": "摘要"}\n```',
    )
    assert name == '标题'
    assert summary == '摘要'


def test_summarize_success() -> None:
    """成功路径返回解析后的文件名与摘要."""
    with patch.object(
        llm_summary,
        'AsyncOpenAI',
        return_value=_mock_client(
            '{"file_name": "测试标题", "summary": "测试摘要"}',
        ),
    ):
        name, summary = asyncio.run(
            summarize_and_name(
                answer_md='回答',
                question='提问',
                api_key='sk-x',
                workspace_id='ws-test',
                region_id='cn-beijing',
            ),
        )
    assert name == '测试标题'
    assert summary == '测试摘要'


def test_summarize_api_status_error_degrades() -> None:
    """APIStatusError (如 403) 降级为空串."""
    response = httpx.Response(
        403, request=httpx.Request('POST', 'https://x/v1'),
    )
    error = APIStatusError(
        'Access denied', response=response, body=None,
    )
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=error)
    with patch.object(
        llm_summary, 'AsyncOpenAI', return_value=client,
    ):
        result = asyncio.run(
            summarize_and_name(
                answer_md='回答',
                question='提问',
                api_key='sk-x',
                workspace_id='ws-test',
                region_id='cn-beijing',
            ),
        )
    assert result == ('', '')


def test_summarize_generic_error_degrades() -> None:
    """任意异常均降级为空串."""
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError('boom'),
    )
    with patch.object(
        llm_summary, 'AsyncOpenAI', return_value=client,
    ):
        result = asyncio.run(
            summarize_and_name(
                answer_md='回答',
                question='提问',
                api_key='sk-x',
                workspace_id='ws-test',
                region_id='cn-beijing',
            ),
        )
    assert result == ('', '')


def test_summarize_bad_json_degrades() -> None:
    """模型输出非法 JSON 时降级为空串."""
    with patch.object(
        llm_summary,
        'AsyncOpenAI',
        return_value=_mock_client('这不是 JSON'),
    ):
        result = asyncio.run(
            summarize_and_name(
                answer_md='回答',
                question='提问',
                api_key='sk-x',
                workspace_id='ws-test',
                region_id='cn-beijing',
            ),
        )
    assert result == ('', '')


def main() -> None:
    """依次执行全部 test_ 前缀函数并汇总结果."""
    tests = [
        fn
        for name, fn in sorted(globals().items())
        if name.startswith('test_') and callable(fn)
    ]
    failed: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed.append(fn.__name__)
            logger.error('用例失败 | {} | {}', fn.__name__, exc)
        else:
            logger.info('用例通过 | {}', fn.__name__)
    logger.info(
        '单测汇总 | 共 {} 例 | 通过 {} | 失败 {}',
        len(tests), len(tests) - len(failed), len(failed),
    )
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
