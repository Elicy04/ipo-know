"""临时脚本: 估算 C36 披露文件的总数据量与总页数 (整合版).

整合原 estimate_c36_file_size.py 与 sample_estimate_c36_pages.py:
    1. 调用 SSEClient 拉取汽车制造业(C36)全部项目的披露文件清单,
       按 fileId 去重, 按文件类型统计文件数量与 fileSize 之和;
    2. 按 fileTypeMap 分层抽样 (每组等比例抽取, 至少 1 个,
       固定随机种子可复现), 流式下载样本 PDF 用 pypdf 读取页数,
       读完立即删除;
    3. 每组计算 页数/MB 比值, 乘以该组全量 MB 外推组内总页数;
    4. 生成合并报告 c36_estimate_report.md, 同时呈现各文件类型的
       大小统计与页数估算, 末尾为 All 总和行.

依赖 pypdf, 但不写入 pyproject.toml, 用 uv 临时引入;
部分历史项目 PDF 为 AES 加密, 需同时引入 cryptography:
    uv run --with pypdf --with cryptography `
        python estimate_c36_size_and_pages.py
"""

import random
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any


# 保证未安装项目包时也能直接运行
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import httpx
import pypdf

from ipo_know.clients.sse.client import SSEClient
from ipo_know.clients.sse.models import FileItem
from ipo_know.clients.sse.models import IPOProjectItem
from ipo_know.config.config import settings


# ==================== 常量配置 ====================
CSRC_CODE = 'C36'  # 证监会行业代码: 汽车制造业
REQUEST_INTERVAL = 0.3  # 相邻查询请求间隔(秒)

# 【重要】吉利汽车(703)、敏实集团(1008) 在接口记录中 csrcCode 为
# None, 用 C36 行业过滤查不到, 需按审核编号点名补充
EXTRA_AUDIT_NUMS = ('703', '1008')

SAMPLE_RATIO = 0.2  # 分层抽样比例
RANDOM_SEED = 42  # 随机种子, 保证抽样可复现
MAX_DOWNLOAD_RETRIES = 3  # 单文件下载最大重试次数

MB = 1024 * 1024
GB = 1024 * MB

# 报告输出路径: 项目根目录
REPORT_FILE = Path(__file__).parent / 'c36_estimate_report.md'


def fetch_all_projects(client: SSEClient) -> list[IPOProjectItem]:
    """全状态拉取汽车制造业的全部 IPO 项目.

    【重要】不传 currStatus 时接口只返回在审项目, 必须用
    query_projects_all_status 按状态分桶查询合并, 否则漏掉
    注册生效/终止等历史项目; 再按审核编号补充行业字段缺失
    的点名项目.

    Args:
        client: 上交所客户端实例.

    Returns:
        全状态去重后的项目条目列表.
    """
    projects = client.query_projects_all_status(csrc_code=CSRC_CODE)
    print(f'全状态项目查询 | 唯一项目 {len(projects)} 个')

    seen_audit_nums = {p.stockAuditNum for p in projects}
    for audit_num in EXTRA_AUDIT_NUMS:
        if audit_num in seen_audit_nums:
            continue
        resp = client.query_projects(stock_audit_num=audit_num)
        for project in resp.pageHelp.data:
            seen_audit_nums.add(project.stockAuditNum)
            projects.append(project)
            print(f'点名补充项目: {project.stockAuditName}')
        time.sleep(REQUEST_INTERVAL)
    return projects


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


