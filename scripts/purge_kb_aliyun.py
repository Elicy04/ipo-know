"""临时脚本: 清空阿里云百炼知识库 (初始化用).

删除知识库索引中的全部文档, 并同步删除对应数据中心文件
(索引内文件与本地映射记录的文件取并集). 阿里云切片随索引文档
删除而删除, 不单独处理孤儿切片; 执行前需输入 DELETE 二次确认,
--dry-run 仅盘点数量不删除.

用法:
    uv run python purge_kb_aliyun.py --dry-run  # 只盘点数量
    uv run python purge_kb_aliyun.py            # 交互确认后清库
"""

import asyncio
import sys
from pathlib import Path


# 保证未安装项目包时也能直接运行
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ipo_know.kb_align import AliyunKBAligner


async def main() -> None:
    """盘点并清空阿里云知识库."""
    dry_run = '--dry-run' in sys.argv[1:]
    aligner = AliyunKBAligner()

    if not dry_run:
        answer = input('此操作将删除知识库全部文档与数据中心文件, '
                       '输入 DELETE 确认执行: ')
        if answer.strip() != 'DELETE':
            print('已取消, 未执行任何删除')
            return

    report = await aligner.purge(dry_run=dry_run)

    print('\n' + '=' * 62)
    print(f'盘点: 索引文档 {report.total_docs} 篇 | '
          f'本地映射 {report.total_mapped_files} 条')
    if not dry_run:
        print(f'已删除: 索引文档 {report.deleted_docs} 篇 | '
              f'数据中心文件 {report.deleted_files} 个')
        if report.failed:
            print(f'失败 {len(report.failed)} 项:')
            for item_id, reason in report.failed:
                print(f'  - {item_id}: {reason}')
    print('=' * 62)


if __name__ == '__main__':
    asyncio.run(main())
