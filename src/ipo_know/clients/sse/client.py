"""上交所 IPO 披露平台统一客户端.

提供 SSEClient 类, 继承 BaseHttpClient, 封装上交所 IPO 项目查询
与披露文件查询等公开接口的调用逻辑.
"""

import json
import random
import re
import string
import time
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel

from ipo_know.clients.http_client import BaseHttpClient
from ipo_know.clients.sse.loader import ApiConfig
from ipo_know.clients.sse.loader import ConfigLoader
from ipo_know.clients.sse.models import IPOProjectItem
from ipo_know.clients.sse.models import SSEFileListResponse
from ipo_know.clients.sse.models import SSEIPOQueryResponse
from ipo_know.config.config import settings


class SSEClient(BaseHttpClient):
    """上交所 IPO 披露平台统一客户端.

    继承 BaseHttpClient (httpx + hishel + tenacity), 叠加 SOA 配置
    驱动能力: YAML 路由 → JSONP 解析 → Pydantic 校验.

    当前支持:
        - IPO 项目多条件筛选查询 (query_projects)
        - IPO 披露文件列表查询 (query_files)

    Attributes:
        base_url: 接口基础域名 (继承自 BaseHttpClient).
        config_loader: YAML 配置加载器实例.
        model_registry: Pydantic 模型注册表.
    """

    # JSONP 响应解析正则: 匹配 回调名(...) 格式
    _JSONP_REGEX = re.compile(r'^[a-zA-Z0-9_]+\((.*)\)\s*;?\s*$', re.DOTALL)

    # 【重要】项目查询接口的审核状态分桶取值.
    # 不传 currStatus 时后端只返回在审项目, 全量口径必须逐桶
    # 查询后合并, 详见 query_projects_all_status.
    PROJECT_STATUS_BUCKETS: tuple[str, ...] = (
        '2',  # 在审: 已受理/已问询/上市委审议/提交注册等
        '5',  # 注册结果: 注册生效等
        '8',  # 终止: 终止审核/撤回等
    )

    def __init__(
        self,
        base_url: str | None = None,
        config_dir: str | None = None,
        timeout: int | None = None,
        extra_headers: dict[str, str] | None = None,
        cache_dir: str | None = None,
    ) -> None:
        """初始化上交所客户端.

        Args:
            base_url: 接口基础域名, 默认从上交所配置读取.
            config_dir: API 配置文件目录, 留空则使用内置 api/ 目录.
            timeout: HTTP 请求超时 (秒), 默认从上交所配置读取.
            extra_headers: 额外请求头, 覆盖默认请求头同名字段.
            cache_dir: HTTP 缓存目录, 为 None 则不启用缓存.
        """
        resolved_url = (base_url or settings.sse.query_base_url).rstrip('/')

        # 先做 SSE 专有初始化: YAML 加载 + 模型注册表 + 请求头
        if config_dir is None:
            config_dir = str(Path(__file__).parent / 'api')

        logger.info(
            '上交所客户端初始化 | base_url={} | timeout={}s | '
            'config_dir={}',
            resolved_url,
            timeout or settings.sse.timeout,
            config_dir,
        )

        self.config_loader = ConfigLoader()
        self.config_loader.load_dir(config_dir)

        self.model_registry: dict[str, type[BaseModel]] = {
            'SSEIPOQueryResponse': SSEIPOQueryResponse,
            'SSEFileListResponse': SSEFileListResponse,
        }

        self.global_headers: dict[str, str] = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/126.0.0.0 Safari/537.36'
            ),
            'Accept': '*/*',
            'Referer': f'{settings.sse.www_base_url}/',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        if extra_headers:
            self.global_headers.update(extra_headers)

        # 再调基类: httpx + hishel + tenacity
        # headers 在 _build_request_headers 中按请求组装,
        # 不在此处设置, 以支持 YAML 中 inherit_global: false 场景
        super().__init__(
            base_url=resolved_url,
            headers={},
            timeout=timeout or settings.sse.timeout,
            cache_dir=cache_dir,
        )

    # ==================================================
    # 参数与请求头构建
    # ==================================================
    def _generate_jsonp_callback(self) -> str:
        """生成符合规范的随机 JSONP 回调函数名."""
        rand_suffix = ''.join(
            random.choices(string.ascii_lowercase + string.digits, k=8)
        )
        return f'jQuery_{int(time.time() * 1000)}_{rand_suffix}'

    def _build_request_params(
        self,
        api_config: ApiConfig,
        business_params: dict[str, Any],
    ) -> dict[str, Any]:
        """组装最终请求参数.

        优先级: 业务传入 > 默认值 > 动态生成;
        同时执行必填校验与类型转换.
        """
        final_params: dict[str, Any] = {}

        for param_cfg in api_config.query_params:
            param_name = param_cfg.name

            # 1. 动态参数: 运行时自动生成
            if param_cfg.dynamic:
                if param_name == 'jsonCallBack':
                    final_params[param_name] = (
                        self._generate_jsonp_callback()
                    )
                elif param_name == '_':
                    final_params[param_name] = str(
                        int(time.time() * 1000)
                    )
                else:
                    raise ValueError(
                        f'未定义处理逻辑的动态参数: {param_name}'
                    )
                continue

            # 2. 业务传入参数优先, 同步做类型转换
            if param_name in business_params:
                value = business_params[param_name]
                if param_cfg.type == 'integer':
                    value = int(value)
                elif param_cfg.type == 'boolean':
                    value = (
                        str(value).lower()
                        if isinstance(value, bool)
                        else value
                    )
                final_params[param_name] = value
                continue

            # 3. 填充配置默认值
            if param_cfg.default is not None:
                final_params[param_name] = param_cfg.default
                continue

            # 4. 必填参数缺失拦截
            if param_cfg.required:
                logger.error(
                    '接口 [{api_id}] 缺少必填参数: {param_name}',
                    api_id=api_config.api_meta.api_id,
                    param_name=param_name,
                )
                raise ValueError(
                    f'接口 [{api_config.api_meta.api_id}] '
                    f'缺少必填参数: {param_name}'
                )

        return final_params

    def _build_request_headers(
        self,
        api_config: ApiConfig,
    ) -> dict[str, str]:
        """组装请求头.

        全局头为基础, 接口专属头做覆盖.
        """
        if api_config.headers.inherit_global:
            base_headers = self.global_headers.copy()
        else:
            base_headers = {}
        base_headers.update(api_config.headers.extra)
        return base_headers

    # ==================================================
    # 响应解析
    # ==================================================
    def _parse_jsonp_response(self, resp_text: str) -> dict[str, Any]:
        """解析 JSONP 格式响应, 提取内部 JSON 数据."""
        match = self._JSONP_REGEX.match(resp_text.strip())
        if not match:
            logger.error(
                'JSONP 解析失败 | 响应长度: {} | 前 200 字符: {}',
                len(resp_text), resp_text[:200],
            )
            raise ValueError('响应内容不是合法的 JSONP 格式')
        json_content = match.group(1)
        return json.loads(json_content)

    def _get_model_class(self, model_name: str) -> type[BaseModel]:
        """从模型注册表获取对应 Pydantic 类."""
        if model_name not in self.model_registry:
            raise KeyError(f'模型注册表中未找到模型: {model_name}')
        return self.model_registry[model_name]

    # ==================================================
    # SOA 请求入口 (不与基类 request() 冲突)
    # ==================================================
    def call_api(
        self,
        api_id: str,
        params: dict[str, Any] | None = None,
        validate_response: bool = True,
    ) -> dict[str, Any] | BaseModel:
        """通用 SOA 请求方法.

        根据 api_id 查找 YAML 配置 → 组装参数 → 调基类 request()
        (含自动重试 + HTTP 缓存) → 解析 JSONP/JSON → 可选 Pydantic
        校验.

        Args:
            api_id: 接口配置 ID.
            params: 业务查询参数.
            validate_response: 是否用 Pydantic 模型校验响应.

        Returns:
            校验开启时返回 Pydantic 模型实例, 关闭时返回字典.
        """
        params = params or {}
        api_config = self.config_loader.get_config(api_id)

        logger.info(
            'SOA 请求 | api_id={} ({}) | params={}',
            api_id, api_config.api_meta.api_name, params,
        )

        req_params = self._build_request_params(api_config, params)
        req_headers = self._build_request_headers(api_config)

        logger.debug(
            '请求参数组装完成 | api_id={} | params={}',
            api_id, req_params,
        )

        # 基类的 request() —— 自带 tenacity 重试 + hishel 缓存
        response = self.request(
            method=api_config.api_meta.method,
            url=api_config.api_meta.endpoint,
            params=req_params,
            headers=req_headers,
        )

        # 解析响应数据
        if api_config.response.format == 'jsonp':
            resp_data = self._parse_jsonp_response(response.text)
        elif api_config.response.format == 'json':
            resp_data = response.json()
        else:
            raise ValueError(
                f'不支持的响应格式: {api_config.response.format}'
            )

        logger.debug(
            '响应解析完成 | api_id={} | format={}',
            api_id, api_config.response.format,
        )

        # 可选: Pydantic 模型校验
        if validate_response:
            model_cls = self._get_model_class(
                api_config.response.response_model
            )
            return model_cls(**resp_data)

        return resp_data

    # ==================================================
    # IPO 业务接口
    # ==================================================
    def query_projects(
        self,
        csrc_code: str | None = None,
        stock_audit_num: str | None = None,
        issue_market_type: str = '1,2',
        curr_status: str | None = None,
        is_pagination: bool = False,
        page_no: int = 1,
        page_size: int = 100,
    ) -> SSEIPOQueryResponse:
        """IPO 项目通用筛选查询.

        支持多条件自由组合, 所有筛选参数均为可选.

        【重要】curr_status 不传时后端只返回在审状态项目
        (已受理/已问询/上市委审议/提交注册等), 注册生效、终止等
        历史项目会被静默过滤; 全量口径请用
        query_projects_all_status 或自行分状态查询合并.

        Args:
            csrc_code: 证监会行业代码, 如 C36=汽车制造业.
            stock_audit_num: 项目审核编号, 精确匹配单条项目.
            issue_market_type: 上市板块, 1=科创板 2=主板, 逗号分隔.
            curr_status: 审核状态, 2=在审 5=注册结果 8=终止;
                留空表示仅查在审状态项目.
            is_pagination: 是否启用分页.
            page_no: 页码, 从 1 开始.
            page_size: 每页条数, 最大 100.

        Returns:
            分页查询响应, 含项目列表与总数.
        """
        params: dict[str, Any] = {
            'isPagination': is_pagination,
            'issueMarketType': issue_market_type,
            'pageNo': page_no,
            'pageSize': page_size,
        }
        if csrc_code is not None:
            params['csrcCode'] = csrc_code
        if stock_audit_num is not None:
            params['stockAuditNum'] = stock_audit_num
        if curr_status:
            params['currStatus'] = curr_status

        return self.call_api(
            api_id='sse_ipo_project_query', params=params
        )

    def query_projects_all_status(
        self,
        csrc_code: str | None = None,
        issue_market_type: str = '1,2',
        page_size: int = 100,
    ) -> list[IPOProjectItem]:
        """按全部审核状态分桶查询并按审核编号去重.

        逐桶遍历 PROJECT_STATUS_BUCKETS 并分页拉取, 合并后按
        stockAuditNum 去重, 得到包含在审/注册结果/终止在内的
        全量项目列表.

        【重要】不要直接用 query_projects 的默认结果当全量口径,
        那只有在审状态项目.

        Args:
            csrc_code: 证监会行业代码, 如 C36=汽车制造业.
            issue_market_type: 上市板块, 1=科创板 2=主板, 逗号分隔.
            page_size: 每页条数, 最大 100.

        Returns:
            全状态去重后的项目列表.
        """
        merged: list[IPOProjectItem] = []
        seen_audit_nums: set[str] = set()

        for status in self.PROJECT_STATUS_BUCKETS:
            page_no = 1
            while True:
                resp = self.query_projects(
                    csrc_code=csrc_code,
                    issue_market_type=issue_market_type,
                    curr_status=status,
                    is_pagination=True,
                    page_no=page_no,
                    page_size=page_size,
                )
                page = resp.pageHelp
                for project in page.data:
                    if project.stockAuditNum in seen_audit_nums:
                        continue
                    seen_audit_nums.add(project.stockAuditNum)
                    merged.append(project)
                logger.info(
                    '全状态项目查询 | currStatus={} | 第{}/{}页 | '
                    '累计唯一项目 {} 个',
                    status, page_no, page.pageCount, len(merged),
                )
                if page_no >= page.pageCount or not page.data:
                    break
                page_no += 1

        return merged

    def query_files(
        self,
        audit_id: str,
        market_type: str = '1,2',
    ) -> SSEFileListResponse:
        """IPO 项目披露文件列表查询.

        按审核 ID 查询项目对应的全部披露文件清单.

        Args:
            audit_id: 项目审核 ID, 来自项目列表/详情.
            market_type: 市场板块, 1=科创板 2=主板, 逗号分隔.

        Returns:
            文件列表响应, 含 PDF 文件名、路径、大小等.
        """
        params: dict[str, Any] = {
            'auditId': audit_id,
            'marketType': market_type,
        }
        return self.call_api(
            api_id='sse_ipo_files_list_query', params=params
        )
