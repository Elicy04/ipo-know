"""深交所注册制审核项目文件爬虫模块.

依赖深交所客户端按行业筛选 IPO 项目, 逐项拉取披露文件列表,
按同名文件保留最新版本的规则去重, 最终输出兼容上交所格式的
文件清单 JSON.
"""

import json
import math
import re
import time
from pathlib import Path
from typing import Any

from loguru import logger

from ipo_know.clients.szse.client import SZSEClient
from ipo_know.clients.szse.models import SZSEFileItem
from ipo_know.clients.szse.models import SZSEProjectItem


# 深交所项目查询默认分页大小
_SZSE_QUERY_PAGE_SIZE = 100

# 深交所文件静态资源域名
_SZSE_STATIC_BASE_URL = 'https://reportdocs.static.szse.cn'

# 披露日期中的非数字字符 (如 YYYY-MM-DD 中的连字符)
_NON_DIGIT_RE = re.compile(r'\D+')


def normalize_upd_date(value: str | None) -> str:
    """将披露日期规范化为 YYYYMMDD 纯数字格式.

    深交所 ddt 字段为 YYYY-MM-DD 形式, 对齐器取前 8 位作日期
    后缀, 直接截断会得到带连字符的残缺结果, 需先去非数字字符.

    Args:
        value: 原始披露日期字符串, 可为 None.

    Returns:
        至多 8 位纯数字日期字符串; 无法解析时为空串.
    """
    return _NON_DIGIT_RE.sub('', value or '')[:8]


