"""深交所客户端集成测试脚本.

调用 SZSEClient 查询 IPO 项目列表及披露文件,
将结果以 JSON 格式保存到 tests/integration/output/ 目录.

用法:
    # 不使用代理
    python tests/integration/test_szse_client.py

    # 使用代理
    python tests/integration/test_szse_client.py --proxy http://127.0.0.1:7890
"""

import argparse
import json
import os
import sys
from pathlib import Path

from loguru import logger


# 将项目根目录加入 sys.path, 确保可以直接运行脚本
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from ipo_know.clients.szse.client import SZSEClient  # noqa: E402


OUTPUT_DIR = Path(__file__).resolve().parent / 'output'

# 测试查询参数
TEST_INDUSTRY = '汽车制造业'
TEST_PAGE_SIZE = 5


def _setup_proxy(proxy: str | None) -> None:
    """设置 HTTP 代理环境变量.

    httpx 在创建 Client 时会读取 HTTP_PROXY / HTTPS_PROXY 环境变量,
    通过设置环境变量实现代理透传, 无需修改客户端代码.

    Args:
        proxy: 代理 URL, 如 http://127.0.0.1:7890; None 时不设置.
    """
    if proxy:
        os.environ['HTTP_PROXY'] = proxy
        os.environ['HTTPS_PROXY'] = proxy
        os.environ['http_proxy'] = proxy
        os.environ['https_proxy'] = proxy
        logger.info('代理已设置: {}', proxy)
    else:
        for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
            os.environ.pop(key, None)
        logger.info('未使用代理')


def _save_json(filename: str, data: object) -> Path:
    """将数据保存为 JSON 文件.

    Args:
        filename: 输出文件名.
        data: 可序列化的数据对象.

    Returns:
        输出文件的完整路径.
    """
    out_path = OUTPUT_DIR / filename
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    logger.info('结果已保存到 {}', out_path)
    return out_path


def main() -> None:
    """执行深交所客户端集成测试."""
    parser = argparse.ArgumentParser(description='深交所客户端集成测试')
    parser.add_argument(
        '--proxy', type=str, default=None,
        help='HTTP 代理地址, 如 http://127.0.0.1:7890',
    )
    args = parser.parse_args()

    _setup_proxy(args.proxy)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info('=' * 60)
    logger.info('深交所客户端集成测试开始')
    logger.info('=' * 60)

    client = SZSEClient()

    # ---- 测试 1: query_projects ----
    print(f'\n查询项目: industry={TEST_INDUSTRY}, page_size={TEST_PAGE_SIZE}')
    try:
        projects, total_size = client.query_projects(
            industry=TEST_INDUSTRY,
            page_size=TEST_PAGE_SIZE,
        )

        # 保存项目列表
        projects_data = [p.model_dump(by_alias=True) for p in projects]
        out_projects_path = _save_json(
            'szse_projects_auto.json',
            {'total_size': total_size, 'data': projects_data},
        )

        # 打印项目摘要
        print('\n' + '=' * 50)
        print('深交所项目查询结果')
        print('=' * 50)
        print(f'  行业筛选:    {TEST_INDUSTRY}')
        print(f'  总项目数:    {total_size}')
        print(f'  本页返回:    {len(projects)} 条')
        print(f'  输出文件:    {out_projects_path}')
        print('=' * 50)

        if projects:
            print('\n项目列表:')
            for proj in projects:
                print(
                    f'  prjid={proj.prjid}  '
                    f'公司={proj.cmpnm}  '
                    f'状态={proj.prjst}  '
                    f'板块={proj.board_name}'
                )

    except Exception as exc:
        logger.exception('深交所项目查询失败')
        print(f'\n[FAILED] 深交所项目查询失败: {exc}')
        return

    # ---- 测试 2: query_project_files ----
    if not projects:
        print('\n[PARTIAL] 未查到项目, 跳过文件查询')
        return

    first_prjid = projects[0].prjid
    first_cmpnm = projects[0].cmpnm
    print(f'\n查询项目文件: prjid={first_prjid} ({first_cmpnm})')

    try:
        files = client.query_project_files(project_id=first_prjid)

        # 保存文件列表
        files_data = [f.model_dump() for f in files]
        out_files_path = _save_json(
            f'szse_project_files_{first_prjid}.json',
            files_data,
        )

        # 打印文件摘要
        print('\n' + '=' * 50)
        print('深交所项目文件查询结果')
        print('=' * 50)
        print(f'  项目 ID:     {first_prjid}')
        print(f'  公司名称:    {first_cmpnm}')
        print(f'  文件总数:    {len(files)}')
        print(f'  输出文件:    {out_files_path}')
        print('=' * 50)

        if files:
            print('\n前 5 个文件:')
            for file_item in files[:5]:
                print(
                    f'  [{file_item.dfext}] '
                    f'{file_item.dfnm or file_item.matnm}  '
                    f'({file_item.ddt})'
                )

        print('\n[SUCCESS] 深交所客户端测试通过')

    except Exception as exc:
        logger.exception('深交所项目文件查询失败')
        print(f'\n[FAILED] 深交所项目文件查询失败: {exc}')


if __name__ == '__main__':
    main()
