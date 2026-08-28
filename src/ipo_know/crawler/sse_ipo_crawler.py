"""上交所 IPO 披露文件爬虫模块.

依赖 clients.sse 提供的网络接口 (SSEClient) 与数据模型
(IPOProjectItem / FileItem), 针对指定行业与上市板块, 按全审核状态
拉取项目及其披露文件清单, 再依据披露阶段 (申报稿/上会稿/注册稿)
筛选出各项目当前有效的文件, 最终输出文件清单 JSON.
"""

import json
import re
import time
from pathlib import Path
from typing import Any

from loguru import logger

from ipo_know.clients.sse.client import SSEClient
from ipo_know.clients.sse.models import FileItem
from ipo_know.clients.sse.models import IPOProjectItem
from ipo_know.config.config import settings


# 阶段型文件编码: 匹配 I00xx 且末位为 1/2/3,
# 例: I0011(招股说明书申报稿)、I0013(招股说明书注册稿).
_STAGED_FILE_TYPE_RE = re.compile(r'^I00\d[123]$')

# C36 行业字段缺失的点名补充项目: 吉利汽车(703)、敏实集团(1008)
# 在接口记录中 csrcCode 为 None, 按 C36 过滤查不到, 需按审核编号补查.
EXTRA_AUDIT_NUMS: tuple[str, ...] = ('703', '1008')

# 日期字符串中的非数字字符 (如连字符)
_NON_DIGIT_RE = re.compile(r'\D+')


def _project_year(raw: str | None) -> str:
    """从日期串归一化出 4 位申报年份.

    去非数字字符后取前 4 位, 兼容 YYYYMMDDHHMMSS 等格式;
    数字不足 4 位视为缺失.

    Args:
        raw: 原始日期字符串, 可为 None.

    Returns:
        4 位数字年份字符串; 无法解析时为空串.
    """
    digits = _NON_DIGIT_RE.sub('', raw or '')
    return digits[:4] if len(digits) >= 4 else ''


def file_base_group(file_type_map: str) -> str:
    """返回文件类型的类别基组.

    阶段型文件 (I00xx) 去掉末位阶段码, 例: I0011 → I001;
    非阶段型文件保持原编码不变.

    Args:
        file_type_map: 文件类型映射编码.

    Returns:
        类别基组编码.
    """
    if _STAGED_FILE_TYPE_RE.match(file_type_map):
        return file_type_map[:4]
    return file_type_map


def file_stage(file_type_map: str) -> int:
    """返回文件的披露阶段码.

    阶段型文件返回末位数字 (1=申报稿 2=上会稿 3=注册稿),
    非阶段型文件返回 0.

    Args:
        file_type_map: 文件类型映射编码.

    Returns:
        阶段码.
    """
    if _STAGED_FILE_TYPE_RE.match(file_type_map):
        return int(file_type_map[-1])
    return 0


def build_download_url(file_path: str) -> str:
    """拼接披露文件的完整下载 URL.

    实测 IPO 审核披露文件在静态资源路径前需加 /stock 前缀,
    否则 CDN 返回 302 至 /404.

    Args:
        file_path: 接口返回的文件相对路径.

    Returns:
        完整下载 URL.
    """
    base = settings.sse.static_base_url.rstrip('/')
    path = file_path if file_path.startswith('/') else f'/{file_path}'
    return f'{base}/stock{path}'


def resolve_audit_id(project: IPOProjectItem) -> str:
    """提取文件查询所需的审核 ID.

    优先取嵌套子记录中的 auditId, 兜底用审核编号 stockAuditNum.

    Args:
        project: 单个 IPO 项目条目.

    Returns:
        文件列表查询用的审核 ID.
    """
    if project.intermediary:
        return project.intermediary[0].auditId
    if project.stockIssuer:
        return project.stockIssuer[0].auditId
    return project.stockAuditNum


