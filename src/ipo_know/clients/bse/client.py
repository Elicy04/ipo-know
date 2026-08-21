"""北交所 IPO 审核信息披露客户端.

提供 BSEClient 类, 继承 BaseHttpClient, 封装北交所 IPO 项目
查询 (infoResult.do) 与项目详情文件查询 (infoDetailResult.do)
两个 JSONP 接口的调用与解析逻辑.
"""

import datetime
from typing import Any

from loguru import logger

from ipo_know.clients.bse.models import BSEFileItem
from ipo_know.clients.bse.models import BSEProjectItem
from ipo_know.clients.http_client import BaseHttpClient
from ipo_know.clients.jsonp_utils import generate_jsonp_callback
from ipo_know.clients.jsonp_utils import parse_jsonp
from ipo_know.config.config import settings


# 北交所 JSONP 响应外层是数组, parse_jsonp 类型注解为 dict,
# 实际 json.loads 可返回 list, 此处统一用 Any 承接.
_JsonpResult = Any

# 项目查询请求所需的 needFields 字段列表.
_PROJECT_NEED_FIELDS: tuple[str, ...] = (
    'id', 'stockCode', 'stockName', 'companyName', 'status',
    'registerAddress', 'sponsorOrg', 'appraisalOrg', 'lawyerOrg',
    'accountingOrg', 'updateDate', 'receiveDate', 'operatingTime',
)


def _bse_date_to_str(date_obj: object) -> str | None:
    """将北交所 Java 风格日期对象转为 YYYY-MM-DD 字符串.

    北交所接口返回的日期字段为 JSON 对象, 含 year (自 1900 起),
    month (0-indexed), date (日) 等属性; 或直接含 time 毫秒时间戳.

    Args:
        date_obj: 北交所日期对象, 或 None / 字符串.

    Returns:
        YYYY-MM-DD 格式字符串, 无法解析时返回 None.
    """
    if date_obj is None or isinstance(date_obj, str):
        return date_obj  # type: ignore[return-value]
    if not isinstance(date_obj, dict):
        return None
    # 优先使用 time 毫秒时间戳, 精度更高.
    ts_ms = date_obj.get('time')
    if ts_ms is not None:
        dt = datetime.datetime.fromtimestamp(
            ts_ms / 1000,
            tz=datetime.timezone(datetime.timedelta(hours=8)),
        )
        return dt.strftime('%Y-%m-%d')
    # 回退: 使用 year/month/date 字段.
    year = date_obj.get('year')
    month = date_obj.get('month')
    day = date_obj.get('date')
    if year is not None and month is not None and day is not None:
        return f'{year + 1900:04d}-{month + 1:02d}-{day:02d}'
    return None


def _parse_jsonp_text(text: str) -> _JsonpResult:
    """解析北交所 JSONP 响应, 兼容数组和对象.

    parse_jsonp 的类型注解为 dict, 但北交所接口实际返回的是
    数组 (jQuery...([{...}])). 此处先用 parse_jsonp 尝试, 若
    类型不符则直接用 json.loads 兜底.

    Args:
        text: JSONP 格式响应原文.

    Returns:
        解析后的 Python 对象 (通常为 list 或 dict).

    Raises:
        ValueError: JSONP 格式不匹配或 JSON 解析失败.
    """
    result = parse_jsonp(text)
    # parse_jsonp 内部使用 json.loads, 返回值实际可能是 list,
    # 只是类型注解标注为 dict, 这里不做类型断言, 直接返回.
    return result  # type: ignore[return-value]


