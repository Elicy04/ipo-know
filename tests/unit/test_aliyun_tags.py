"""阿里云数据中心标签模块纯函数单元测试.

覆盖 ``ipo_know.kb_align.aliyun_tags`` 的 ``fileid_anchor`` /
``build_file_tags`` / ``extract_fileid`` / ``has_source_tag`` 四个
纯函数, 零 mock、零网络 IO, 可直接作为脚本执行.

用法:
    uv run python tests/unit/test_aliyun_tags.py

说明: 项目未引入 pytest 依赖, 现有测试均为可直接执行的脚本形
式, 本文件沿用该惯例, 采用纯 ``assert`` 断言.
"""

import sys
from pathlib import Path

from loguru import logger


# 将项目 src 目录加入 sys.path, 确保可以直接运行脚本
_SRC_DIR = Path(__file__).resolve().parent.parent.parent / 'src'
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from ipo_know.kb_align.aliyun_tags import FILEID_PREFIX  # noqa: E402
from ipo_know.kb_align.aliyun_tags import build_file_tags  # noqa: E402
from ipo_know.kb_align.aliyun_tags import extract_fileid  # noqa: E402
from ipo_know.kb_align.aliyun_tags import fileid_anchor  # noqa: E402
from ipo_know.kb_align.aliyun_tags import has_source_tag  # noqa: E402


# 阿里云单标签长度上限, 全部标签断言不超过该值.
_TAG_MAX_LEN = 32

# 三所实测最长形态的深交所 fileId (49 字符), 超长回归基准.
_LONG_SZSE_FILE_ID = (
    'RAS_202606_2520059FCC1F50BBFF4D87995EEAA3429864DF'
)


def _full_record() -> dict[str, object]:
    """构造字段齐全的文件清单记录.

    Returns:
        含 fileId / companyAbbr / auditId / projectYear 的记录.
    """
    return {
        'fileId': 'f1',
        'companyAbbr': '地通控股',
        'auditId': '2160',
        'projectYear': '2017',
        'fileName': '招股说明书.pdf',
    }


def test_fileid_anchor_deterministic() -> None:
    """同输入多次换算结果一致 (确定性)."""
    assert fileid_anchor('f1') == fileid_anchor('f1')
    assert fileid_anchor(_LONG_SZSE_FILE_ID) == fileid_anchor(
        _LONG_SZSE_FILE_ID,
    )


def test_fileid_anchor_distinct() -> None:
    """不同输入产生不同锚点."""
    assert fileid_anchor('f1') != fileid_anchor('f2')
    assert fileid_anchor('sse_1') != fileid_anchor('szse_1')


def test_fileid_anchor_strip_consistent() -> None:
    """含首尾空白的输入与 strip 后结果一致."""
    assert fileid_anchor('  f1\t') == fileid_anchor('f1')
    assert fileid_anchor(
        f' {_LONG_SZSE_FILE_ID}\n',
    ) == fileid_anchor(_LONG_SZSE_FILE_ID)


def test_fileid_anchor_length() -> None:
    """锚点哈希定长 24 位, 拼前缀后总长 31 (上限 32 留余量)."""
    for file_id in ('f1', _LONG_SZSE_FILE_ID, '  f1\t'):
        anchor = fileid_anchor(file_id)
        assert len(anchor) == 24, f'{file_id!r} 锚点应定长 24'
        assert len(f'{FILEID_PREFIX}{anchor}') == 31
        assert len(f'{FILEID_PREFIX}{anchor}') <= _TAG_MAX_LEN


def test_build_file_tags_full() -> None:
    """完整记录按固定顺序返回 5 个标签, 锚点为哈希."""
    assert build_file_tags(_full_record(), 'szse') == [
        f'fileid_{fileid_anchor("f1")}',
        'szse',
        '地通控股',
        'autid_2160',
        'project_year_2017',
    ]


def test_build_file_tags_year_fallback() -> None:
    """申报年份 (projectYear) 缺失或非 4 位数字一律兜底."""
    for year in (None, '201', 'abcd'):
        record = _full_record()
        if year is None:
            del record['projectYear']
        else:
            record['projectYear'] = year
        tags = build_file_tags(record, 'szse')
        assert len(tags) == 5, f'年份={year!r} 时标签数应为 5'
        assert tags[-1] == 'project_year_unknown', f'年份={year!r}'


