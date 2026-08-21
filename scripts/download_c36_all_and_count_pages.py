"""临时脚本: 全量下载 C36 披露文件并实测页数 (非抽样).

流程:
    1. 调用 SSEClient 拉取汽车制造业(C36)全部项目的披露文件清单,
       按 fileId 去重 (同一审核 ID 的重复项目条目只查询一次);
    2. 全量下载到系统下载文件夹的子目录 ipo_know_c36, 目录结构为
       {项目名}_{审核编号}/{类别}_{文件标题}_{更新日期}.pdf, 项目目录
       带审核编号以区分同一公司的多次申报, 类别目录扁平化进文件名,
       文件名统一附加 fileUpdTime 日期便于按元信息定位;
       类别名取自 c36_file_type_mapping_report.md 的 fileTypeMap
       映射表, 表外代码回退为 其他_{fileTypeMap};
       已存在且大小与接口 fileSize 一致的文件自动跳过;
    3. 逐个用 pypdf 实测页数;
    4. 生成精确页数报告 c36_full_download_report.md.

依赖 pypdf, 但不写入 pyproject.toml, 用 uv 临时引入;
部分历史项目 PDF 为 AES 加密, 需同时引入 cryptography:
    uv run --with pypdf --with cryptography `
        python download_c36_all_and_count_pages.py
"""

import ctypes
import re
import sys
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
MAX_DOWNLOAD_RETRIES = 3  # 单文件下载最大重试次数
SIZE_TOLERANCE = 1024  # 本地文件大小与接口值的容差(字节)

MB = 1024 * 1024
GB = 1024 * MB

# 下载根目录: 系统下载文件夹/ipo_know_c36
DOWNLOAD_ROOT = Path.home() / 'Downloads' / 'ipo_know_c36'

# 报告输出路径: 项目根目录
REPORT_FILE = Path(__file__).parent / 'c36_full_download_report.md'

# fileTypeMap → 披露文件类别名
# 来源: c36_file_type_mapping_report.md 映射表 (I + 三位类别码 + 阶段码)
CATEGORY_NAMES: dict[str, str] = {
    'I0011': '招股说明书(申报稿)',
    'I0012': '招股说明书(上会稿)',
    'I0013': '招股说明书(注册稿)',
    'I0021': '财务报告及审计报告(申报稿)',
    'I0022': '财务报告及审计报告(上会稿)',
    'I0023': '财务报告及审计报告(注册稿)',
    'I0031': '法律意见书(申报稿)',
    'I0032': '法律意见书(上会稿)',
    'I0033': '法律意见书(注册稿)',
    'I0051': '发行保荐书(申报稿)',
    'I0052': '发行保荐书(上会稿)',
    'I0053': '发行保荐书(注册稿)',
    'I0061': '上市保荐书(申报稿)',
    'I0062': '上市保荐书(上会稿)',
    'I0063': '上市保荐书(注册稿)',
    'I1010': '注册批复',
    'I1020': '终止审核决定',
    'I2010': '上市委审议会议公告',
    'I2020': '上市委审议会议结果公告',
}


def get_windows_downloads_dir() -> Path:
    """获取 Windows 系统下载文件夹的真实路径.

    通过 shell32 的 SHGetKnownFolderPath 查询, 避免 OneDrive
    重定向等场景下 Path.home()/Downloads 与实际不一致.

    Returns:
        下载文件夹路径; 查询失败时回退用户目录下的 Downloads.
    """
    try:
        # FOLDERID_Downloads = {374DE290-123F-4565-9164-39C4925E467B}
        class GUID(ctypes.Structure):
            _fields_ = [
                ('Data1', ctypes.c_ulong),
                ('Data2', ctypes.c_ushort),
                ('Data3', ctypes.c_ushort),
                ('Data4', ctypes.c_ubyte * 8),
            ]

        folder_id = GUID(
            0x374DE290, 0x123F, 0x4565,
            (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4,
                                 0x92, 0x5E, 0x46, 0x7B),
        )
        buf = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        ret = shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id), 0, None, ctypes.byref(buf)
        )
        if ret == 0 and buf.value:
            path = Path(buf.value)
            ctypes.windll.ole32.CoTaskMemFree(buf)  # type: ignore[attr-defined]
            return path
    except Exception:  # 回退默认路径
        pass
    return Path.home() / 'Downloads'


