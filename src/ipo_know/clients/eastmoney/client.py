"""东方财富北交所 IPO 项目查询客户端.

提供 EastmoneyClient 类, 继承 BaseHttpClient, 封装东方财富数据中心
北交所 IPO 审核项目查询接口的调用逻辑.
"""

from typing import Any

from loguru import logger

from ipo_know.clients.eastmoney.models import EastmoneyIPOItem
from ipo_know.clients.eastmoney.models import EastmoneyIPOResult
from ipo_know.clients.http_client import BaseHttpClient
from ipo_know.clients.jsonp_utils import generate_jsonp_callback
from ipo_know.clients.jsonp_utils import parse_jsonp
from ipo_know.config.config import settings


class EastmoneyClient(BaseHttpClient):
    """东方财富北交所 IPO 项目查询客户端.

    继承 BaseHttpClient (httpx + hishel + tenacity), 封装东方财富
    数据中心 RPT_REGISTERED_INFO 报表查询接口, 支持分页查询与
    全量拉取北交所 IPO 项目信息.

    Attributes:
        base_url: 接口基础域名 (继承自 BaseHttpClient).
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
        cache_dir: str | None = None,
    ) -> None:
        """初始化东方财富客户端.

        Args:
            base_url: 接口基础域名, 默认从配置读取.
            timeout: HTTP 请求超时 (秒), 默认从配置读取.
            cache_dir: HTTP 缓存目录, 为 None 则不启用缓存.
        """
        resolved_url = (base_url or settings.eastmoney.base_url).rstrip('/')

        logger.info(
            '东方财富客户端初始化 | base_url={} | timeout={}s',
            resolved_url,
            timeout or settings.eastmoney.timeout,
        )

        super().__init__(
            base_url=resolved_url,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/126.0.0.0 Safari/537.36'
                ),
                'Referer': 'https://data.eastmoney.com/xg/ipo/',
                'Accept': '*/*',
            },
            timeout=timeout or settings.eastmoney.timeout,
            cache_dir=cache_dir,
        )

    # ==================================================
    # 业务接口
    # ==================================================
    def query_bse_ipo_projects(
        self,
        page_number: int = 1,
        page_size: int = 50,
    ) -> EastmoneyIPOResult:
        """查询北交所 IPO 项目列表 (单页).

        调用东方财富数据中心 RPT_REGISTERED_INFO 报表接口,
        筛选北交所上市板块, 返回分页结果.

        Args:
            page_number: 页码, 从 1 开始.
            page_size: 每页条数, 默认 50.

        Returns:
            包含分页信息与项目列表的查询结果.
        """
        params: dict[str, Any] = {
            'callback': generate_jsonp_callback(),
            'sortColumns': 'UPDATE_DATE,SECURITY_CODE',
            'sortTypes': '-1,-1',
            'pageSize': page_size,
            'pageNumber': page_number,
            'reportName': 'RPT_REGISTERED_INFO',
            'columns': 'ALL',
            'source': 'WEB',
            'client': 'WEB',
            'filter': '(TOLIST_MARKET="北交所")',
        }

        logger.info(
            '东方财富北交所 IPO 查询 | page={} | pageSize={}',
            page_number, page_size,
        )

        response = self.get('/api/data/v1/get', params=params)
        resp_data = parse_jsonp(response.text)

        result = resp_data.get('result', {})
        items = [
            {
                'security_code': item.get('SECURITY_CODE', ''),
                'csrc_industry': item.get('CSRC_INDUSTRY'),
            }
            for item in result.get('data', [])
        ]

        return EastmoneyIPOResult(
            pages=result.get('pages', 0),
            count=result.get('count', 0),
            data=items,
        )

    def query_all_bse_ipo_projects(self) -> list[EastmoneyIPOItem]:
        """拉取全部北交所 IPO 项目并按股票代码去重.

        首页查询获取总页数后串行遍历所有页, 合并结果并按
        security_code 去重, 返回完整项目列表.

        Returns:
            去重后的北交所 IPO 项目列表.
        """
        first_page = self.query_bse_ipo_projects(page_number=1)
        total_pages = first_page.pages

        logger.info(
            '东方财富全量拉取 | 总页数={} | 总记录={}',
            total_pages, first_page.count,
        )

        seen_codes: set[str] = set()
        merged: list[EastmoneyIPOItem] = []

        # 合并首页结果
        for item in first_page.data:
            if item.security_code not in seen_codes:
                seen_codes.add(item.security_code)
                merged.append(item)

        # 串行遍历剩余页
        for page in range(2, total_pages + 1):
            result = self.query_bse_ipo_projects(page_number=page)
            for item in result.data:
                if item.security_code not in seen_codes:
                    seen_codes.add(item.security_code)
                    merged.append(item)
            logger.info(
                '东方财富全量拉取 | 第{}/{}页 | 累计唯一项目 {} 个',
                page, total_pages, len(merged),
            )

        logger.info(
            '东方财富全量拉取完成 | 共 {} 个唯一项目',
            len(merged),
        )
        return merged
