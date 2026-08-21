"""北交所爬虫集成测试脚本.

调用 BSEIPOCrawler 采集汽车制造业有效文件清单,
将结果以 JSON 格式保存到 tests/integration/output/ 目录.

用法:
    # 不使用代理
    python tests/integration/test_bse_crawler.py

    # 使用代理
    python tests/integration/test_bse_crawler.py --proxy http://127.0.0.1:7890
"""

import argparse
import os
import sys
from pathlib import Path

from loguru import logger


# 将项目根目录加入 sys.path, 确保可以直接运行脚本
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from ipo_know.crawler.bse_ipo_crawler import BSEIPOCrawler  # noqa: E402


OUTPUT_DIR = Path(__file__).resolve().parent / 'output'

# 测试查询参数
TEST_CSRC_INDUSTRY = '汽车制造业'
PREVIEW_COUNT = 5


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


def main() -> None:
    """执行北交所爬虫集成测试."""
    parser = argparse.ArgumentParser(description='北交所爬虫集成测试')
    parser.add_argument(
        '--proxy', type=str, default=None,
        help='HTTP 代理地址, 如 http://127.0.0.1:7890',
    )
    args = parser.parse_args()

    _setup_proxy(args.proxy)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info('=' * 60)
    logger.info('北交所爬虫集成测试开始')
    logger.info('=' * 60)

    crawler = BSEIPOCrawler()

    # ---- 采集有效文件清单 ----
    print(f'\n采集有效文件: csrc_industry={TEST_CSRC_INDUSTRY}')
    try:
        files = crawler.collect(csrc_industry=TEST_CSRC_INDUSTRY)
    except Exception as exc:
        logger.exception('北交所文件采集失败')
        print(f'\n[FAILED] 北交所文件采集失败: {exc}')
        return

    # ---- 保存结果 ----
    out_path = crawler.save(files, OUTPUT_DIR)
    logger.info('结果已保存到 {}', out_path)

    # ---- 打印摘要 ----
    print('\n' + '=' * 50)
    print('北交所爬虫采集结果')
    print('=' * 50)
    print(f'  行业筛选:    {TEST_CSRC_INDUSTRY}')
    print(f'  有效文件数:  {len(files)}')
    print(f'  输出文件:    {out_path}')
    print('=' * 50)

    if files:
        print(f'\n前 {PREVIEW_COUNT} 条记录:')
        for record in files[:PREVIEW_COUNT]:
            print(
                f'  [{record.get("auditId", "")}] '
                f'{record.get("companyName", "")} - '
                f'{record.get("fileName", "")}'
            )

    print('\n[SUCCESS] 北交所爬虫测试通过')


if __name__ == '__main__':
    main()
