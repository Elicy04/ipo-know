"""临时脚本: 测试 SSEClient 两个核心接口, 结果保存到项目根目录."""
import json
import sys
from pathlib import Path

from ipo_know.clients.sse.client import SSEClient

ROOT = Path(__file__).parent


def save_json(filename: str, data: object) -> Path:
    """保存 JSON 到项目根目录, 返回文件路径."""
    path = ROOT / filename
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding='utf-8',
    )
    print(f'[OK] 已保存: {path}')
    return path


def main() -> None:
    client = SSEClient()

    try:
        # 1. 项目查询
        print('=' * 60)
        print('[1/2] 测试 query_projects (汽车制造业) ...')
        result1 = client.query_projects(csrc_code='C36')
        total = result1.pageHelp.total
        project_count = len(result1.pageHelp.data)
        print(
            f'      C36 汽车制造业: 共 {total} 条, '
            f'当前页 {project_count} 条'
        )
        save_json(
            'sse_query_projects_C36.json',
            result1.model_dump(),
        )

        # 2. 文件查询 (取第一个项目的 auditId)
        if result1.pageHelp.data:
            first_project = result1.pageHelp.data[0]
            audit_id = first_project.stockAuditNum
            project_name = first_project.stockAuditName
            print()
            print(
                f'[2/2] 测试 query_files (audit_id={audit_id}, '
                f'{project_name}) ...'
            )
            result2 = client.query_files(audit_id=audit_id)
            file_count = len(result2.pageHelp.data)
            print(f'      披露文件数: {file_count}')
            save_json(
                f'sse_query_files_{audit_id}.json',
                result2.model_dump(),
            )
        else:
            print('[2/2] 跳过: 无项目数据可供文件查询')

        print()
        print('=' * 60)
        print('全部测试完成, 结果文件已保存至项目根目录.')
    finally:
        client.close()


if __name__ == '__main__':
    sys.exit(main())
