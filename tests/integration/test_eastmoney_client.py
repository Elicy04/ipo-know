"""东方财富客户端集成测试脚本.

调用 EastmoneyClient 查询北交所 IPO 项目列表,
将结果以 JSON 格式保存到 tests/integration/output/ 目录.

用法:
    # 不使用代理
    python tests/integration/test_eastmoney_client.py

    # 使用代理
    python tests/integration/test_eastmoney_client.py --proxy http://127.0.0.1:7890
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

from ipo_know.clients.eastmoney.client import EastmoneyClient  # noqa: E402


OUTPUT_DIR = Path(__file__).resolve().parent / 'output'


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
    """执行东方财富客户端集成测试."""
    parser = argparse.ArgumentParser(description='东方财富客户端集成测试')
    parser.add_argument(
        '--proxy', type=str, default=None,
        help='HTTP 代理地址, 如 http://127.0.0.1:7890',
    )
    args = parser.parse_args()

    _setup_proxy(args.proxy)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info('=' * 60)
    logger.info('东方财富客户端集成测试开始')
    logger.info('=' * 60)

    client = EastmoneyClient()

    # ---- 测试 query_bse_ipo_projects ----
    try:
        result = client.query_bse_ipo_projects(page_number=1, page_size=10)

        # 保存结果
        out_data = {
            'pages': result.pages,
            'count': result.count,
            'data': [item.model_dump() for item in result.data],
        }
        out_path = _save_json('eastmoney_bse_ipo_projects_page1.json', out_data)

        # 打印摘要
        print('\n' + '=' * 50)
        print('东方财富北交所 IPO 项目查询结果')
        print('=' * 50)
        print(f'  总页数:         {result.pages}')
        print(f'  总条数:         {result.count}')
        print(f'  第一页数据条数: {len(result.data)}')
        print(f'  输出文件:       {out_path}')
        print('=' * 50)

        if result.data:
            print('\n前 5 条项目:')
            for item in result.data[:5]:
                print(
                    f'  股票代码={item.security_code}  '
                    f'行业={item.csrc_industry}'
                )

        print('\n[SUCCESS] 东方财富客户端测试通过')

    except Exception as exc:
        logger.exception('东方财富客户端测试失败')
        print(f'\n[FAILED] 东方财富客户端测试失败: {exc}')


if __name__ == '__main__':
    main()
