"""临时脚本: 清空火山知识库 (初始化用).

删除知识库中的全部切片与全部文档. 切片拉取不按 doc_id 过滤,
可覆盖文档已删除但切片残留的孤儿切片; 执行前需输入 DELETE
二次确认, --dry-run 仅盘点数量不删除.

用法:
    uv run python purge_kb_volc.py --dry-run  # 只盘点文档/切片数量
    uv run python purge_kb_volc.py            # 交互确认后清库
"""

import asyncio
import sys
from pathlib import Path


# 保证未安装项目包时也能直接运行
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ipo_know.kb_align import VolcKBAligner


async def main() -> None:
    """盘点并清空火山知识库."""
    dry_run = '--dry-run' in sys.argv[1:]
    aligner = VolcKBAligner()

    if not dry_run:
        answer = input('此操作将删除知识库全部文档与切片, '
                       '输入 DELETE 确认执行: ')
        if answer.strip() != 'DELETE':
            print('已取消, 未执行任何删除')
            return

    report = await aligner.purge(dry_run=dry_run)

    print('\n' + '=' * 62)
    print(f'盘点: 文档 {report.total_docs} 篇 | '
          f'切片 {report.total_points} 个')
    if not dry_run:
        print(f'已删除: 文档 {report.deleted_docs} 篇 | '
              f'切片 {report.deleted_points} 个')
        if report.failed:
            print(f'失败 {len(report.failed)} 项:')
            for item_id, reason in report.failed:
                print(f'  - {item_id}: {reason}')
    print('=' * 62)


if __name__ == '__main__':
    asyncio.run(main())