def fetch_all_files(
    client: SSEClient,
    projects: list[IPOProjectItem],
) -> tuple[list[FileItem], list[str]]:
    """拉取全部项目的披露文件并按 fileId 去重.

    项目列表中可能存在同一审核 ID 的重复条目, 同一审核 ID 只
    查询一次文件列表.

    Args:
        client: 上交所客户端实例.
        projects: 项目列表.

    Returns:
        二元组: (去重后的全部文件列表, 查询失败的项目审核编号列表).
    """
    files: list[FileItem] = []
    seen_file_ids: set[str] = set()
    queried_audit_ids: set[str] = set()
    failed_projects: list[str] = []

    for idx, project in enumerate(projects, start=1):
        audit_id = resolve_audit_id(project)
        if audit_id in queried_audit_ids:
            print(
                f'[{idx}/{len(projects)}] '
                f'{project.stockAuditName} (重复审核ID, 跳过)'
            )
            continue
        queried_audit_ids.add(audit_id)

        try:
            resp = client.query_files(audit_id=audit_id)
        except Exception as exc:  # 临时脚本, 单项目失败不中断
            print(
                f'[{idx}/{len(projects)}] '
                f'{project.stockAuditName} 文件查询失败: {exc}'
            )
            failed_projects.append(project.stockAuditNum)
            continue

        page_files = resp.pageHelp.data
        for file_item in page_files:
            if file_item.fileId in seen_file_ids:
                continue
            seen_file_ids.add(file_item.fileId)
            files.append(file_item)

        print(
            f'[{idx}/{len(projects)}] '
            f'{project.stockAuditName} → {len(page_files)} 个文件'
        )
        time.sleep(REQUEST_INTERVAL)

    return files, failed_projects


def build_group_stats(files: list[FileItem]) -> dict[str, dict[str, Any]]:
    """按 fileTypeMap 汇总全量口径的文件数量与大小.

    Args:
        files: 去重后的全部文件列表.

    Returns:
        分组统计字典, key=fileTypeMap, value 含 file_type/
        total_count/total_mb/sample_count/sampled_mb/sampled_pages/
        pages_per_mb/est_pages.
    """
    group_stats: dict[str, dict[str, Any]] = {}
    for file_item in files:
        s = group_stats.setdefault(
            file_item.fileTypeMap,
            {'file_type': file_item.fileType, 'total_count': 0,
             'total_mb': 0.0, 'sample_count': 0, 'sampled_mb': 0.0,
             'sampled_pages': 0, 'pages_per_mb': 0.0, 'est_pages': 0.0},
        )
        s['total_count'] += 1
        s['total_mb'] += file_item.fileSize / MB
    return group_stats


def stratified_sample(files: list[FileItem]) -> list[FileItem]:
    """按 fileTypeMap 分层等比例抽样.

    每组抽取 max(1, round(组内数量 * SAMPLE_RATIO)) 个文件,
    使用固定随机种子保证可复现.

    Args:
        files: 去重后的全部文件列表.

    Returns:
        抽中的样本文件列表.
    """
    rng = random.Random(RANDOM_SEED)
    groups: dict[str, list[FileItem]] = {}
    for file_item in files:
        groups.setdefault(file_item.fileTypeMap, []).append(file_item)

    samples: list[FileItem] = []
    for type_map in sorted(groups):
        group = groups[type_map]
        sample_size = max(1, round(len(group) * SAMPLE_RATIO))
        samples.extend(rng.sample(group, sample_size))
        print(
            f'分层抽样 | fileTypeMap={type_map} | '
            f'抽取 {sample_size}/{len(group)} 个'
        )
    return samples


def build_download_url(file_path: str) -> str:
    """拼接披露文件的完整下载 URL.

    实测 IPO 审核披露文件在静态资源路径前需加 /stock 前缀,
    例: https://static.sse.com.cn/stock/disclosure/announcement/...

    Args:
        file_path: 接口返回的文件相对路径.

    Returns:
        完整下载 URL.
    """
    base = settings.sse.static_base_url.rstrip('/')
    path = file_path if file_path.startswith('/') else f'/{file_path}'
    return f'{base}/stock{path}'


def download_and_count(file_item: FileItem, dest_dir: Path) -> int:
    """下载单个样本 PDF 并读取页数, 读完立即删除.

    Args:
        file_item: 样本文件条目.
        dest_dir: 临时下载目录.

    Returns:
        PDF 页数.

    Raises:
        Exception: 重试耗尽后仍失败时抛出最后一次的异常.
    """
    url = build_download_url(file_item.filePath)
    local_path = dest_dir / f'{file_item.fileId}.pdf'
    last_exc: Exception | None = None

    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            with (
                httpx.Client(
                    follow_redirects=True,
                    timeout=httpx.Timeout(120.0),
                ) as cli,
                cli.stream('GET', url) as resp,
            ):
                resp.raise_for_status()
                with open(local_path, 'wb') as f:
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        f.write(chunk)
            reader = pypdf.PdfReader(local_path, strict=False)
            return len(reader.pages)
        except Exception as exc:  # 重试需捕获全部异常
            last_exc = exc
            print(f'  第 {attempt} 次尝试失败: {exc}')
            if attempt < MAX_DOWNLOAD_RETRIES:
                time.sleep(2 * attempt)
        finally:
            local_path.unlink(missing_ok=True)

    raise RuntimeError(f'下载/解析失败: {url}') from last_exc


