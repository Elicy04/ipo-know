"""北交所客户端集成测试脚本.

调用 BSEClient 按股票代码查询 IPO 项目及披露文件,
将结果以 JSON 格式保存到 tests/integration/output/ 目录.

用法:
    # 不使用代理
    python tests/integration/test_bse_client.py

    # 使用代理
    python tests/integration/test_bse_client.py --proxy http://127.0.0.1:7890
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

from ipo_know.clients.bse.client import BSEClient  # noqa: E402


OUTPUT_DIR = Path(__file__).resolve().parent / 'output'

# 已知测试股票代码
TEST_STOCK_CODE = '874386'


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
    """执行北交所客户端集成测试."""
    parser = argparse.ArgumentParser(description='北交所客户端集成测试')
    parser.add_argument(
        '--proxy', type=str, default=None,
        help='HTTP 代理地址, 如 http://127.0.0.1:7890',
    )
    args = parser.parse_args()

    _setup_proxy(args.proxy)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info('=' * 60)
    logger.info('北交所客户端集成测试开始')
    logger.info('=' * 60)

    client = BSEClient()

    # ---- 测试 1: query_project ----
    print(f'\n查询项目: stock_code={TEST_STOCK_CODE}')
    try:
        project = client.query_project(stock_code=TEST_STOCK_CODE)

        if project is None:
            _save_json(
                f'bse_project_{TEST_STOCK_CODE}.json',
                {'error': '未找到项目', 'stock_code': TEST_STOCK_CODE},
            )
            print(f'  [WARNING] 未找到股票代码 {TEST_STOCK_CODE} 的项目')
            print('\n[PARTIAL] 项目查询未返回数据, 跳过文件查询')
            return

        # 保存项目信息
        project_data = project.model_dump()
        out_project_path = _save_json(
            f'bse_project_{TEST_STOCK_CODE}.json',
            project_data,
        )

        # 打印项目摘要
        print('\n' + '=' * 50)
        print('北交所项目查询结果')
        print('=' * 50)
        print(f'  项目 ID:     {project.id}')
        print(f'  股票代码:    {project.stock_code}')
        print(f'  股票名称:    {project.stock_name}')
        print(f'  公司名称:    {project.company_name}')
        print(f'  审核状态:    {project.status}')
        print(f'  注册地址:    {project.register_address}')
        print(f'  更新日期:    {project.update_date}')
        print(f'  受理日期:    {project.receive_date}')
        print(f'  输出文件:    {out_project_path}')
        print('=' * 50)

    except Exception as exc:
        logger.exception('北交所项目查询失败')
        print(f'\n[FAILED] 北交所项目查询失败: {exc}')
        return

    # ---- 测试 2: query_project_files ----
    print(f'\n查询项目文件: project_id={project.id}')
    try:
        files = client.query_project_files(project_id=project.id)

        # 保存文件列表
        files_data = [f.model_dump() for f in files]
        out_files_path = _save_json(
            f'bse_project_files_{project.id}.json',
            files_data,
        )

        # 打印文件摘要
        print('\n' + '=' * 50)
        print('北交所项目文件查询结果')
        print('=' * 50)
        print(f'  项目 ID:     {project.id}')
        print(f'  文件总数:    {len(files)}')
        print(f'  输出文件:    {out_files_path}')
        print('=' * 50)

        if files:
            print('\n前 5 个文件:')
            for file_item in files[:5]:
                print(
                    f'  [{file_item.file_ext}] '
                    f'{file_item.disclosure_title}  '
                    f'({file_item.up_date})'
                )

        print('\n[SUCCESS] 北交所客户端测试通过')

    except Exception as exc:
        logger.exception('北交所项目文件查询失败')
        print(f'\n[FAILED] 北交所项目文件查询失败: {exc}')


if __name__ == '__main__':
    main()
