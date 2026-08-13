"""上交所 IPO 接口响应 Pydantic 模型.

包含项目查询和文件查询两套响应模型, 支持 JSONP 响应的 Pydantic
校验与反序列化.
"""

# ruff: noqa: N815
# 外部接口返回字段使用 camelCase, 模型字段名需与响应键保持一致.

from typing import Any
from typing import Generic
from typing import TypeVar

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


T = TypeVar('T')


# ==================================================
# 嵌套子模型
# ==================================================
class IntermediaryPerson(BaseModel):
    """中介机构签字或负责人员信息.

    Attributes:
        i_p_personName: 人员姓名.
        i_p_jobType: 职位类型编码.
        i_p_personId: 人员唯一标识 ID.
        i_p_jobTitle: 职位名称.
    """

    i_p_personName: str = Field(description='人员姓名')
    i_p_jobType: int = Field(description='职位类型编码')
    i_p_personId: str = Field(description='人员唯一标识ID')
    i_p_jobTitle: str = Field(description='职位名称')


class Intermediary(BaseModel):
    """中介机构信息.

    包含保荐机构、会所、律所、评估等中介机构信息.

    Attributes:
        auditId: 关联审核项目 ID.
        i_intermediaryType: 机构类型编码, 1=保荐机构 2=会计师事务所
            3=律师事务所 4=评估机构.
        i_intermediaryId: 机构唯一标识 ID.
        i_person: 机构对应签字或负责人员列表.
        i_intermediaryAbbrName: 机构简称.
        i_intermediaryName: 机构全称.
        i_intermediaryOrder: 机构排序号.
    """

    auditId: str = Field(description='关联审核项目ID')
    i_intermediaryType: int = Field(
        description='机构类型编码: 1=保荐机构 2=会计师事务所 '
        '3=律师事务所 4=评估机构'
    )
    i_intermediaryId: str = Field(description='机构唯一标识ID')
    i_person: list[IntermediaryPerson] = Field(
        description='机构对应签字/负责人员列表'
    )
    i_intermediaryAbbrName: str = Field(description='机构简称')
    i_intermediaryName: str = Field(description='机构全称')
    i_intermediaryOrder: int = Field(description='机构排序号')


class StockIssuerPerson(BaseModel):
    """发行人关键人员信息.

    Attributes:
        s_personName: 人员姓名.
        auditId: 关联审核项目 ID.
        s_stockIssueId: 发行 ID.
        s_personId: 人员唯一标识 ID.
        s_issueCompanyFullName: 发行人公司全称.
        s_csrcCode: 证监会行业代码.
        s_jobTitle: 人员职务.
        s_issueCompanyAbbrName: 发行人公司简称.
        s_csrcCodeDesc: 证监会行业名称.
        s_province: 发行人注册省份.
        s_areaNameDesc: 发行人注册地市或区县.
        s_companyCode: 公司代码.
    """

    s_personName: str = Field(description='人员姓名')
    auditId: str = Field(description='关联审核项目ID')
    s_stockIssueId: str = Field(description='发行ID')
    s_personId: str = Field(description='人员唯一标识ID')
    s_issueCompanyFullName: str = Field(description='发行人公司全称')
    s_csrcCode: str = Field(description='证监会行业代码')
    s_jobTitle: str = Field(description='人员职务')
    s_issueCompanyAbbrName: str = Field(description='发行人公司简称')
    s_csrcCodeDesc: str = Field(description='证监会行业名称')
    s_province: str = Field(description='发行人注册省份')
    s_areaNameDesc: str = Field(description='发行人注册地市/区县')
    s_companyCode: str = Field(description='公司代码')