def category_name(type_map: str) -> str:
    """FileTypeMap 对应的披露文件类别目录名.

    Args:
        type_map: 文件的 fileTypeMap 代码.

    Returns:
        类别目录名; 映射表外的代码回退为 其他_{type_map}.
    """
    return CATEGORY_NAMES.get(type_map, f'其他_{type_map}')


def sanitize_name(name: str) -> str:
    """清洗 Windows 非法字符, 用于目录/文件名.

    Args:
        name: 原始名称.

    Returns:
        清洗后的名称; 清洗后为空时回退为 unknown.
    """
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', name).strip(' .')
    return cleaned or 'unknown'


def project_dir_name(project: IPOProjectItem) -> str:
    """项目目录名: {项目名}_{审核编号}.

    同一公司多次申报(如地通工业两次 IPO)项目名相同, 必须带
    审核编号才能区分.

    Args:
        project: 单个 IPO 项目条目.

    Returns:
        清洗后的项目目录名.
    """
    return sanitize_name(
        f'{project.stockAuditName}_{project.stockAuditNum}'
    )


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
) -> tuple[list[tuple[IPOProjectItem, FileItem]], list[str]]:
    """拉取全部项目的披露文件并按 fileId 去重, 保留所属项目.

    项目列表中可能存在同一审核 ID 的重复条目, 同一审核 ID 只
    查询一次文件列表.

    Args:
        client: 上交所客户端实例.
        projects: 项目列表.

    Returns:
        二元组: ((项目, 文件) 元组列表, 查询失败的项目审核编号列表).
    """
    pairs: list[tuple[IPOProjectItem, FileItem]] = []
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
            pairs.append((project, file_item))

        print(
            f'[{idx}/{len(projects)}] '
            f'{project.stockAuditName} → {len(page_files)} 个文件'
        )
        time.sleep(REQUEST_INTERVAL)

    return pairs, failed_projects


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


def resolve_local_path(
    project: IPOProjectItem,
    file_item: FileItem,
    used_names: dict[Path, set[str]],
) -> Path:
    """计算文件在本地目录树中的落盘路径.

    结构: {下载根}/{项目名}_{审核编号}/{类别}_{文件标题}_{更新日期}.pdf,
    项目目录带审核编号以区分同一公司的多次申报;
    类别目录扁平化进文件名, 避免一个文件夹只装一个文件;
    接口原始文件名(如 002160_20260709_WVTN.pdf)可读性差,
    改用 fileTitle 命名; 所有文件名统一附加 fileUpdTime 日期,
    便于按元信息直接定位落盘路径并区分更新版本;
    极端重名时再追加序号避免覆盖.

    Args:
        project: 文件所属项目.
        file_item: 文件条目.
        used_names: 各目录已占用文件名集合, 原地更新.

    Returns:
        本地文件完整路径.
    """
    proj_dir = DOWNLOAD_ROOT / project_dir_name(project)
    proj_dir.mkdir(parents=True, exist_ok=True)

    title = file_item.fileTitle.strip() or file_item.fileId
    # 统一附加更新日期, 便于按元信息直接定位落盘路径
    date_suffix = (file_item.fileUpdTime or '')[:8]
    base_name = sanitize_name(
        f'{category_name(file_item.fileTypeMap)}_{title}_{date_suffix}'
        if date_suffix
        else f'{category_name(file_item.fileTypeMap)}_{title}'
    )
    used = used_names.setdefault(proj_dir, set())
    name = f'{base_name}.pdf'
    counter = 1
    while name in used:
        counter += 1
        name = f'{base_name}_{counter}.pdf'
    used.add(name)
    return proj_dir / name


