"""阿里云数据中心文件标签构建与解析模块.

定义 fileID 映射重构中云端标签格式的唯一权威约定: 上传时为
每个文件打 5 类标签 (本地文件 ID 锚点/交易所/公司简称/审核
号/申报年份), 对齐时从云端标签反向解析锚点匹配本地清单. 本模
块为纯函数集合, 不做任何 IO.

锚点为哈希而非原始 fileId: 阿里云单标签上限 32 字符, 而深交
所形态的 fileId 可长达 49 字符, 直接拼接必然超限. 故锚点标签取
``fileid_`` + sha256(fileId.strip()) 前 24 位十六进制, 总长固定 31 字
符. 匹配侧用同一 ``fileid_anchor`` 函数本地换算, 双向无需反查.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from collections.abc import Mapping
from typing import Any

from loguru import logger


# 本地文件 ID 锚点标签前缀, 反向匹配的唯一依据.
FILEID_PREFIX = 'fileid_'

# 锚点哈希截取长度: 前缀 7 + 哈希 24 = 31 字符, 单标签上限 32,
# 留 1 字符余量. 24 位十六进制约 96 bit, 碰撞概率对万级文件量可忽.
ANCHOR_HASH_LEN = 24

# 审核编号标签前缀 (拼写按需求约定保留, 勿改为 audit).
AUDIT_PREFIX = 'autid_'

# 申报年份标签前缀, 后接 4 位数字年份.
YEAR_PREFIX = 'project_year_'

# 年份缺失或非法时的兜底标签值.
YEAR_UNKNOWN = 'project_year_unknown'

# 4 位 ASCII 数字年份校验, 兼容 str.isdigit 的 Unicode 误判.
_YEAR_RE = re.compile(r'[0-9]{4}')


def _is_blank(value: object) -> bool:
    """判断标签取值是否为空 (None/空串/纯空白).

    Args:
        value: 待检查的标签取值.

    Returns:
        为空返回 True.
    """
    return not isinstance(value, str) or not value.strip()


def _project_year_tag(record: Mapping[str, Any]) -> str:
    """计算申报年份标签值.

    年份缺失或非 4 位数字时一律返回兜底标签, 不告警 (年份
    缺失属预期场景, 由兜底标签显式标记).

    Args:
        record: 文件清单记录.

    Returns:
        完整年份标签字符串.
    """
    raw = record.get('projectYear')
    if isinstance(raw, str) and _YEAR_RE.fullmatch(raw):
        return f'{YEAR_PREFIX}{raw}'
    return YEAR_UNKNOWN


def fileid_anchor(file_id: str) -> str:
    """计算本地文件 ID 的哈希锚点值.

    先对入参 ``strip()`` 再取 UTF-8 编码的 sha256, 去空白行为与
    ``build_file_tags`` 打标时完全一致, 保证匹配侧用原始清单值换
    算即可命中. 返回十六进制摘要前 ANCHOR_HASH_LEN 位.

    Args:
        file_id: 本地文件 ID (可含首尾空白).

    Returns:
        24 位十六进制锚点哈希串, 拼前缀后总长 31 字符.
    """
    digest = hashlib.sha256(
        file_id.strip().encode('utf-8')
    ).hexdigest()
    return digest[:ANCHOR_HASH_LEN]


def build_file_tags(
    record: Mapping[str, Any],
    source: str,
) -> list[str]:
    """为单个文件记录构建阿里云数据中心标签列表.

    标签顺序固定: 本地文件 ID 锚点 (哈希)、裸交易所标签、裸公司简
    称、审核编号、申报年份. 锚点取 ``fileid_`` + fileId 去空白后的
    sha256 前 24 位 (单标签 32 字符上限约束, 见模块文档). auditId /
    companyAbbr / fileId 为空时跳过对应标签并告警, 不阻塞上传; 三者取
    值拼接前均去除首尾空白, 避免带空白标签导致锚点匹配失败.

    Args:
        record: 文件清单记录, 需含 fileId, 可含 companyAbbr /
            auditId / projectYear 键.
        source: 交易所标识, 如 sse / szse / bse.

    Returns:
        标签字符串列表, 最多 5 个.
    """
    tags: list[str] = []

    file_id = record.get('fileId')
    if _is_blank(file_id):
        logger.warning(
            '文件 ID 缺失, 跳过 fileid 锚点标签 | fileName={}',
            record.get('fileName'),
        )
    else:
        tags.append(f'{FILEID_PREFIX}{fileid_anchor(file_id)}')

    tags.append(source)

    company_abbr = record.get('companyAbbr')
    if _is_blank(company_abbr):
        logger.warning(
            '公司简称缺失, 跳过公司简称标签 | fileId={}',
            record.get('fileId'),
        )
    else:
        tags.append(company_abbr.strip())

    audit_id = record.get('auditId')
    if _is_blank(audit_id):
        logger.warning(
            '审核编号缺失, 跳过审核编号标签 | fileId={}',
            record.get('fileId'),
        )
    else:
        tags.append(f'{AUDIT_PREFIX}{audit_id.strip()}')

    tags.append(_project_year_tag(record))
    return tags


def extract_fileid(tags: Iterable[str]) -> str | None:
    """从标签集合中提取文件 ID 锚点哈希值.

    注意: 锚点为哈希而非原始 fileId (见模块文档), 返回的是首个 ``fileid_``
    前缀标签去掉前缀后的哈希串. 匹配侧需用 ``fileid_anchor`` 对本地
    fileId 换算同一哈希后比对, 不可直接等值原始值.
    函数名保留旧称以减少调用面改动.

    Args:
        tags: 云端文件的标签列表.

    Returns:
        首个 fileid_ 前缀标签去掉前缀后的锚点哈希串, 不存在时返回
        None.
    """
    for tag in tags:
        if tag.startswith(FILEID_PREFIX):
            return tag[len(FILEID_PREFIX):]
    return None


def has_source_tag(tags: Iterable[str], source: str) -> bool:
    """判断标签集合中是否含指定交易所的裸标签.

    Args:
        tags: 云端文件的标签列表.
        source: 交易所标识, 如 sse / szse / bse.

    Returns:
        存在等值匹配的裸交易所标签时返回 True.
    """
    return any(tag == source for tag in tags)
