"""临时脚本: 总结 C36 披露文件 fileType/fileTypeMap 的映射规律.

调用 SSEClient 拉取汽车制造业(C36)全部项目的披露文件, 提取每条
文件的 fileTypeMap、fileType、fileTitle 并分组整合, 再调用
DeepSeek 模型总结编码与文件类别之间的映射规律.

仅用于一次性分析, 不属于项目业务代码.

用法:
    1. 在下方 DEEPSEEK_API_KEY 填入密钥(留空则回退读取 .env 中的
       IPO_KNOW_DEEPSEEK_API_KEY)
    2. uv run python analyze_c36_file_type_mapping.py
"""

import sys
import time
from datetime import datetime
from pathlib import Path


# 保证未安装项目包时也能直接运行
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import httpx

from ipo_know.clients.sse.client import SSEClient
from ipo_know.clients.sse.models import IPOProjectItem
from ipo_know.config.config import settings


# ==================== 常量配置 ====================
# DeepSeek API Key, 留空则回退读取 settings.deepseek_api_key (.env)
DEEPSEEK_API_KEY = ''
DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
DEEPSEEK_MODEL = 'deepseek-v4-flash'

CSRC_CODE = 'C36'  # 证监会行业代码: 汽车制造业
REQUEST_INTERVAL = 0.3  # 相邻请求间隔(秒), 控制目标站点压力

# 【重要】吉利汽车(703)、敏实集团(1008) 在接口记录中 csrcCode 为
# None, 用 C36 行业过滤查不到, 需按审核编号点名补充
EXTRA_AUDIT_NUMS = ('703', '1008')

# 报告输出路径: 项目根目录
REPORT_FILE = Path(__file__).parent / 'c36_file_type_mapping_report.md'


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


def collect_title_groups(
    client: SSEClient,
    projects: list[IPOProjectItem],
) -> dict[tuple[str, int | None], dict[str, int]]:
    """抓取全部项目文件并按编码分组整合标题.

    Args:
        client: 上交所客户端实例.
        projects: 项目列表.

    Returns:
        嵌套字典, 外层 key=(fileTypeMap, fileType),
        内层为 {fileTitle: 出现次数}, 文件按 fileId 去重.
    """
    groups: dict[tuple[str, int | None], dict[str, int]] = {}
    seen_file_ids: set[str] = set()

    for idx, project in enumerate(projects, start=1):
        audit_id = resolve_audit_id(project)
        try:
            resp = client.query_files(audit_id=audit_id)
        except Exception as exc:  # 临时脚本, 单项目失败不中断
            print(
                f'[{idx}/{len(projects)}] '
                f'{project.stockAuditName} 文件查询失败: {exc}'
            )
            continue

        files = resp.pageHelp.data
        for file_item in files:
            if file_item.fileId in seen_file_ids:
                continue
            seen_file_ids.add(file_item.fileId)
            key = (file_item.fileTypeMap, file_item.fileType)
            titles = groups.setdefault(key, {})
            titles[file_item.fileTitle] = (
                titles.get(file_item.fileTitle, 0) + 1
            )

        print(
            f'[{idx}/{len(projects)}] '
            f'{project.stockAuditName} → {len(files)} 个文件'
        )
        time.sleep(REQUEST_INTERVAL)

    return groups


def build_prompt(
    groups: dict[tuple[str, int | None], dict[str, int]],
) -> str:
    """将分组数据组装为发给大模型的分析提示词.

    Args:
        groups: collect_title_groups 的返回值.

    Returns:
        完整提示词文本.
    """
    lines: list[str] = []
    for (type_map, file_type), titles in sorted(
        groups.items(), key=lambda kv: kv[0][0],
    ):
        total = sum(titles.values())
        lines.append(
            f'【fileTypeMap={type_map} | fileType={file_type}】'
            f'共 {total} 个文件'
        )
        for title, count in sorted(
            titles.items(), key=lambda kv: kv[1], reverse=True,
        ):
            lines.append(f'  - ({count}) {title}')
        lines.append('')

    data_block = '\n'.join(lines)
    return (
        '以下是从上交所 IPO 披露平台抓取的汽车制造业(C36)全部项目\n'
        '的披露文件清单, 已按 fileTypeMap 与 fileType 编码分组,\n'
        '每组列出文件标题(fileTitle)及出现次数:\n\n'
        f'{data_block}\n'
        '请分析以上数据, 总结 fileTypeMap 与 fileType 编码的映射规律:\n'
        '1. 每个 (fileTypeMap, fileType) 组合对应的披露文件类别\n'
        '   (如招股说明书、问询函回复、注册批文等);\n'
        '2. 编码本身的结构规律(前缀含义、数字位含义、后缀与文件\n'
        '   版本/轮次的关系等);\n'
        '3. fileType 为 None 的分组可能代表什么;\n'
        '4. 最终用 markdown 表格输出完整映射表, 并附简要说明.\n'
    )