def download_file(file_item: FileItem, local_path: Path) -> bool:
    """下载单个文件, 已存在且大小一致时跳过.

    下载写入临时后缀文件后改名, 避免中断留下半截文件被
    误判为完整.

    Args:
        file_item: 文件条目.
        local_path: 目标落盘路径.

    Returns:
        True 表示跳过(已存在), False 表示本次实际下载.

    Raises:
        Exception: 重试耗尽后仍失败时抛出最后一次的异常.
    """
    if local_path.exists() and abs(
        local_path.stat().st_size - file_item.fileSize
    ) <= SIZE_TOLERANCE:
        return True

    url = build_download_url(file_item.filePath)
    tmp_path = local_path.with_suffix(local_path.suffix + '.part')
    last_exc: Exception | None = None

    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            with (
                httpx.Client(
                    follow_redirects=True,
                    timeout=httpx.Timeout(300.0),
                ) as cli,
                cli.stream('GET', url) as resp,
            ):
                resp.raise_for_status()
                with open(tmp_path, 'wb') as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
            tmp_path.replace(local_path)
            return False
        except Exception as exc:  # 重试需捕获全部异常
            last_exc = exc
            print(f'  第 {attempt} 次下载失败: {exc}')
            tmp_path.unlink(missing_ok=True)
            if attempt < MAX_DOWNLOAD_RETRIES:
                time.sleep(2 * attempt)

    raise RuntimeError(f'下载失败: {url}') from last_exc


def count_pages(local_path: Path) -> int:
    """用 pypdf 读取本地 PDF 的页数.

    Args:
        local_path: 本地 PDF 路径.

    Returns:
        PDF 页数.
    """
    reader = pypdf.PdfReader(local_path, strict=False)
    return len(reader.pages)


