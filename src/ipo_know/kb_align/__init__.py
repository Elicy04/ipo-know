"""知识库文档对齐模块 (火山引擎 / 阿里云双平台).

以爬虫产出的有效文件清单为基准, 对知识库做文档与切片的全量
对齐 (补缺失 / 删无关). 火山平台同时清理孤儿切片, 阿里云平台
不管理孤儿切片.
"""

from ipo_know.kb_align.aliyun_aligner import AliyunAlignReport
from ipo_know.kb_align.aliyun_aligner import AliyunKBAligner
from ipo_know.kb_align.aliyun_aligner import AliyunPurgeReport
from ipo_know.kb_align.aliyun_aligner import build_file_name
from ipo_know.kb_align.aliyun_tags import build_file_tags
from ipo_know.kb_align.volc_aligner import DOC_ID_PREFIX
from ipo_know.kb_align.volc_aligner import STRATEGY_RESOURCE_ID
from ipo_know.kb_align.volc_aligner import AlignReport
from ipo_know.kb_align.volc_aligner import PurgeReport
from ipo_know.kb_align.volc_aligner import VolcKBAligner
from ipo_know.kb_align.volc_aligner import file_id_to_doc_id


__all__ = [
    'DOC_ID_PREFIX',
    'STRATEGY_RESOURCE_ID',
    'AlignReport',
    'AliyunAlignReport',
    'AliyunKBAligner',
    'AliyunPurgeReport',
    'PurgeReport',
    'VolcKBAligner',
    'build_file_name',
    'build_file_tags',
    'file_id_to_doc_id',
]