def extrapolate_pages(group_stats: dict[str, dict[str, Any]]) -> float:
    """根据样本页数/MB 比值外推各组及全量总页数.

    样本全失败的组回退使用整体样本比值.

    Args:
        group_stats: build_group_stats 的返回值, 原地写回
            pages_per_mb 与 est_pages 字段.

    Returns:
        全量总页数估计值.
    """
    sampled_pages_all = sum(
        s['sampled_pages'] for s in group_stats.values()
    )
    sampled_mb_all = sum(s['sampled_mb'] for s in group_stats.values())
    overall_ratio = (
        sampled_pages_all / sampled_mb_all if sampled_mb_all else 0.0
    )

    total_est_pages = 0.0
    for s in group_stats.values():
        if s['sampled_pages'] > 0 and s['sampled_mb'] > 0:
            s['pages_per_mb'] = s['sampled_pages'] / s['sampled_mb']
        else:
            s['pages_per_mb'] = overall_ratio
        s['est_pages'] = s['pages_per_mb'] * s['total_mb']
        total_est_pages += s['est_pages']
    return total_est_pages


def save_report(
    total_projects: int,
    files: list[FileItem],
    samples: list[FileItem],
    group_stats: dict[str, dict[str, Any]],
    total_est_pages: float,
    failed_projects: list[str],
    failed_samples: list[str],
) -> Path:
    """将大小统计与页数估算的合并结果写入报告文件.

    Args:
        total_projects: 查询的项目总数.
        files: 全量去重文件列表.
        samples: 抽中的样本列表.
        group_stats: build_group_stats + extrapolate_pages 后的
            分组统计字典.
        total_est_pages: 外推的全量总页数估计.
        failed_projects: 文件查询失败的项目审核编号列表.
        failed_samples: 下载或解析失败的样本文件名列表.

    Returns:
        生成的报告文件路径.
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total_bytes = sum(f.fileSize for f in files)
    total_mb = total_bytes / MB
    sample_mb = sum(f.fileSize for f in samples) / MB
    sampled_pages_sum = sum(
        s['sampled_pages'] for s in group_stats.values()
    )
    overall_ratio = (
        sampled_pages_sum / sample_mb if sample_mb else 0.0
    )

    lines: list[str] = [
        '# C36 IPO 披露文件数据量与页数估算报告',
        '',
        f'- 生成时间: {now}',
        '- 数据来源: 上交所 IPO 披露平台 (query.sse.com.cn)',
        '- 行业: 汽车制造业 (证监会行业代码 C36)',
        f'- 统计口径: {total_projects} 个项目 | '
        f'{len(files)} 个去重文件 (按 fileId 去重)',
        f'- 全量大小: {total_mb:.2f} MB (约 {total_bytes / GB:.2f} GB)',
        '- 页数估算方法: 按 fileTypeMap 分层抽样下载 PDF, 实测样本'
        '页数/MB 比值, 按组外推至全量',
        f'- 抽样参数: 比例 {SAMPLE_RATIO:.0%} | 随机种子 {RANDOM_SEED} '
        f'| 样本 {len(samples)} 个文件 / {sample_mb:.2f} MB',
        f'- 总页数估计: 约 {round(total_est_pages)} 页',
        '',
        '## 按文件类型统计',
        '',
        '| fileType | fileTypeMap | 文件数 | 总大小 | 样本数 | 样本页数 '
        '| 页数/MB | 估算页数 |',
        '|---|---|---:|---:|---:|---:|---:|---:|',
    ]
    sorted_groups = sorted(
        group_stats.items(),
        key=lambda kv: kv[1]['total_mb'],
        reverse=True,
    )
    for type_map, s in sorted_groups:
        lines.append(
            f'| {s["file_type"]} | {type_map} | {s["total_count"]} | '
            f'{s["total_mb"]:.2f} MB | {s["sample_count"]:.0f} | '
            f'{s["sampled_pages"]:.0f} | {s["pages_per_mb"]:.2f} | '
            f'{s["est_pages"]:.0f} |'
        )
    lines.append(
        f'| All | All | {len(files)} | {total_mb:.2f} MB | '
        f'{len(samples)} | {sampled_pages_sum:.0f} | '
        f'{overall_ratio:.2f} | {round(total_est_pages)} |'
    )

    if failed_projects:
        lines.append('')
        lines.append(f'## 查询失败的项目 ({len(failed_projects)} 个)')
        lines.append('')
        for audit_num in failed_projects:
            lines.append(f'- {audit_num}')

    if failed_samples:
        lines.append('')
        lines.append(f'## 下载/解析失败的样本 ({len(failed_samples)} 个)')
        lines.append('')
        for name in failed_samples:
            lines.append(f'- {name}')

    lines.append('')
    lines.append(
        '> 注: 页数基于样本实测外推, 存在抽样误差; 页数/MB 比值按组内'
        '样本页数之和除以样本 MB 之和计算.'
    )

    REPORT_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return REPORT_FILE


def main() -> None:
    """统计文件大小, 抽样估算页数, 生成合并报告."""
    with SSEClient() as client:
        projects = fetch_all_projects(client)
        print(f'\n共 {len(projects)} 个项目, 开始采集文件清单...\n')
        files, failed_projects = fetch_all_files(client, projects)

    total_bytes = sum(f.fileSize for f in files)
    print(
        f'\n全量文件: {len(files)} 个 | {total_bytes / MB:.2f} MB, '
        '开始分层抽样...\n'
    )
    group_stats = build_group_stats(files)
    samples = stratified_sample(files)

    failed_samples: list[str] = []
    print()
    with tempfile.TemporaryDirectory(prefix='ipo_know_sample_') as tmp:
        dest_dir = Path(tmp)
        for idx, sample in enumerate(samples, start=1):
            label = f'{sample.companyAbbr} | {sample.fileTitle}'
            print(f'[{idx}/{len(samples)}] {label}')
            try:
                pages = download_and_count(sample, dest_dir)
            except Exception as exc:  # 单样本失败不中断
                print(f'  样本失败, 已跳过: {exc}')
                failed_samples.append(sample.fileName)
                continue
            s = group_stats[sample.fileTypeMap]
            s['sample_count'] += 1
            s['sampled_mb'] += sample.fileSize / MB
            s['sampled_pages'] += pages
            print(f'  → {pages} 页 | {sample.fileSize / MB:.2f} MB')

    total_est_pages = extrapolate_pages(group_stats)

    print('\n' + '=' * 62)
    print('按文件类型统计 (大小实测 + 页数估算)')
    print('=' * 62)
    sorted_groups = sorted(
        group_stats.items(),
        key=lambda kv: kv[1]['total_mb'],
        reverse=True,
    )
    for type_map, s in sorted_groups:
        print(
            f'fileType={s["file_type"]} | fileTypeMap={type_map} | '
            f'文件数={s["total_count"]} | 大小={s["total_mb"]:.2f} MB | '
            f'估算页数={round(s["est_pages"])}'
        )
    print(
        f'fileType=All | fileTypeMap=All | 文件数={len(files)} | '
        f'大小={total_bytes / MB:.2f} MB | '
        f'估算页数={round(total_est_pages)}'
    )
    print('-' * 62)
    print(
        f'合计: 去重文件 {len(files)} 个 | '
        f'总大小 {total_bytes / MB:.2f} MB '
        f'(约 {total_bytes / GB:.2f} GB) | '
        f'总页数估计 约 {round(total_est_pages)} 页'
    )

    report_path = save_report(
        len(projects), files, samples, group_stats, total_est_pages,
        failed_projects, failed_samples,
    )
    print(f'\n报告已保存至: {report_path}')


if __name__ == '__main__':
    main()