def resolve_api_key() -> str:
    """获取 DeepSeek API Key, 脚本常量优先, 其次 settings.

    Returns:
        API Key 字符串, 未配置时为空串.
    """
    return DEEPSEEK_API_KEY or settings.deepseek_api_key


def call_deepseek(prompt: str, api_key: str) -> str:
    """调用 DeepSeek chat 接口获取映射规律分析结果.

    Args:
        prompt: 用户消息内容.
        api_key: DeepSeek API Key.

    Returns:
        模型回复的文本内容.

    Raises:
        httpx.HTTPStatusError: 接口返回非 2xx 时抛出.
    """
    print(
        f'\n调用 DeepSeek | model={DEEPSEEK_MODEL} | '
        f'prompt 长度={len(prompt)} 字符'
    )
    resp = httpx.post(
        f'{DEEPSEEK_BASE_URL}/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': DEEPSEEK_MODEL,
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        '你是金融信息披露领域的数据分析专家, '
                        '擅长从原始数据中归纳编码规则.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.3,
        },
        timeout=180.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content']


def save_report(
    answer: str,
    groups: dict[tuple[str, int | None], dict[str, int]],
) -> Path:
    """将分析结果与原始分组数据写入报告文件.

    Args:
        answer: 模型返回的映射规律分析文本.
        groups: collect_title_groups 的返回值.

    Returns:
        生成的报告文件路径.
    """
    total_files = sum(sum(titles.values()) for titles in groups.values())
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lines: list[str] = [
        '# C36 IPO 披露文件类型编码映射规律报告',
        '',
        f'- 生成时间: {now}',
        '- 数据来源: 上交所 IPO 披露平台 (query.sse.com.cn)',
        '- 行业: 汽车制造业 (证监会行业代码 C36)',
        f'- 统计口径: {total_files} 个去重文件 | '
        f'{len(groups)} 个编码组合',
        f'- 分析模型: {DEEPSEEK_MODEL}',
        '',
        '## 映射规律分析',
        '',
        answer,
        '',
        '## 附录: 原始分组数据',
        '',
    ]
    for (type_map, file_type), titles in sorted(
        groups.items(), key=lambda kv: kv[0][0],
    ):
        count = sum(titles.values())
        lines.append(
            f'### fileTypeMap={type_map} | fileType={file_type} '
            f'({count} 个文件)'
        )
        lines.append('')
        for title, num in sorted(
            titles.items(), key=lambda kv: kv[1], reverse=True,
        ):
            lines.append(f'- ({num}) {title}')
        lines.append('')

    REPORT_FILE.write_text('\n'.join(lines), encoding='utf-8')
    return REPORT_FILE


def main() -> None:
    """采集文件信息并调用大模型总结映射规律."""
    api_key = resolve_api_key()
    if not api_key:
        print(
            '未配置 DeepSeek API Key: 请在脚本顶部 DEEPSEEK_API_KEY '
            '填入, 或在 .env 中设置 IPO_KNOW_DEEPSEEK_API_KEY'
        )
        sys.exit(1)

    with SSEClient() as client:
        projects = fetch_all_projects(client)
        print(f'\n共 {len(projects)} 个项目, 开始采集文件信息...\n')
        groups = collect_title_groups(client, projects)

    total_files = sum(
        sum(titles.values()) for titles in groups.values()
    )
    print(
        f'\n采集完成: {len(groups)} 个编码组合 | '
        f'{total_files} 个去重文件'
    )

    prompt = build_prompt(groups)
    answer = call_deepseek(prompt, api_key)
    report_path = save_report(answer, groups)

    print('\n' + '=' * 62)
    print('DeepSeek 映射规律分析结果')
    print('=' * 62)
    print(answer)
    print('\n' + '-' * 62)
    print(f'报告已保存至: {report_path}')


if __name__ == '__main__':
    main()
