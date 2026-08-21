"""临时脚本: 一键对齐 C36 有效文件清单与火山知识库.

流程:
    1. 调用 crawler 采集汽车制造业(C36)、主板+科创板、全审核状态
       的有效披露文件清单;
    2. 调用 kb_align 将清单与火山 VikingDB 知识库做全量对齐:
       清单有而知识库缺失的文档按 fileId 补充, 知识库有而不在
       清单内的文档先删切片再删文档.

行为变更说明:
    孤儿删除现按 sse_ 前缀隔离, 仅删除本数据源前缀的孤儿文档,
    不再清理无前缀或其他数据源前缀的文档. 首次运行建议先加
    --dry-run 确认待增删差异.

用法:
    uv run python align_kb_c36_volc.py            # 实际执行增删
    uv run python align_kb_c36_volc.py --dry-run  # 只打印差异不执行
"""

import asyncio
import sys
from pathlib import Path


# 保证未安装项目包时也能直接运行
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ipo_know.crawler import SSEIPOCrawler
from ipo_know.kb_align import VolcKBAligner


# 脚本链路保持历史行为: 显式使用原硬编码切片策略 ID.
# 来源: kb_align/volc_aligner.py 原 STRATEGY_RESOURCE_ID
# 常量; VolcKBAligner 默认值已改为留空 (走知识库默认
# 切片策略), 脚本场景不受影响.
STRATEGY_RESOURCE_ID = 'kb-strategy-59c0da9fd88c3b5a'


async def main() -> None:
    """采集有效清单并对齐火山知识库."""
    dry_run = '--dry-run' in sys.argv[1:]
    if dry_run:
        print('预演模式: 只打印差异, 不执行增删\n')

    crawler = SSEIPOCrawler()
    files = crawler.collect()
    print(f'\n有效文件清单: {len(files)} 篇, 开始对齐火山知识库...\n')

    aligner = VolcKBAligner(
        strategy_resource_id=STRATEGY_RESOURCE_ID,
    )
    report = await aligner.align(files, dry_run=dry_run)

    print('\n' + '=' * 62)
    print(f'知识库现有文档: {report.total_kb_docs} 篇')
    print(f'待补充: {report.to_add_count} 篇 | '
          f'待删除: {report.to_delete_count} 篇')
    if not dry_run:
        print(f'实际补充: {len(report.added)} 篇 | '
              f'实际删除: {len(report.deleted)} 篇')
        print(f'已存在跳过: {len(report.skipped_existing)} 篇')
        if report.failed_adds:
            print(f'补充失败: {len(report.failed_adds)} 篇')
            for doc_id, reason in report.failed_adds:
                print(f'  - {doc_id}: {reason}')
        if report.failed_deletes:
            print(f'删除失败: {len(report.failed_deletes)} 篇')
            for doc_id, reason in report.failed_deletes:
                print(f'  - {doc_id}: {reason}')
        if report.parse_failed:
            print(f'解析失败: {len(report.parse_failed)} 篇')
            for doc_id, reason in report.parse_failed:
                print(f'  - {doc_id}: {reason}')
    print('=' * 62)


if __name__ == '__main__':
    asyncio.run(main())