class IPOProjectItem(BaseModel):
    """IPO 项目单条核心数据.

    同时适用于列表模式和详情模式.

    Attributes:
        updateDate: 数据最后更新时间, 格式 YYYYMMDDHHMMSS.
        planIssueCapital: 计划募集资金额, 单位为亿元.
        suspendStatus: 项目中止状态标识.
        wenHao: 监管批复文号.
        stockAuditName: 项目全称, 包含发行人和板块信息.
        projectType: 项目类型编码.
        currStatus: 当前审核状态编码.
        stockAuditNum: 项目审核编号, 详情查询的核心入参.
        registeResult: 注册结果编码.
        intermediary: 项目涉及的中介机构数组.
        collectType: 数据采集类型编码.
        stockIssuer: 发行人关键人员数组.
        createTime: 数据创建时间, 格式 YYYYMMDDHHMMSS.
        auditApplyDate: 审核受理日期, 格式 YYYYMMDDHHMMSS.
        issueAmount: 拟发行股份数量.
        uniformCode: 发行人统一社会信用代码.
        commitiResult: 上市委审议结果文本.
        issueMarketType: 上市板块, 1=科创板 2=主板.
        OPERATION_SEQ: 数据版本序列号, 用于增量更新判断.
    """

    updateDate: str = Field(description='数据最后更新时间, 格式 YYYYMMDDHHMMSS')
    planIssueCapital: float | None = Field(
        None, description='计划募集资金额 (单位: 亿元)'
    )
    suspendStatus: str = Field(description='项目中止状态标识')
    wenHao: str = Field(description='监管批复文号')
    stockAuditName: str = Field(description='项目全称 (发行人+板块)')
    projectType: int = Field(description='项目类型编码')
    currStatus: int = Field(description='当前审核状态编码')
    stockAuditNum: str = Field(description='项目审核编号, 详情查询的核心入参')
    registeResult: int | None = Field(None, description='注册结果编码')
    intermediary: list[Intermediary] = Field(
        description='项目涉及的中介机构数组'
    )
    collectType: int = Field(description='数据采集类型编码')
    stockIssuer: list[StockIssuerPerson] = Field(
        description='发行人关键人员数组'
    )
    createTime: str = Field(description='数据创建时间, 格式 YYYYMMDDHHMMSS')
    auditApplyDate: str = Field(description='审核受理日期, 格式 YYYYMMDDHHMMSS')
    issueAmount: str = Field(description='拟发行股份数量')
    uniformCode: str = Field(description='发行人统一社会信用代码')
    commitiResult: str = Field(description='上市委审议结果文本')
    issueMarketType: int = Field(description='上市板块: 1=科创板 2=主板')
    OPERATION_SEQ: str = Field(description='数据版本序列号, 用于增量更新判断')

    @field_validator('planIssueCapital', 'registeResult', mode='before')
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        """将空字符串转换为 None.

        Args:
            v: 原始字段值.

        Returns:
            当值为空字符串时返回 None, 否则返回原值.
        """
        if isinstance(v, str) and v.strip() == '':
            return None
        return v


# ==================================================
# 通用分页容器与响应外壳
# ==================================================
class PageHelp(BaseModel, Generic[T]):
    """接口通用分页数据容器.

    Attributes:
        beginPage: 起始页码.
        cacheSize: 缓存数据条数.
        data: 当前页业务数据列表.
        endDate: 查询结束日期.
        endPage: 结束页码.
        objectResult: 扩展结果对象.
        pageCount: 总页数.
        pageNo: 当前页码.
        pageSize: 每页数据条数.
        pageSizeWithOutLimit: 无限制页大小参数.
        searchDate: 查询执行日期.
        sort: 排序规则.
        startDate: 查询开始日期.
        total: 筛选条件下总数据条数.
    """

    beginPage: int = Field(description='起始页码')
    cacheSize: int = Field(description='缓存数据条数')
    data: list[T] = Field(description='当前页业务数据列表')
    endDate: str | None = Field(None, description='查询结束日期')
    endPage: int | None = Field(None, description='结束页码')
    objectResult: Any | None = Field(None, description='扩展结果对象')
    pageCount: int = Field(description='总页数')
    pageNo: int = Field(description='当前页码')
    pageSize: int = Field(description='每页数据条数')
    pageSizeWithOutLimit: int = Field(description='无限制页大小参数')
    searchDate: str | None = Field(None, description='查询执行日期')
    sort: str | None = Field(None, description='排序规则')
    startDate: str | None = Field(None, description='查询开始日期')
    total: int = Field(description='筛选条件下总数据条数')


