"""临时维护脚本: 清理阿里云数据中心的孤儿文件.

孤儿文件 = 数据中心中存在, 但既不在知识库索引内、也不在本地
映射中的文件 (历史上中断重跑产生的重复副本).

安全保护:
    - 若孤儿中存在解析中 (INIT/PARSING) 的文件, 说明可能有
      对齐任务正在运行, 直接中止;
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

from ipo_know.clients.aliyun_knowledge.client import AliyunKnowledgeClient
from ipo_know.kb_align import AliyunKBAligner
from ipo_know.kb_align import FileMappingStore


# 批量删除单批大小, 与对齐器保持一致.
DELETE_BATCH_SIZE = 10


async def get_default_category_id(client: AliyunKnowledgeClient) -> str:
    """查询非结构化默认类目的真实 ID."""
    resp = await client._api_call(
        client._get_client().list_category,
        client.workspace_id,
        bailian_models.ListCategoryRequest(category_type='UNSTRUCTURED'),
    )
    cats = resp.body.data.category_list or []
    for cat in cats:
        if cat.category_name == '默认类目':
            return cat.category_id
    if cats:
        return cats[0].category_id
    raise RuntimeError('未找到任何非结构化类目')


async def list_all_data_center_files(
    client: AliyunKnowledgeClient, category_id: str,
) -> list:
    """分页拉取数据中心全部文件."""
    files = []
    next_token = None
    while True:
        request = bailian_models.ListFileRequest(
            category_id=category_id, max_results=100,
        )
        if next_token:
            request.next_token = next_token
        resp = await client.list_file(request)
        data = resp.body.data
        if data and data.file_list:
            files.extend(data.file_list)
        if data and data.has_next and data.next_token:
            next_token = data.next_token
        else:
            break
    return files


async def main() -> None:
    """盘点孤儿文件并按模式清理."""
    apply = '--apply' in sys.argv[1:]
    if not apply:
        print('预演模式: 只打印孤儿清单, 不执行删除\n')

    aligner = AliyunKBAligner()
    client = AliyunKnowledgeClient()
    mapping = FileMappingStore()

    mapped_ids = {aliyun_id for _, aliyun_id in mapping.items()}
    index_docs = await aligner.list_all_index_documents()
    index_ids = {doc.id for doc in index_docs if doc.id}

    category_id = await get_default_category_id(client)
    dc_files = await list_all_data_center_files(client, category_id)

    orphans = [
        f for f in dc_files
        if f.file_id not in index_ids and f.file_id not in mapped_ids
    ]
    print(f'数据中心文件: {len(dc_files)} 个')
    print(f'索引内文档:   {len(index_ids)} 篇')
    print(f'本地映射条目: {len(mapping)} 条')
    print(f'孤儿文件:     {len(orphans)} 个')

    if not orphans:
        print('无孤儿文件, 无需清理.')
        return

    in_flight = [f for f in orphans if f.status in ('INIT', 'PARSING')]
    if in_flight:
        print(f'\n发现 {len(in_flight)} 个解析中的孤儿文件, '
              '可能有对齐任务正在运行, 中止清理:')
        for f in in_flight:
            print(f'  {f.file_id} | {f.status} | {f.file_name}')
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