class BSEClient(BaseHttpClient):
    """北交所 IPO 审核信息披露客户端.

    继承 BaseHttpClient (httpx + hishel + tenacity), 封装北交所
    两个核心 JSONP 接口:
        - infoResult.do: 按股票代码查询 IPO 项目摘要
        - infoDetailResult.do: 按项目 ID 查询全部披露文件

    Attributes:
        base_url: 接口基础域名 (继承自 BaseHttpClient).
    """

    def __init__(  # noqa: ANN204  # pystyle: __init__ 不需要返回值注解
        self,
        base_url: str | None = None,
        timeout: int | None = None,
    ):
        """初始化北交所客户端.

        Args:
            base_url: 北交所官网域名, 默认从 settings.bse.base_url 读取.
            timeout: 请求超时时间 (秒), 默认从 settings.bse.timeout 读取.
        """
        resolved_base_url = base_url or settings.bse.base_url
        resolved_timeout = (
            timeout if timeout is not None else settings.bse.timeout
        )

        super().__init__(
            base_url=resolved_base_url,
            timeout=float(resolved_timeout),
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) '
                    'Gecko/20100101 Firefox/154.0'
                ),
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://www.bse.cn/audit/project_news.html',
                'Accept': 'text/html, */*; q=0.01',
            },
        )
        logger.info(
            'BSEClient 初始化 | base_url={} | timeout={}s',
            resolved_base_url,
            resolved_timeout,
        )

    # ==================================================
    # 公开接口
    # ==================================================

    def query_project(self, stock_code: str) -> BSEProjectItem | None:
        """按股票代码查询北交所 IPO 项目摘要.

        调用 /projectNewsController/infoResult.do, 返回该项目
        的基本信息 (项目 ID、公司名、审核状态等).

        Args:
            stock_code: 股票代码, 如 '874386'.

        Returns:
            BSEProjectItem 实例; 无匹配项目时返回 None.
        """
        callback = generate_jsonp_callback()
        url = f'/projectNewsController/infoResult.do?callback={callback}'

        # 构造 application/x-www-form-urlencoded 表单.
        # httpx 的 data 参数不支持同名多值列表, 需手动编码.
        form_parts = [
            'statetypes%5B%5D=',
            'page=0',
            f'companyCode={stock_code}',
            'isNewThree=1',
            'sortfield=updateDate',
            'sorttype=desc',
            'keyword=',
        ]
        for field in _PROJECT_NEED_FIELDS:
            form_parts.append(f'needFields%5B%5D={field}')
        form_body = '&'.join(form_parts)

        logger.info('BSE 查询项目 | stock_code={}', stock_code)
        resp = self.post(
            url,
            content=form_body,
            headers={
                'Content-Type': (
                    'application/x-www-form-urlencoded; charset=UTF-8'
                ),
            },
        )

        parsed = _parse_jsonp_text(resp.text)
        # 北交所响应: jQuery...([{countsInfo, listInfo}])
        if not isinstance(parsed, list) or not parsed:
            logger.warning(
                'BSE 项目查询响应非数组或为空 | stock_code={}',
                stock_code,
            )
            return None

        root = parsed[0]
        if not isinstance(root, dict):
            logger.warning(
                'BSE 项目查询响应首元素非 dict | stock_code={}',
                stock_code,
            )
            return None

        list_info = root.get('listInfo')
        if not list_info or not isinstance(list_info, dict):
            logger.warning('BSE 响应缺少 listInfo | stock_code={}', stock_code)
            return None

        content = list_info.get('content')
        if not content or not isinstance(content, list) or len(content) == 0:
            logger.info('BSE 未找到项目 | stock_code={}', stock_code)
            return None

        raw = content[0]
        return _build_project_item(raw)

    def query_project_files(self, project_id: int) -> list[BSEFileItem]:
        """按项目 ID 查询全部披露文件.

        调用 /projectNewsController/infoDetailResult.do, 遍历
        xxgkInfo 各分类/阶段以及 wxhfhInfo、hztzInfo、hyggjgInfo
        等顶层文件列表, 扁平化返回.

        Args:
            project_id: 项目 ID (infoResult.do 返回的 id 字段).

        Returns:
            所有披露文件项的列表; 无文件时返回空列表.
        """
        callback = generate_jsonp_callback()
        url = (
            f'/projectNewsController/infoDetailResult.do'
            f'?id={project_id}&callback={callback}'
        )
        form_body = f'id={project_id}'

        logger.info('BSE 查询项目文件 | project_id={}', project_id)
        resp = self.post(
            url,
            content=form_body,
            headers={
                'Content-Type': (
                    'application/x-www-form-urlencoded; charset=UTF-8'
                ),
            },
        )

        parsed = _parse_jsonp_text(resp.text)
        if not isinstance(parsed, list) or not parsed:
            logger.warning(
                'BSE 文件查询响应非数组或为空 | project_id={}',
                project_id,
            )
            return []

        root = parsed[0]
        if not isinstance(root, dict):
            logger.warning(
                'BSE 文件查询响应首元素非 dict | project_id={}',
                project_id,
            )
            return []

        files: list[BSEFileItem] = []

        # 1. xxgkInfo: 按分类 (GPFXSMS/GPFXBJS/SJBG/FYYJS/GPZJXCGPTJS/QT 等)
        #    → 按阶段 (SYG/BHG/SBG 等) → 文件对象列表.
        xxgk_info = root.get('xxgkInfo')
        if isinstance(xxgk_info, dict):
            for category_val in xxgk_info.values():
                if not isinstance(category_val, dict):
                    continue
                for stage_files in category_val.values():
                    if not isinstance(stage_files, list):
                        continue
                    for raw_file in stage_files:
                        item = _build_file_item(raw_file)
                        if item is not None:
                            files.append(item)

        # 2. 顶层文件列表: wxhfhInfo (问询回复函), hztzInfo (核准通知),
        #    hyggjgInfo (审议会议结果公告) 等.
        for top_key in ('wxhfhInfo', 'hztzInfo', 'hyggjgInfo'):
            top_files = root.get(top_key)
            if not isinstance(top_files, list):
                continue
            for raw_file in top_files:
                item = _build_file_item(raw_file)
                if item is not None:
                    files.append(item)

        logger.info(
            'BSE 项目文件解析完成 | project_id={} | 文件数={}',
            project_id,
            len(files),
        )
        return files

    @staticmethod
    def build_file_url(file_path: str) -> str:
        """将相对文件路径拼接为完整下载 URL.

        Args:
            file_path: 北交所接口返回的 destFilePath 相对路径.

        Returns:
            完整 URL, 如 https://www.bse.cn/disclosure/.../xxx.pdf.
        """
        return f'https://www.bse.cn{file_path}'