def test_build_file_tags_audit_id_blank() -> None:
    """审核编号 (auditId) 为空时不打 autid_ 标签."""
    for audit_id in (None, '', '   '):
        record = _full_record()
        record['auditId'] = audit_id
        assert build_file_tags(record, 'szse') == [
            f'fileid_{fileid_anchor("f1")}',
            'szse',
            '地通控股',
            'project_year_2017',
        ], f'auditId={audit_id!r} 时应为 4 标签'


def test_build_file_tags_company_abbr_blank() -> None:
    """公司简称 (companyAbbr) 为空时不打简称标签."""
    for abbr in (None, '', '  '):
        record = _full_record()
        record['companyAbbr'] = abbr
        assert build_file_tags(record, 'sse') == [
            f'fileid_{fileid_anchor("f1")}',
            'sse',
            'autid_2160',
            'project_year_2017',
        ], f'companyAbbr={abbr!r} 时应为 4 标签'


def test_extract_fileid_round_trip() -> None:
    """构建后提取往返返还原锚点哈希 (build 转 extract)."""
    tags = build_file_tags(_full_record(), 'bse')
    assert extract_fileid(tags) == fileid_anchor('f1')


def test_build_file_tags_file_id_strip() -> None:
    """首尾空白的 fileId 打锚点前去除, 与原始值换算结果一致."""
    record = _full_record()
    record['fileId'] = '  f1\t'
    tags = build_file_tags(record, 'szse')
    assert tags[0] == f'fileid_{fileid_anchor("f1")}', (
        'fileId 锚点应去除首尾空白后换算'
    )
    assert extract_fileid(tags) == fileid_anchor('f1')


def test_build_file_tags_file_id_blank_only() -> None:
    """FileId 为纯空白时视为缺失, 不打锚点标签."""
    record = _full_record()
    record['fileId'] = '   '
    tags = build_file_tags(record, 'szse')
    assert extract_fileid(tags) is None
    assert len(tags) == 4, '纯空白 fileId 时应为 4 标签'


def test_build_file_tags_long_file_id() -> None:
    """超长 fileId (深交所 49 字符形态) 构建不报错且标签合规."""
    record = _full_record()
    record['fileId'] = _LONG_SZSE_FILE_ID
    tags = build_file_tags(record, 'szse')
    assert tags[0] == f'fileid_{fileid_anchor(_LONG_SZSE_FILE_ID)}'
    assert extract_fileid(tags) == fileid_anchor(_LONG_SZSE_FILE_ID)


def test_build_file_tags_all_within_limit() -> None:
    """超长形态下全部标签长度不超过单标签上限 32."""
    record = {
        'fileId': _LONG_SZSE_FILE_ID,
        'companyAbbr': '测',
        'auditId': '2160',
        'projectYear': '2026',
    }
    tags = build_file_tags(record, 'szse')
    for tag in tags:
        assert len(tag) <= _TAG_MAX_LEN, f'标签超长: {tag!r}'


def test_extract_fileid_missing() -> None:
    """无 fileid_ 前缀标签时返回 None."""
    assert extract_fileid(
        ['bse', 'autid_9', 'project_year_2020'],
    ) is None
    assert extract_fileid([]) is None


def test_extract_fileid_first_wins() -> None:
    """存在多个 fileid_ 标签时取首个锚点值."""
    assert extract_fileid(['fileid_a', 'fileid_b']) == 'a'
    assert extract_fileid(['bse', 'fileid_b', 'fileid_c']) == 'b'


def test_has_source_tag_exact_match() -> None:
    """精确等值匹配, 前后缀变体不算命中."""
    assert has_source_tag(['sse'], 'sse')
    assert not has_source_tag(['sse_xxx'], 'sse')
    assert not has_source_tag(['xsse'], 'sse')
    assert not has_source_tag(['fileid_sse'], 'sse')


def test_has_source_tag_edge_cases() -> None:
    """空列表返回 False, 匹配区分大小写."""
    assert not has_source_tag([], 'sse')
    assert not has_source_tag(['SSE'], 'sse')
    assert not has_source_tag(['Sse', 'SZSE'], 'sse')
    assert has_source_tag(['szse', 'sse', 'bse'], 'sse')


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