def save_report(
    total_projects: int,
    pairs: list[tuple[IPOProjectItem, FileItem]],
    pages_map: dict[str, int],
    skipped: int,
    downloaded: int,
    failed_projects: list[str],
    failed_files: list[tuple[str, str]],
) -> Path:
    """将全量下载与实测页数结果写入报告文件.

    Args:
        total_projects: 查询的项目总数.
        pairs: (项目, 文件) 元组列表.
        pages_map: fileId → 实测页数.
        skipped: 跳过(已存在且大小一致)的文件数.
        downloaded: 本次实际下载的文件数.
        failed_projects: 文件查询失败的项目审核编号列表.
        failed_files: (文件名, 失败原因) 列表.

    Returns:
        生成的报告文件路径.
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total_bytes = sum(f.fileSize for _, f in pairs)
    total_pages = sum(pages_map.values())

    # 按 fileTypeMap 汇总
    group_stats: dict[str, dict[str, Any]] = {}
    for _, file_item in pairs:
        s = group_stats.setdefault(
            file_item.fileTypeMap,
            {'file_type': file_item.fileType, 'count': 0,
             'total_mb': 0.0, 'pages': 0},
        )
        s['count'] += 1
        s['total_mb'] += file_item.fileSize / MB
        s['pages'] += pages_map.get(file_item.fileId, 0)

    # 按项目汇总, 项目名带审核编号以区分同一公司的多次申报
    project_stats: dict[str, dict[str, int]] = {}
    for project, file_item in pairs:
        s = project_stats.setdefault(
            project_dir_name(project),
            {'count': 0, 'pages': 0, 'bytes': 0},
        )
        s['count'] += 1
        s['pages'] += pages_map.get(file_item.fileId, 0)
        s['bytes'] += file_item.fileSize

    lines: list[str] = [
        '# C36 IPO 披露文件全量下载与精确页数报告',
        '',
        f'- 生成时间: {now}',
        '- 数据来源: 上交所 IPO 披露平台 (query.sse.com.cn)',
        '- 行业: 汽车制造业 (证监会行业代码 C36)',
        f'- 统计口径: {total_projects} 个项目 | '
        f'{len(pairs)} 个去重文件 (按 fileId 去重)',
        f'- 下载目录: {DOWNLOAD_ROOT}',
        f'- 全量大小: {total_bytes / MB:.2f} MB '
        f'(约 {total_bytes / GB:.2f} GB)',
        f'- 实测总页数: {total_pages} 页 (pypdf 全量实测, 非估算)',
        f'- 本次下载: {downloaded} 个 | 跳过(已存在): {skipped} 个 '
        f'| 失败: {len(failed_files)} 个',
        '',
        '## 按披露文件类别统计',
        '',
        '| fileType | fileTypeMap | 披露文件类别 | 文件数 | 总大小 '
        '| 实测页数 |',
        '|---|---|---|---:|---:|---:|',
    ]
    sorted_groups = sorted(
        group_stats.items(),
        key=lambda kv: kv[1]['total_mb'],
        reverse=True,
    )
    for type_map, s in sorted_groups:
        lines.append(
            f'| {s["file_type"]} | {type_map} | '
            f'{category_name(type_map)} | {s["count"]} | '
            f'{s["total_mb"]:.2f} MB | {s["pages"]} |'
        )
    lines.append(
        f'| All | All | 全部 | {len(pairs)} | '
        f'{total_bytes / MB:.2f} MB | {total_pages} |'
    )

    lines.append('')
    lines.append('## 按项目统计 (项目目录名含审核编号)')
    lines.append('')
    lines.append('| 项目名_审核编号 | 文件数 | 大小 | 实测页数 |')
    lines.append('|---|---:|---:|---:|')
    sorted_projects = sorted(
        project_stats.items(),
        key=lambda kv: kv[1]['pages'],
        reverse=True,
    )
    for name, s in sorted_projects:
        lines.append(
            f'| {name} | {s["count"]} | {s["bytes"] / MB:.2f} MB '
            f'| {s["pages"]} |'
        )

    if failed_projects:
        lines.append('')
        lines.append(
            f'## 查询失败的项目 ({len(failed_projects)} 个)'
        )
        lines.append('')
        for audit_num in failed_projects:
            lines.append(f'- {audit_num}')

    if failed_files:
        lines.append('')
        lines.append(
            f'## 下载/解析失败的文件 ({len(failed_files)} 个)'
        )
        lines.append('')
        for name, reason in failed_files:
            lines.append(f'- {name}: {reason}')

    lines.append('')
    lines.append(
        '> 注: 页数为 pypdf 全量实测; 已存在且大小一致的文件未重复'
        '下载, 但仍参与页数统计.'
    )

    REPORT_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return REPORT_FILE


def main() -> None:
    """全量下载 C36 披露文件, 实测页数, 生成精确报告."""
    downloads_dir = get_windows_downloads_dir()
    global DOWNLOAD_ROOT  # 临时脚本, 修正重定向路径
    DOWNLOAD_ROOT = downloads_dir / 'ipo_know_c36'
    print(f'下载根目录: {DOWNLOAD_ROOT}')

    with SSEClient() as client:
        projects = fetch_all_projects(client)
        print(f'\n共 {len(projects)} 个项目, 开始采集文件清单...\n')
        pairs, failed_projects = fetch_all_files(client, projects)

    total_bytes = sum(f.fileSize for _, f in pairs)
    print(
        f'\n全量文件: {len(pairs)} 个 | {total_bytes / MB:.2f} MB, '
        '开始全量下载...\n'
    )

    pages_map: dict[str, int] = {}
    failed_files: list[tuple[str, str]] = []
    used_names: dict[Path, set[str]] = {}
    skipped = 0
    downloaded = 0

    for idx, (project, file_item) in enumerate(pairs, start=1):
        label = (
            f'{project.stockAuditName}({project.stockAuditNum}) | '
            f'{category_name(file_item.fileTypeMap)} | '
            f'{file_item.fileName}'
        )
        print(f'[{idx}/{len(pairs)}] {label}')
        local_path = resolve_local_path(project, file_item, used_names)

        try:
            if download_file(file_item, local_path):
                skipped += 1
                print('  → 已存在且大小一致, 跳过下载')
            else:
                downloaded += 1
                print(f'  → 下载完成 {file_item.fileSize / MB:.2f} MB')
            pages = count_pages(local_path)
        except Exception as exc:  # 单文件失败不中断
            print(f'  失败, 已跳过: {exc}')
            failed_files.append((label, str(exc)))
            continue

        pages_map[file_item.fileId] = pages
        print(f'  → {pages} 页')

    print('\n' + '=' * 62)
    print(f'下载完成: 本次 {downloaded} 个 | 跳过 {skipped} 个 | '
          f'失败 {len(failed_files)} 个')
    print(f'实测总页数: {sum(pages_map.values())} 页')
    print('=' * 62)

    report_path = save_report(
        len(projects), pairs, pages_map, skipped, downloaded,
        failed_projects, failed_files,
    )
    print(f'\n报告已保存至: {report_path}')


if __name__ == '__main__':
    main()