# ==================================================
# 内部辅助函数
# ==================================================


def _build_project_item(raw: dict[str, Any]) -> BSEProjectItem:
    """将北交所原始项目 dict 转为 BSEProjectItem.

    处理 camelCase → snake_case 字段映射, 并将 Java 日期对象
    转为 YYYY-MM-DD 字符串.
    """
    return BSEProjectItem(
        id=raw['id'],
        stock_code=raw.get('stockCode', ''),
        stock_name=raw.get('stockName'),
        company_name=raw.get('companyName'),
        status=raw.get('status'),
        register_address=raw.get('registerAddress'),
        update_date=_bse_date_to_str(raw.get('updateDate')),
        receive_date=_bse_date_to_str(raw.get('receiveDate')),
    )


def _build_file_item(raw: object) -> BSEFileItem | None:
    """将北交所原始文件 dict 转为 BSEFileItem.

    处理 camelCase → snake_case 字段映射; 缺少 destFilePath
    时返回 None.
    """
    if not isinstance(raw, dict):
        return None
    dest_file_path = raw.get('destFilePath')
    if not dest_file_path:
        logger.debug('BSE 文件缺少 destFilePath, 跳过 | raw={}', raw)
        return None
    return BSEFileItem(
        dest_file_path=dest_file_path,
        disclosure_title=raw.get('disclosureTitle'),
        disclosure_type=raw.get('disclosureType'),
        publish_date=raw.get('publishDate'),
        up_date=_bse_date_to_str(raw.get('upDate')),
        file_ext=raw.get('fileExt'),
    )
