"""临时维护脚本: 清理阿里云数据中心的孤儿文件.

孤儿文件 = 数据中心中存在, 但既不在知识库索引内、也没有
fileid_ 锚点标签的文件 (历史上中断重跑产生的重复副本).
不在索引内但带有 fileid_ 标签的文件是断点续传候选, 严禁误删.

安全保护:
    - 孤儿候选中处于解析流水线中间态
      (INIT/UPLOADING/UPLOADED/PARSING/IN_PARSE_QUEUE)
      的文件逐个跳过, 防止误杀在途对齐任务;
    - 默认预演只打印清单, 加 --apply 才真正删除.

用法:
    uv run python clean_aliyun_orphans.py            # 预演
    uv run python clean_aliyun_orphans.py --apply    # 实际删除
"""

import asyncio
import sys
from pathlib import Path


# 保证未安装项目包时也能直接运行
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from alibabacloud_bailian20231229 import models as bailian_models

from ipo_know.clients.aliyun_knowledge.client import FILE_FAILED_STATUSES
from ipo_know.clients.aliyun_knowledge.client import AliyunKnowledgeClient
from ipo_know.kb_align import AliyunKBAligner
from ipo_know.kb_align.aliyun_tags import extract_fileid


# 批量删除单批大小, 与对齐器保持一致.
DELETE_BATCH_SIZE = 10

# 数据中心文件解析处理中状态集合, 与对齐器的
# _PARSE_PENDING_STATUSES 保持一致, 处于这些状态的文件一律
# 跳过, 防止误杀在途任务.
PARSE_PENDING_STATUSES = frozenset({
    'INIT',
    'UPLOADING',
    'UPLOADED',
    'PARSING',
    'IN_PARSE_QUEUE',
})


async def main() -> None:
    """盘点孤儿文件并按模式清理."""
    apply = '--apply' in sys.argv[1:]
    if not apply:
        print('预演模式: 只打印孤儿清单, 不执行删除\n')

    aligner = AliyunKBAligner()
    client = AliyunKnowledgeClient()

    index_docs = await aligner.list_all_index_documents()
    index_ids = {doc.id for doc in index_docs if doc.id}
    dc_files = await client.list_all_data_center_files()

    unindexed = [f for f in dc_files if f.file_id not in index_ids]
    resume = [f for f in unindexed if extract_fileid(f.tags)]
    orphans = [f for f in unindexed if not extract_fileid(f.tags)]

    print(f'数据中心文件: {len(dc_files)} 个')
    print(f'索引内文档:   {len(index_ids)} 篇')
    print(f'断点续传候选 (不在索引, 有 fileid_ 标签): {len(resume)} 个')
    if resume:
        failed_resume = [f for f in resume if f.status in FILE_FAILED_STATUSES]
        for f in resume:
            hint = (
                '  [失败终态: 需跑一次 align 才会被回收]'
                if f.status in FILE_FAILED_STATUSES
                else ''
            )
            print(f'  {f.file_id} | {f.status} | {f.file_name}{hint}')
        if failed_resume:
            print(
                f'  ↑ 其中 {len(failed_resume)} 个处于失败终态, '
                '需先跑一次 align 才会被删除重传回收'
            )
    print(f'孤儿文件:     {len(orphans)} 个')

    if not orphans:
        print('无孤儿文件, 无需清理.')
        return

    in_flight = [f for f in orphans if f.status in PARSE_PENDING_STATUSES]
    if in_flight:
        orphans = [
            f for f in orphans if f.status not in PARSE_PENDING_STATUSES
        ]
        print(f'\n{len(in_flight)} 个文件处于解析中间态, 跳过不清理:')
        for f in in_flight:
            print(f'  {f.file_id} | {f.status} | {f.file_name}')
        if not orphans:
            print('跳过后无剩余孤儿文件, 无需清理.')
            return

    print('\n孤儿文件明细:')
    for f in orphans:
        print(f'  {f.file_id} | {f.status} | {f.file_name}')

    if not apply:
        print('\n确认无误后追加 --apply 执行删除.')
        return

    orphan_ids = [f.file_id for f in orphans]
    deleted = 0
    total = len(orphan_ids)
    for i in range(0, total, DELETE_BATCH_SIZE):
        batch = orphan_ids[i:i + DELETE_BATCH_SIZE]
        await client.delete_files(
            bailian_models.DeleteFilesRequest(file_ids=batch)
        )
        deleted += len(batch)
        print(f'删除进度 [{deleted}/{total}]')
    print(f'清理完成, 共删除 {deleted} 个孤儿文件.')


if __name__ == '__main__':
    asyncio.run(main())