class SZSEIPOCrawler:
    """深交所注册制审核文件爬虫.

    流程: 按行业查询项目列表(分页) → 逐项拉取文件清单 →
    同名文件保留最新版本 → 输出文件清单 JSON.

    Attributes:
        request_interval: 相邻查询请求间隔 (秒), 控制目标站点压力.
    """

    def __init__(
        self,
        request_interval: float = 0.3,
        client: SZSEClient | None = None,
    ) -> None:
        """初始化爬虫.

        Args:
            request_interval: 相邻查询请求间隔 (秒).
            client: 可复用的深交所客户端, 为 None 时由 collect 自动创建.
        """
        self._request_interval = request_interval
        self._client = client

    def collect(
        self,
        industry: str = '汽车制造业',
    ) -> list[dict[str, Any]]:
        """采集并去重, 返回有效文件清单.

        仅负责网络采集与同名文件去重, 不涉及文件落盘; 需要持久化
        时把返回值交给 save.

        Args:
            industry: 行业筛选 (中文, 如 "汽车制造业").

        Returns:
            有效文件清单, 每条为项目与文件信息组合的字典,
            filePath 已拼接为完整下载 URL.
        """
        client = self._client
        owns_client = client is None
        if client is None:
            client = SZSEClient()

        try:
            projects = self._fetch_all_projects(client, industry)
            pairs = self._fetch_files(client, projects)
            valid_pairs = self._select_valid_files(pairs)
            files = [self._build_record(proj, f) for proj, f in valid_pairs]
            logger.info(
                '有效文件筛选完成 | 有效 {} / 原始 {} 个',
                len(valid_pairs), len(pairs),
            )
            return files
        finally:
            if owns_client:
                client.close()

    def save(self, files: list[dict[str, Any]], output_dir: str | Path) -> Path:
        """将文件清单写入 JSON.

        Args:
            files: 由 collect 返回的有效文件清单.
            output_dir: 输出目录, JSON 清单将写入其中.

        Returns:
            生成的文件清单 JSON 路径.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'szse_valid_files.json'
        output_path.write_text(
            json.dumps(files, ensure_ascii=False, indent=2), encoding='utf-8',
        )
        logger.info(
            '深交所有效文件清单已生成 | {} 个 | 路径 {}',
            len(files), output_path,
        )
        return output_path

    # ==================================================
    # 采集
    # ==================================================
    def _fetch_all_projects(
        self,
        client: SZSEClient,
        industry: str,
    ) -> list[SZSEProjectItem]:
        """分页拉取指定行业的全部 IPO 项目.

        先获取第一页与总条数, 再按 _SZSE_QUERY_PAGE_SIZE 循环拉取后续页.

        Args:
            client: 深交所客户端实例.
            industry: 行业筛选 (中文).

        Returns:
            全部项目条目列表.
        """
        first_page, total_size = client.query_projects(
            industry=industry, page_size=_SZSE_QUERY_PAGE_SIZE,
        )
        all_projects: list[SZSEProjectItem] = list(first_page)

        total_pages = math.ceil(total_size / _SZSE_QUERY_PAGE_SIZE)
        for page_idx in range(1, total_pages):
            time.sleep(self._request_interval)
            page_items, _ = client.query_projects(
                industry=industry, page_index=page_idx,
                page_size=_SZSE_QUERY_PAGE_SIZE,
            )
            all_projects.extend(page_items)

        logger.info(
            '深交所项目查询完成 | industry={} | 项目总数 {}',
            industry, len(all_projects),
        )
        return all_projects

    def _fetch_files(
        self,
        client: SZSEClient,
        projects: list[SZSEProjectItem],
    ) -> list[tuple[SZSEProjectItem, SZSEFileItem]]:
        """拉取全部项目的披露文件.

        Args:
            client: 深交所客户端实例.
            projects: 项目列表.

        Returns:
            (项目, 文件) 元组列表.
        """
        pairs: list[tuple[SZSEProjectItem, SZSEFileItem]] = []

        for idx, project in enumerate(projects, start=1):
            try:
                file_items = client.query_project_files(project.prjid)
            except Exception as exc:  # 单项目失败不中断
                logger.warning(
                    '[{}/{}] {} 文件查询失败: {}',
                    idx, len(projects), project.cmpnm, exc,
                )
                time.sleep(self._request_interval)
                continue

            for file_item in file_items:
                pairs.append((project, file_item))

            logger.info(
                '[{}/{}] {} → {} 个文件',
                idx, len(projects), project.cmpnm, len(file_items),
            )
            time.sleep(self._request_interval)

        return pairs

    # ==================================================
    # 有效文件筛选
    # ==================================================
    @staticmethod
    def _select_valid_files(
        pairs: list[tuple[SZSEProjectItem, SZSEFileItem]],
    ) -> list[tuple[SZSEProjectItem, SZSEFileItem]]:
        """同名文件去重, 每个项目每个文件名仅保留最新版本.

        按 (project.prjid, file_item.dfnm) 分组, 每组内按 ddt
        降序排列, 保留第一条 (最新版本).

        Args:
            pairs: (项目, 文件) 元组列表.

        Returns:
            筛选后的 (项目, 文件) 元组列表.
        """
        groups: dict[
            tuple[int, str | None],
            list[tuple[SZSEProjectItem, SZSEFileItem]],
        ] = {}
        for pair in pairs:
            key = (pair[0].prjid, pair[1].dfnm)
            groups.setdefault(key, []).append(pair)

        valid: list[tuple[SZSEProjectItem, SZSEFileItem]] = []
        for group_items in groups.values():
            # 按披露日期 ddt 降序, None 排末尾
            group_items.sort(
                key=lambda p: p[1].ddt or '', reverse=True,
            )
            valid.append(group_items[0])

        return valid

    # ==================================================
    # 输出
    # ==================================================
    @classmethod
    def _build_record(
        cls,
        project: SZSEProjectItem,
        file_item: SZSEFileItem,
    ) -> dict[str, Any]:
        """将项目与文件条目组合为清单记录.

        Args:
            project: 项目条目.
            file_item: 文件条目.

        Returns:
            文件清单字典, filePath 为完整下载 URL; fileTypeMap
            取材料名称 matnm, fileTitle 取文件名 dfnm,
            fileUpdTime 规范化为 YYYYMMDD.
        """
        return {
            'auditId': str(project.prjid),
            'companyAbbr': project.cmpsnm,
            'companyName': project.cmpnm,
            'fileName': file_item.dfnm,
            'fileId': Path(file_item.dfpth).stem,
            'filePath': cls.build_file_url(file_item.dfpth),
            'fileUpdTime': normalize_upd_date(file_item.ddt),
            'fileTypeMap': file_item.matnm or '',
            'fileTitle': file_item.dfnm or '',
        }

    @staticmethod
    def build_file_url(file_path: str) -> str:
        """构建文件完整下载 URL.

        使用深交所静态资源域名 reportdocs.static.szse.cn.

        Args:
            file_path: 文件相对路径, 如 /UpFiles/rasinfodisc1/...

        Returns:
            完整 URL, 如 https://reportdocs.static.szse.cn/UpFiles/...
        """
        return _SZSE_STATIC_BASE_URL + file_path
