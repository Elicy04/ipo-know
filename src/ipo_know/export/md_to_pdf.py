"""Markdown 转 PDF 转换模块.

本模块是项目中唯一的第三方 PDF 转换引擎入口（基于
markdown-pdf / PyMuPDF）。如需替换渲染引擎，只需修改本文件，
其余导出逻辑不受影响。

中文字体说明：PyMuPDF Story 不识别 Windows 系统字体名称，
本模块在检测到微软雅黑字体文件时，通过 CSS @font-face 与
Archive 将字体缓冲注入渲染链；否则回退到 MuPDF 内置的
Droid Sans Fallback，保证中文始终可用。生成的 PDF 会再做
字体子集化与压缩，避免完整嵌入大字体文件。
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger


if TYPE_CHECKING:
    from pymupdf import Archive


# 微软雅黑字体候选路径（按优先级探测，取第一个存在的）。
_YAHEI_FONT_CANDIDATES = (
    Path('C:/Windows/Fonts/msyh.ttc'),
    Path('C:/Windows/Fonts/msyh.ttf'),
)

# Archive 中登记字体缓冲使用的名称，与 @font-face 的 url 对应。
_YAHEI_ARCHIVE_NAME = 'msyh.ttc'

# 基础导出样式：代码块浅灰底、表格细边框、图片限宽。
# 注意：PyMuPDF Story 不支持 @page 规则，2cm 页边距实际通过
# Section 的 borders 参数实现（见 _PAGE_MARGIN_PT），此处保留
# @page 声明仅为语义说明（无页眉页脚）。
_BASE_CSS = """
body {
    font-family: "Microsoft YaHei", "SimSun", sans-serif;
    font-size: 11px;
    line-height: 1.6;
}
@page { margin: 2cm; }
code, pre {
    background-color: #f4f4f4;
    font-family: Consolas, monospace;
}
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #dddddd; padding: 6px 8px; }
img { max-width: 100%; }
"""

# 注入微软雅黑时附加的 @font-face 声明。
_FONT_FACE_CSS = (
    '@font-face { font-family: "Microsoft YaHei"; '
    f'src: url({_YAHEI_ARCHIVE_NAME}); }}\n'
)

# 页边距（单位 pt），57pt ≈ 2cm。
_PAGE_MARGIN_PT = 57


def _find_yahei_font_file() -> Path | None:
    """探测本机可用的微软雅黑字体文件.

    Returns:
        存在的字体文件路径；未找到时返回 None。
    """
    for candidate in _YAHEI_FONT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _build_css_and_archive() -> tuple[str, Archive | None]:
    """构建导出 CSS 与字体 Archive.

    Returns:
        (css_text, archive) 二元组。找到微软雅黑时附加
        @font-face 声明并返回含字体缓冲的 Archive；否则返回
        (基础 CSS, None)，由 MuPDF 内置 CJK 字体兜底。
    """
    try:
        from pymupdf import Archive
    except ImportError:
        logger.debug('pymupdf 不可用 | 跳过字体注入')
        return _BASE_CSS, None

    font_file = _find_yahei_font_file()
    if font_file is None:
        logger.debug('未找到微软雅黑字体 | 使用内置 CJK 兜底字体')
        return _BASE_CSS, None
    try:
        archive = Archive()
        archive.add(font_file.read_bytes(), _YAHEI_ARCHIVE_NAME)
    except OSError as exc:
        logger.warning('微软雅黑字体读取失败 | 降级内置字体 | {}', exc)
        return _BASE_CSS, None
    logger.debug('微软雅黑字体注入成功 | path={}', font_file)
    return _FONT_FACE_CSS + _BASE_CSS, archive


def _subset_embedded_fonts(out_path: Path) -> None:
    """对已生成 PDF 的嵌入字体做子集化与压缩.

    markdown-pdf 会完整嵌入字体文件（微软雅黑约 20MB），
    子集化后仅保留实际用到的字形，体积可降至数十 KB。
    子集化失败时保留原始 PDF，不影响导出结果。

    Args:
        out_path: 已生成的 PDF 文件路径。
    """
    try:
        import pymupdf
    except ImportError:
        logger.debug('pymupdf 不可用 | 跳过字体子集化')
        return
    tmp_path = out_path.with_name(out_path.name + '.tmp')
    try:
        with pymupdf.open(out_path) as doc:
            doc.subset_fonts()
            doc.save(str(tmp_path), garbage=3, deflate=True)
        tmp_path.replace(out_path)
        logger.debug(
            '字体子集化完成 | size={} bytes',
            out_path.stat().st_size,
        )
    except Exception as exc:
        logger.warning('字体子集化失败 | 保留原始 PDF | {}', exc)
        tmp_path.unlink(missing_ok=True)


def convert_markdown_to_pdf(md_text: str, out_path: Path) -> None:
    """将 Markdown 文本渲染为 PDF 文件.

    Args:
        md_text: Markdown 正文。
        out_path: 输出 PDF 文件路径。

    Raises:
        RuntimeError: markdown-pdf 依赖未安装时抛出。
    """
    try:
        from markdown_pdf import MarkdownPdf
        from markdown_pdf import Section
    except ImportError as exc:
        logger.error('PDF 导出依赖缺失 | {}', exc)
        raise RuntimeError(
            'PDF 导出功能需要安装 markdown-pdf 依赖'
        ) from exc

    css_text, archive = _build_css_and_archive()
    # Section.root 传入 Archive 实例时，Story 会直接采用，
    # 使 @font-face 的 url 可从字体缓冲解析。
    root = archive if archive is not None else '.'
    pdf = MarkdownPdf(toc_level=0)
    section = Section(
        md_text,
        toc=False,
        root=root,
        borders=(
            _PAGE_MARGIN_PT,
            _PAGE_MARGIN_PT,
            -_PAGE_MARGIN_PT,
            -_PAGE_MARGIN_PT,
        ),
    )
    pdf.add_section(section, user_css=css_text)
    pdf.save(str(out_path))
    _subset_embedded_fonts(out_path)
    logger.info(
        'PDF 导出完成 | path={} | size={} bytes',
        out_path,
        out_path.stat().st_size,
    )
