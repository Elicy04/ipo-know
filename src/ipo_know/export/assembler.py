"""导出文档组装模块.

将问答内容、元信息与引用来源拼装为完整的 Markdown 文档，
供 PDF 转换使用。
"""
import re


# Windows 文件名非法字符。
_INVALID_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|]')

_DEFAULT_TITLE = '对话记录'

_MAX_FILENAME_LENGTH = 60


def sanitize_filename(name: str) -> str:
    """清洗导出文件名.

    去除反斜杠、斜杠、冒号、星号、问号、双引号、尖括号、
    竖线等非法字符并截断至 60 字符；清洗后为空时返回默认标题。

    Args:
        name: 原始文件名（通常由 LLM 生成）。

    Returns:
        可安全用作文件名的字符串。
    """
    cleaned = _INVALID_CHARS_PATTERN.sub('', name).strip()
    cleaned = cleaned[:_MAX_FILENAME_LENGTH].strip()
    return cleaned or _DEFAULT_TITLE


def assemble_export_document(
    answer_md: str,
    question: str,
    platform: str,
    timestamp: str,
    usage_text: str,
    references: list[str],
    file_name: str,
    summary_text: str,
) -> str:
    """组装完整导出 Markdown 文档.

    Args:
        answer_md: AI 回答的 Markdown 正文。
        question: 用户提问。
        platform: 知识平台名称。
        timestamp: 对话时间（已格式化字符串）。
        usage_text: Token 用量说明文本。
        references: 引用来源列表，空列表时跳过该小节。
        file_name: LLM 生成的文件名，作为文档标题。
        summary_text: 内容摘要，为空时跳过该小节。

    Returns:
        完整的 Markdown 文档文本。
    """
    title = sanitize_filename(file_name) if file_name else _DEFAULT_TITLE
    lines: list[str] = [f'# {title}', '']
    lines.append(
        f'> 平台：{platform} | 时间：{timestamp} | 用量：{usage_text}'
    )
    lines.append('')
    lines.extend(['## 提问', '', question, ''])
    if summary_text:
        lines.extend(['## 内容摘要', '', summary_text, ''])
    lines.extend(['## 正文', '', answer_md, ''])
    valid_refs = [ref for ref in references if ref.strip()]
    if valid_refs:
        lines.extend(['## 引用来源', ''])
        lines.extend(f'- {ref}' for ref in valid_refs)
    return '\n'.join(lines).rstrip() + '\n'