class SSEIPOCrawler:
    """上交所 IPO 披露文件爬虫.

    流程: 拉取项目 → 拉取文件清单 → 按披露阶段筛选有效文件 →
    拼接下载 URL → 输出文件清单 JSON.

    Attributes:
        request_interval: 相邻查询请求间隔 (秒), 控制目标站点压力.
    """

    def __init__(
        self,
        request_interval: float = 0.3,
        client: SSEClient | None = None,
    ) -> None:
        """初始化爬虫.

        Args:
            request_interval: 相邻查询请求间隔 (秒).
            client: 可复用的上交所客户端, 为 None 时由 crawl 自动创建.
        """
        self._request_interval = request_interval
        self._client = client

    def collect(
        self,
        csrc_code: str = 'C36',
        issue_market_type: str = '1,2',
        extra_audit_nums: tuple[str, ...] = EXTRA_AUDIT_NUMS,
    ) -> list[dict[str, Any]]:
        """采集并筛选有效文件, 返回文件清单列表.

        仅负责网络采集与有效文件筛选, 不涉及文件落盘; 需要持久化
        时把返回值交给 save.

        Args:
            csrc_code: 证监会行业代码.
            issue_market_type: 上市板块, 1=科创板 2=主板, 逗号分隔.
            extra_audit_nums: 行业字段缺失需按审核编号补查的项目.

        Returns:
            有效文件清单, 每条为 FileItem 转字典且 filePath 已拼接
            为完整下载 URL.
        """
        client = self._client
        owns_client = client is None
        if client is None:
            client = SSEClient()

        try:
            projects = self._fetch_projects(
                client, csrc_code, issue_market_type, extra_audit_nums,
            )
            pairs = self._fetch_files(client, projects)
            valid_pairs = self._select_valid_files(pairs)
            files = [
                self._build_record(project, file_item)
                for project, file_item in valid_pairs
            ]
            logger.info(
                '有效文件筛选完成 | 有效 {} / 原始 {} 个',
                len(valid_pairs), len(pairs),
            )
            return files
        finally:
            if owns_client:
                client.close()

    def save(
        self,
        files: list[dict[str, Any]],
        csrc_code: str,
        output_dir: str | Path,
    ) -> Path:
        """将文件清单列表写入 JSON 文件.

        Args:
            files: 由 collect 返回的有效文件清单.
            csrc_code: 证监会行业代码, 用于派生清单文件名.
            output_dir: 输出目录, JSON 清单将写入其中.

        Returns:
            生成的文件清单 JSON 路径.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f'{csrc_code.lower()}_valid_files.json'
        output_path = output_dir / filename
        output_path.write_text(
            json.dumps(files, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        logger.info(
            '有效文件清单已生成 | {} 个 | 路径 {}', len(files), output_path,
        )
        return output_path

    # ==================================================
    # 采集
    # ==================================================
    def _fetch_projects(
        self,
        client: SSEClient,
        csrc_code: str,
        issue_market_type: str,
        extra_audit_nums: tuple[str, ...],
    ) -> list[IPOProjectItem]:
        """全状态拉取指定行业的 IPO 项目.

        不传 currStatus 时接口只返回在审项目, 必须用
        query_projects_all_status 按状态分桶查询合并; 再按审核编号
        补充行业字段缺失的点名项目.

        Args:
            client: 上交所客户端实例.
            csrc_code: 证监会行业代码.
            issue_market_type: 上市板块.
            extra_audit_nums: 需按审核编号补查的项目.

        Returns:
            全状态去重后的项目条目列表.
        """
        projects = client.query_projects_all_status(
            csrc_code=csrc_code,
            issue_market_type=issue_market_type,
        )
        logger.info('全状态项目查询 | 唯一项目 {} 个', len(projects))

        seen_audit_nums = {p.stockAuditNum for p in projects}
        for audit_num in extra_audit_nums:
            if audit_num in seen_audit_nums:
                continue
            resp = client.query_projects(stock_audit_num=audit_num)
            for project in resp.pageHelp.data:
                seen_audit_nums.add(project.stockAuditNum)
                projects.append(project)
                logger.info('点名补充项目: {}', project.stockAuditName)
            time.sleep(self._request_interval)
        return projects

    def _fetch_files(
        self,
        client: SSEClient,
        projects: list[IPOProjectItem],
    ) -> list[tuple[IPOProjectItem, FileItem]]:
        """拉取全部项目的披露文件并按 fileId 去重.

        Args:
            client: 上交所客户端实例.
            projects: 项目列表.

        Returns:
            (项目, 文件) 元组列表.
        """
        pairs: list[tuple[IPOProjectItem, FileItem]] = []
        seen_file_ids: set[str] = set()
        queried_audit_ids: set[str] = set()

        for idx, project in enumerate(projects, start=1):
            audit_id = resolve_audit_id(project)
            if audit_id in queried_audit_ids:
                continue
            queried_audit_ids.add(audit_id)

            try:
                resp = client.query_files(audit_id=audit_id)
            except Exception as exc:  # 单项目失败不中断
                logger.warning(
                    '[{}/{}] {} 文件查询失败: {}',
                    idx, len(projects), project.stockAuditName, exc,
                )
                time.sleep(self._request_interval)
                continue

            for file_item in resp.pageHelp.data:
                if file_item.fileId in seen_file_ids:
                    continue
                seen_file_ids.add(file_item.fileId)
                pairs.append((project, file_item))

            logger.info(
                '[{}/{}] {} → {} 个文件',
                idx, len(projects), project.stockAuditName,
                len(resp.pageHelp.data),
            )
            time.sleep(self._request_interval)

        return pairs

    # ==================================================
    # 有效文件筛选
    # ==================================================
    @staticmethod
    def _select_valid_files(
        pairs: list[tuple[IPOProjectItem, FileItem]],
    ) -> list[tuple[IPOProjectItem, FileItem]]:
        """按披露阶段筛选各项目的有效文件.

        同一项目同一类别基组内, 时效性 注册稿 > 上会稿 > 申报稿,
        只保留最高阶段文件; 非阶段型文件不受影响全部保留.

        Args:
            pairs: (项目, 文件) 元组列表.

        Returns:
            有效文件对应的 (项目, 文件) 元组列表.
        """
        by_audit: dict[
            str, list[tuple[IPOProjectItem, FileItem]]
        ] = {}
        for project, file_item in pairs:
            by_audit.setdefault(
                resolve_audit_id(project), [],
            ).append((project, file_item))

        valid: list[tuple[IPOProjectItem, FileItem]] = []
        for items in by_audit.values():
            groups: dict[
                str, list[tuple[IPOProjectItem, FileItem]]
            ] = {}
            for pair in items:
                base = file_base_group(pair[1].fileTypeMap)
                groups.setdefault(base, []).append(pair)

            for group_items in groups.values():
                max_stage = max(
                    file_stage(p[1].fileTypeMap) for p in group_items
                )
                valid.extend(
                    p for p in group_items
                    if file_stage(p[1].fileTypeMap) == max_stage
                )
        return valid

    # ==================================================
    # 输出
    # ==================================================
    @staticmethod
    def _build_record(
        project: IPOProjectItem,
        file_item: FileItem,
    ) -> dict[str, Any]:
        """将项目与文件条目转换为清单记录, filePath 拼接为完整下载 URL.

        Args:
            project: 单个 IPO 项目条目, 提供申报年份来源.
            file_item: 单个披露文件条目.

        Returns:
            与 FileItem 字段一致的字典, 其中 filePath 为完整 URL,
            projectYear 取审核受理日期前 4 位 (缺失为空串).
        """
        record = file_item.model_dump()
        record['filePath'] = build_download_url(file_item.filePath)
        record['projectYear'] = _project_year(project.auditApplyDate)
        return record
