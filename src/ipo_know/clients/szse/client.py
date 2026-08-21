"""深交所注册制审核信息披露客户端.

提供 SZSEClient 类, 继承 BaseHttpClient, 封装深交所 IPO 项目
查询与披露文件查询等公开接口的调用逻辑.
"""

import random

from loguru import logger

from ipo_know.clients.http_client import BaseHttpClient
from ipo_know.clients.szse.models import SZSEFileItem
from ipo_know.clients.szse.models import SZSEProjectItem
from ipo_know.config.config import settings


# 详情接口中所有文件数组字段名
_FILE_ARRAY_KEYS: tuple[str, ...] = (
    'disclosureMaterials',
    'enquiryResponseAttachment',
    'meetingConclusionAttachment',
    'terminationNoticeAttachment',
    'registrationResultAttachment',
    'cashReorganizationResultAttachment',
    'ntbListedResultAttachment',
    'others',
)


class SZSEClient(BaseHttpClient):
    """深交所注册制审核信息披露客户端.

    继承 BaseHttpClient (httpx + hishel + tenacity), 提供深交所
    IPO 项目列表查询与单项目披露文件查询能力.

    接口特点:
        - 纯 JSON 响应, 无需 JSONP 解析
        - boardName 字段通过 Pydantic alias 映射为 board_name

    Attributes:
        base_url: 接口基础域名 (继承自 BaseHttpClient).
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
        cache_dir: str | None = None,
    ) -> None:
        """初始化深交所客户端.

        Args:
            base_url: 接口基础域名, 默认从配置读取.
            timeout: HTTP 请求超时 (秒), 默认从配置读取.
            cache_dir: HTTP 缓存目录, 为 None 则不启用缓存.
        """
        resolved_url = (base_url or settings.szse.base_url).rstrip('/')
        resolved_timeout = (
            timeout if timeout is not None else settings.szse.timeout
        )

        logger.info(
            '深交所客户端初始化 | base_url={} | timeout={}s',
            resolved_url, resolved_timeout,
        )

        super().__init__(
            base_url=resolved_url,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/126.0.0.0 Safari/537.36'
                ),
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
                'X-Request-Type': 'ajax',
                'Referer': (
                    'https://www.szse.cn/disclosure/listed'
                    '/registration/index.html'
                ),
            },
            timeout=resolved_timeout,
            cache_dir=cache_dir,
        )

    # ==================================================
    # 项目查询
    # ==================================================
    def query_projects(
        self,
        industry: str | None = None,
        biz_type: int = 1,
        page_index: int = 0,
        page_size: int = 10,
    ) -> tuple[list[SZSEProjectItem], int]:
        """查询深交所注册制审核项目列表.

        Args:
            industry: 行业筛选 (中文, 如 "汽车制造业"), None 时不传.
            biz_type: 业务类型, 默认 1 (IPO).
            page_index: 页码索引, 从 0 开始.
            page_size: 每页条数.

        Returns:
            (项目列表, 总条数) 元组.
        """
        params: dict[str, object] = {
            'bizType': biz_type,
            'random': random.random(),
            'pageIndex': page_index,
            'pageSize': page_size,
        }
        if industry is not None:
            params['industry'] = industry

        logger.info(
            '深交所项目查询 | industry={} | bizType={} | page={}/{}',
            industry, biz_type, page_index, page_size,
        )

        resp = self.get('/api/ras/projectrends/query', params=params)
        data = resp.json()

        total_size: int = data.get('totalSize', 0)
        items = [
            SZSEProjectItem(**item)
            for item in data.get('data', [])
        ]

        logger.info(
            '深交所项目查询结果 | 本页 {} 条 | 总计 {} 条',
            len(items), total_size,
        )
        return items, total_size

    # ==================================================
    # 项目文件查询
    # ==================================================
    def query_project_files(
        self,
        project_id: int,
    ) -> list[SZSEFileItem]:
        """查询单项目全部披露文件.

        合并 disclosureMaterials / enquiryResponseAttachment /
        meetingConclusionAttachment / registrationResultAttachment
        等多个数组为扁平文件列表.

        Args:
            project_id: 项目 ID (prjid).

        Returns:
            扁平化的披露文件列表.
        """
        params: dict[str, object] = {
            'id': project_id,
            'r': random.random(),
        }

        logger.info('深交所项目文件查询 | project_id={}', project_id)

        resp = self.get('/api/ras/projectrends/details', params=params)
        data = resp.json()

        # 部分终止类项目返回顶层 data 或文件数组为 null,
        # .get 默认值对键存在值为 null 的情况无效, 需用 or 兜底
        project_data = data.get('data') or {}
        files: list[SZSEFileItem] = []

        for key in _FILE_ARRAY_KEYS:
            for raw in project_data.get(key) or []:
                if not isinstance(raw, dict):
                    continue
                item = SZSEFileItem(**raw)
                if item.dfpth is not None:
                    files.append(item)

        logger.info(
            '深交所项目文件查询结果 | project_id={} | 文件数={}',
            project_id, len(files),
        )
        return files

    # ==================================================
    # 工具方法
    # ==================================================
    @staticmethod
    def build_file_url(file_path: str) -> str:
        """构建文件完整下载 URL.

        Args:
            file_path: 文件相对路径, 如 /UpFiles/rasinfodisc1/...

        Returns:
            完整 URL, 如 https://reportdocs.static.szse.cn/UpFiles/...
        """
        return 'https://reportdocs.static.szse.cn' + file_path
