"""LLM 摘要与导出文件命名模块.

基于官方 ``openai`` 包调用阿里云百炼 OpenAI 兼容端点，为导出
文档生成简洁中文标题与内容摘要。任何异常均降级返回空字符串，
不影响导出主流程。
"""
import json

from loguru import logger
from openai import APIStatusError
from openai import AsyncOpenAI


_SUMMARY_MODEL = 'qwen-flash'

# 业务空间专属兼容模式端点模板 (不含 /chat/completions 后缀).
_BASE_URL_TEMPLATE = (
    'https://{workspace_id}.{region_id}'
    '.maas.aliyuncs.com/compatible-mode/v1'
)

_TIMEOUT_SECONDS = 60.0

_PROMPT_TEMPLATE = """你是文档整理助手。请根据下面的问答对话内容，\
输出一个 JSON 对象，格式如下：
{{"file_name": "简洁中文标题", "summary": "100字以内的内容摘要"}}
要求：只输出 JSON 本身，不要输出任何其他文字或代码围栏。

【提问】
{question}

【回答】
{answer}
"""


def _normalize_base_url(workspace_id: str, region_id: str) -> str:
    """归一化兼容模式 base_url.

    workspace_id 既允许填业务空间 ID (按模板拼装)，也允许
    直接填完整 base_url (兼容带或不带 ``/compatible-mode/v1``
    后缀、带 ``/chat/completions`` 尾缀等常见写法)。

    Args:
        workspace_id: 业务空间 ID 或完整 base_url。
        region_id: 部署区域标识，仅模板拼装时使用。

    Returns:
        以 ``/compatible-mode/v1`` 结尾的 base_url。
    """
    raw = workspace_id.strip()
    if raw.lower().startswith(('http://', 'https://')):
        url = raw.rstrip('/')
        if url.endswith('/chat/completions'):
            url = url[: -len('/chat/completions')]
        if url.endswith('/compatible-mode/v1'):
            return url
        if url.endswith('/compatible-mode'):
            return f'{url}/v1'
        return f'{url}/compatible-mode/v1'
    return _BASE_URL_TEMPLATE.format(
        workspace_id=raw, region_id=region_id,
    )


def _parse_summary(content: str) -> tuple[str, str]:
    """从模型输出中解析 file_name 与 summary.

    Args:
        content: 模型返回的消息文本。

    Returns:
        (file_name, summary) 二元组。

    Raises:
        ValueError: JSON 解析失败或结构不符时抛出。
    """
    text = content.strip()
    if text.startswith('```'):
        # 容错：剥离模型可能附带的代码围栏。
        text = text.strip('`')
        if text.lower().startswith('json'):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError('摘要响应不是 JSON 对象')
    file_name = str(data.get('file_name') or '').strip()
    summary = str(data.get('summary') or '').strip()
    return file_name, summary


async def summarize_and_name(
    answer_md: str,
    question: str,
    api_key: str,
    workspace_id: str,
    region_id: str,
) -> tuple[str, str]:
    """调用 LLM 生成导出文件名与内容摘要.

    任何异常（鉴权失败、网络错误、超时、JSON 解析失败等）
    均降级返回 ("", "")，由调用方使用默认标题并跳过摘要
    小节。HTTP 错误会额外记录状态码以便排障。

    Args:
        answer_md: AI 回答的 Markdown 正文。
        question: 用户提问。
        api_key: 阿里云百炼 API Key。
        workspace_id: 百炼业务空间 ID（或完整 base_url）。
        region_id: 部署区域标识。

    Returns:
        (file_name, summary_text) 二元组，失败时为两个空串。
    """
    base_url = _normalize_base_url(workspace_id, region_id)
    logger.debug(
        '导出摘要请求发起 | model={} | question_len={}',
        _SUMMARY_MODEL,
        len(question),
    )
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=_TIMEOUT_SECONDS,
        )
        completion = await client.chat.completions.create(
            model=_SUMMARY_MODEL,
            messages=[
                {
                    'role': 'user',
                    'content': _PROMPT_TEMPLATE.format(
                        question=question,
                        answer=answer_md,
                    ),
                },
            ],
        )
        content = completion.choices[0].message.content or ''
        file_name, summary = _parse_summary(content)
        logger.info(
            '导出摘要生成成功 | file_name={} | summary_len={}',
            file_name,
            len(summary),
        )
        return file_name, summary
    except APIStatusError as exc:
        logger.warning(
            '导出摘要降级为空 | HTTP {} | {}',
            exc.status_code,
            exc.message,
        )
        return '', ''
    except Exception as exc:
        logger.warning('导出摘要降级为空 | {}', exc)
        return '', ''
