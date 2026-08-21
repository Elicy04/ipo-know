"""北交所 IPO 披露文件爬虫模块.

依赖东方财富客户端获取全量北交所 IPO 项目清单, 筛选指定行业后
通过北交所客户端逐项拉取披露文件, 按阶段时效性筛选有效文件,
最终输出兼容上交所格式的文件清单 JSON.
"""

import json
import re
import time
from pathlib import Path
from typing import Any

from loguru import logger

from ipo_know.clients.bse.client import BSEClient
from ipo_know.clients.bse.models import BSEFileItem
from ipo_know.clients.bse.models import BSEProjectItem
from ipo_know.clients.eastmoney.client import EastmoneyClient


# 阶段后缀正则（兼容全角/半角括号）
_STAGE_SUFFIX_RE = re.compile(r'[（(][^）)]*稿[）)]\s*$')

# 披露日期中的非数字字符 (如 YYYY-MM-DD 中的连字符)
_NON_DIGIT_RE = re.compile(r'\D+')


class BSEIPOCrawler:
    """北交所 IPO 披露文件爬虫.

    流程: 东方财富拉取全量项目 → 行业筛选 → 北交所查项目详情 →
    拉取文件清单 → 阶段时效性筛选 → 输出文件清单 JSON.
    """

    def __init__(
        self,
        request_interval: float = 0.5,
        eastmoney_client: EastmoneyClient | None = None,
        bse_client: BSEClient | None = None,
    ) -> None:
        """初始化爬虫.

        Args:
            request_interval: 相邻查询请求间隔 (秒).
            eastmoney_client: 可复用的东方财富客户端, 为 None 时自动创建.
            bse_client: 可复用的北交所客户端, 为 None 时自动创建.
        """
        self._request_interval = request_interval
        self._eastmoney_client = eastmoney_client
        self._bse_client = bse_client

    def collect(
        self,
        csrc_industry: str = '汽车制造业',
        extra_stock_codes: tuple[str, ...] = (),
    ) -> list[dict[str, Any]]:
        """采集并筛选有效文件, 返回文件清单列表.

        仅负责网络采集与有效文件筛选, 不涉及文件落盘; 需要持久化
        时把返回值交给 save.

        Args:
            csrc_industry: 证监会行业名称, 用于筛选目标行业项目.
            extra_stock_codes: 需额外补充的股票代码, 不受行业筛选限制.

        Returns:
            有效文件清单, 每条为与上交所格式兼容的字典.
        """
        em_client = self._eastmoney_client
        bse_client = self._bse_client
        owns_em = em_client is None
        owns_bse = bse_client is None
        if em_client is None:
            em_client = EastmoneyClient()
        if bse_client is None:
            bse_client = BSEClient()

        try:
            projects = self._fetch_projects(
                em_client, bse_client, csrc_industry, extra_stock_codes,
            )
            pairs = self._fetch_files(bse_client, projects)
            valid_pairs = self._select_valid_files(pairs)
            files = [self._build_record(proj, f) for proj, f in valid_pairs]
            logger.info(
                '有效文件筛选完成 | 有效 {} / 原始 {} 个',
                len(valid_pairs), len(pairs),
            )
            return files
        finally:
            if owns_em:
                em_client.close()
            if owns_bse:
                bse_client.close()

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
        output_path = output_dir / 'bse_valid_files.json'
        output_path.write_text(
            json.dumps(files, ensure_ascii=False, indent=2), encoding='utf-8',
        )
        logger.info(
            '北交所有效文件清单已生成 | {} 个 | 路径 {}',
            len(files), output_path,
        )
        return output_path

    # ==================================================
    # 采集
    # ==================================================
    def _fetch_projects(
        self,
        em_client: EastmoneyClient,
        bse_client: BSEClient,
        csrc_industry: str,
        extra_stock_codes: tuple[str, ...],
    ) -> list[BSEProjectItem]:
        """通过东方财富拉取全量项目, 按行业筛选后逐一查询北交所详情.

        Args:
            em_client: 东方财富客户端实例.
            bse_client: 北交所客户端实例.
            csrc_industry: 证监会行业名称.
            extra_stock_codes: 需额外补充的股票代码.

        Returns:
            北交所项目条目列表.
        """
        all_items = em_client.query_all_bse_ipo_projects()
        logger.info('东方财富全量项目 | 共 {} 个', len(all_items))

        # 按行业筛选, 加上额外补充项
        matched_codes: set[str] = set()
        for item in all_items:
            if item.csrc_industry == csrc_industry:
                matched_codes.add(item.security_code)
        for code in extra_stock_codes:
            matched_codes.add(code)

        logger.info(
            '行业筛选完成 | 行业={} | 匹配 {} 个 | 补充 {} 个 | 合计 {} 个',
            csrc_industry,
            sum(1 for item in all_items if item.csrc_industry == csrc_industry),
            len(extra_stock_codes),
            len(matched_codes),
        )

        # 逐一查询北交所项目详情
        projects: list[BSEProjectItem] = []
        for idx, stock_code in enumerate(sorted(matched_codes), start=1):
            try:
                project = bse_client.query_project(stock_code)
            except Exception as exc:  # 单项目失败不中断
                logger.warning(
                    '[{}/{}] {} 项目查询失败: {}',
                    idx, len(matched_codes), stock_code, exc,
                )
                time.sleep(self._request_interval)
                continue

            if project is not None:
                projects.append(project)
                logger.info(
                    '[{}/{}] {} {} → 项目 ID={}',
                    idx, len(matched_codes),
                    stock_code, project.company_name, project.id,
                )
            else:
                logger.warning(
                    '[{}/{}] {} 北交所未找到项目',
                    idx, len(matched_codes), stock_code,
                )

            time.sleep(self._request_interval)

        logger.info('北交所项目采集完成 | 有效 {} 个', len(projects))
        return projects

    def _fetch_files(
        self,
        bse_client: BSEClient,
        projects: list[BSEProjectItem],
    ) -> list[tuple[BSEProjectItem, BSEFileItem]]:
        """拉取全部项目的披露文件.

        Args:
            bse_client: 北交所客户端实例.
            projects: 项目列表.

        Returns:
            (项目, 文件) 元组列表.
        """
        pairs: list[tuple[BSEProjectItem, BSEFileItem]] = []

        for idx, project in enumerate(projects, start=1):
            try:
                file_items = bse_client.query_project_files(project.id)
            except Exception as exc:  # 单项目失败不中断
                logger.warning(
                    '[{}/{}] {} 文件查询失败: {}',
                    idx, len(projects), project.company_name, exc,
                )
                time.sleep(self._request_interval)
                continue

            for file_item in file_items:
                pairs.append((project, file_item))

            logger.info(
                '[{}/{}] {} → {} 个文件',
                idx, len(projects), project.company_name,
                len(file_items),
            )
            time.sleep(self._request_interval)

        return pairs

    # ==================================================
    # 有效文件筛选
    # ==================================================
    @staticmethod
    def _select_valid_files(
        pairs: list[tuple[BSEProjectItem, BSEFileItem]],
    ) -> list[tuple[BSEProjectItem, BSEFileItem]]:
        """按文件名去重, 每个项目每个逻辑文件名仅保留最新版本.

        将文件标题末尾的阶段标记 (如"（注册稿）""（报会稿）") 去除后
        作为逻辑文件名, 按 (project.id, base_name) 分组, 每组内按
        up_date 降序取第一条.

        Args:
            pairs: (项目, 文件) 元组列表.

        Returns:
            筛选后的 (项目, 文件) 元组列表.
        """
        groups: dict[
            tuple[int, str], list[tuple[BSEProjectItem, BSEFileItem]]
        ] = {}

        for project, file_item in pairs:
            title = file_item.disclosure_title or ''
            base_name = _STAGE_SUFFIX_RE.sub('', title).strip()
            key = (project.id, base_name)
            groups.setdefault(key, []).append((project, file_item))

        valid: list[tuple[BSEProjectItem, BSEFileItem]] = []
        for group_items in groups.values():
            winner = max(
                group_items, key=lambda p: p[1].up_date or '',
            )
            valid.append(winner)

        return valid

    # ==================================================
    # 输出
    # ==================================================
    @staticmethod
    def _build_record(
        project: BSEProjectItem,
        file_item: BSEFileItem,
    ) -> dict[str, Any]:
        """将 (项目, 文件) 对转换为兼容上交所格式的清单记录.

        Args:
            project: 北交所项目条目.
            file_item: 北交所披露文件条目.

        Returns:
            与上交所格式兼容的字典; fileTypeMap 取披露类型编码
            disclosure_type, fileTitle 取披露标题, fileUpdTime
            规范化为 YYYYMMDD 与上交所格式对齐.
        """
        return {
            'auditId': str(project.id),
            'companyAbbr': project.stock_name,
            'companyName': project.company_name,
            'fileName': file_item.disclosure_title,
            'fileId': Path(file_item.dest_file_path).stem,
            'filePath': BSEClient.build_file_url(file_item.dest_file_path),
            'fileUpdTime': _NON_DIGIT_RE.sub(
                '', file_item.up_date or '',
            )[:8],
            'fileTypeMap': file_item.disclosure_type or '',
            'fileTitle': file_item.disclosure_title or '',
        }