class BaseSSEResponse(BaseModel, Generic[T]):
    """上交所 SOA 接口通用响应外壳.

    Attributes:
        actionErrors: 接口错误信息集合.
        actionMessages: 接口提示信息集合.
        fieldErrors: 字段级错误信息.
        isPagination: 是否分页标识, 字符串型布尔值.
        jsonCallBack: JSONP 回调函数名, 与请求参数一致.
        locale: 语言区域标识.
        pageHelp: 分页数据容器, 核心业务数据载体.
        pageNo: 冗余页码字段, 与 pageHelp.pageNo 一致.
        pageSize: 冗余页大小字段, 与 pageHelp.pageSize 一致.
        queryDate: 接口查询执行时间.
        result: 冗余结果列表, 与 pageHelp.data 内容完全一致.
        securityCode: 证券代码占位字段, 项目查询场景为空.
        sqlId: SQL 查询标识, 与请求参数一致.
        texts: 扩展文本字段.
        type: 响应类型标识.
        validateCode: 接口校验码.
    """

    actionErrors: list[Any] = Field(
        default_factory=list, description='接口错误信息集合'
    )
    actionMessages: list[Any] = Field(
        default_factory=list, description='接口提示信息集合'
    )
    fieldErrors: dict = Field(
        default_factory=dict, description='字段级错误信息'
    )
    isPagination: str = Field(description='是否分页标识 (字符串型布尔值)')
    jsonCallBack: str = Field(description='JSONP回调函数名, 与请求参数一致')
    locale: str = Field(description='语言区域标识')
    pageHelp: PageHelp[T] = Field(description='分页数据容器, 核心业务数据载体')
    pageNo: int | None = Field(
        None, description='冗余页码字段, 与 pageHelp.pageNo 一致'
    )
    pageSize: int | None = Field(
        None, description='冗余页大小字段, 与 pageHelp.pageSize 一致'
    )
    queryDate: str = Field(description='接口查询执行时间')
    result: list[T] = Field(
        description='冗余结果列表, 与 pageHelp.data 内容完全一致'
    )
    securityCode: str = Field(description='证券代码占位字段, 项目查询场景为空')
    sqlId: str = Field(description='SQL查询标识, 与请求参数一致')
    texts: Any | None = Field(None, description='扩展文本字段')
    type: str = Field(description='响应类型标识')
    validateCode: str = Field(description='接口校验码')


# ==================================================
# 接口专属响应模型
# ==================================================
class SSEIPOQueryResponse(BaseSSEResponse[IPOProjectItem]):
    """上交所 IPO 项目查询接口响应模型.

    同时适配列表分页返回和单条详情返回两种场景.
    详情场景取 `pageHelp.data[0]` 即可获得单项目完整数据.
    """

    pass


# ==================================================
# 文件查询子模型
# ==================================================
class FileItem(BaseModel):
    """披露文件单条数据.

    Attributes:
        auditId: 关联审核 ID.
        companyCode: 公司代码.
        fileName: PDF 文件名.
        companyAbbr: 公司简称.
        filePath: 文件相对路径. 【重要】拼接下载 URL 时, 静态资源域名
            与本路径之间必须加 /stock 前缀, 否则 CDN 返回 302 至 /404.
        companyName: 公司全称.
        isPreviewFile: 是否支持在线预览.
        marketType: 市场板块编码.
        fileTypeMap: 文件类型映射编码.
        fileSize: 文件大小 (字节).
        fileTitle: 文件中文标题.
        fileUpdTime: 文件更新时间, 格式为 YYYYMMDDHHMMSS.
        fileVersion: 文件版本号.
        fileType: 文件类型编码.
        fileId: 文件唯一 ID.
    """

    auditId: str = Field(description='关联审核ID')
    companyCode: str = Field(description='公司代码')
    fileName: str = Field(description='PDF文件名')
    companyAbbr: str = Field(description='公司简称')
    filePath: str = Field(
        description='文件相对路径. 【重要】拼接下载 URL 时, 静态资源域名'
        '与本路径之间必须加 /stock 前缀, '
        '例: https://static.sse.com.cn/stock{filePath}, '
        '否则 CDN 返回 302 至 /404'
    )
    companyName: str = Field(description='公司全称')
    isPreviewFile: str = Field(description='是否支持在线预览')
    marketType: int = Field(description='市场板块编码')
    fileTypeMap: str = Field(description='文件类型映射编码')
    fileSize: int = Field(description='文件大小 (字节)')
    fileTitle: str = Field(description='文件中文标题')
    fileUpdTime: str = Field(description='文件更新时间 YYYYMMDDHHMMSS')
    fileVersion: int | None = Field(None, description='文件版本号')
    fileType: int | None = Field(None, description='文件类型编码')
    fileId: str = Field(description='文件唯一ID')

    @field_validator('fileVersion', 'fileType', mode='before')
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        """将空字符串转换为 None.

        Args:
            v: 原始字段值.

        Returns:
            当值为空字符串时返回 None, 否则返回原值.
        """
        if v == '':
            return None
        return v


class SSEFileListResponse(BaseSSEResponse[FileItem]):
    """文件列表接口响应模型."""

    pass
