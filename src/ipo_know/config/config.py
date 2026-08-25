"""从环境变量和默认值加载的应用配置.

基于 pydantic-settings v2 实现类型安全的配置管理.
提供单例实例供项目各处直接导入使用.
"""

import functools
import pathlib
import sys

import pydantic
import pydantic_settings


@functools.cache
def app_root() -> pathlib.Path:
    """返回应用数据根目录.

    冻结环境（PyInstaller onedir）：exe 所在目录.
    开发环境：项目根目录（src 的父目录）.
    """
    if getattr(sys, 'frozen', False):
        return pathlib.Path(sys.executable).parent
    return pathlib.Path(__file__).resolve().parents[3]


class DatabaseConfig(pydantic.BaseModel):
    """数据库配置.

    管理 SQLite 数据库路径解析与连接 URL 生成.
    由顶层 Settings 通过 env_nested_delimiter 注入环境变量.

    Attributes:
        app_name: 应用名称, 用于拼接默认数据目录.
        database_path: 数据库文件路径, 留空则自动计算.
    """

    app_name: str = 'ipo_know'
    database_path: str | None = None

    @pydantic.computed_field
    @property
    def database_url(self) -> str:
        """统一的 SQLite 连接 URL, 业务代码与 Alembic 共同使用."""
        db_path = self._resolve_db_path()
        db_path_str = str(db_path).replace('\\', '/')
        return f'sqlite:///{db_path_str}'

    def _resolve_db_path(self) -> pathlib.Path:
        """解析数据库文件真实路径, 自动创建父目录."""
        if self.database_path:
            db_path = pathlib.Path(self.database_path)
        else:
            base_dir = app_root() / 'data'
            db_path = base_dir / f'{self.app_name}.db'

        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path


class SSESettings(pydantic.BaseModel):
    """上交所 IPO 披露平台 API 配置.

    支持环境变量覆盖:
        IPO_KNOW_SSE__QUERY_BASE_URL=...
        IPO_KNOW_SSE__STATIC_BASE_URL=...
        IPO_KNOW_SSE__WWW_BASE_URL=...
        IPO_KNOW_SSE__TIMEOUT=20

    Attributes:
        query_base_url: API 数据查询入口,
            SH_XM_LB / GP_COMMON_FILE_SEARCH 等接口地址.
        static_base_url: PDF 等披露文件下载的静态资源 CDN.
        www_base_url: 官网页面 URL, 用于详情页拼接与 Referer 伪装.
        timeout: HTTP 请求默认超时时间, 单位秒.
        config_dir: API yaml 配置文件所在目录, 留空由 client 自动解析.
    """

    query_base_url: str = 'https://query.sse.com.cn'
    static_base_url: str = 'https://static.sse.com.cn'
    www_base_url: str = 'https://www.sse.com.cn'
    timeout: int = 10
    config_dir: str = ''


class VikingKnowledgeSettings(pydantic.BaseModel):
    """火山引擎 VikingDB 知识库客户端配置.

    支持环境变量覆盖 (由顶层 Settings 的 env_prefix 与
    env_nested_delimiter 自动注入):
        IPO_KNOW_VIKING_KNOWLEDGE__HOST=...
        IPO_KNOW_VIKING_KNOWLEDGE__REGION=...
        IPO_KNOW_VIKING_KNOWLEDGE__SCHEME=...
        IPO_KNOW_VIKING_KNOWLEDGE__TIMEOUT=...
        IPO_KNOW_VIKING_KNOWLEDGE__AK=...
        IPO_KNOW_VIKING_KNOWLEDGE__SK=...
        IPO_KNOW_VIKING_KNOWLEDGE__COLLECTION_NAME=...
        IPO_KNOW_VIKING_KNOWLEDGE__PROJECT_NAME=...
        IPO_KNOW_VIKING_KNOWLEDGE__RESOURCE_ID=...
        IPO_KNOW_VIKING_KNOWLEDGE__STRATEGY_RESOURCE_ID=...
        IPO_KNOW_VIKING_KNOWLEDGE__SERVICE_RESOURCE_ID=...
        IPO_KNOW_VIKING_KNOWLEDGE__API_KEY=...

    Attributes:
        host: 知识库服务域名.
        region: 服务地域.
        scheme: 请求协议, http 或 https.
        timeout: 请求超时时间, 单位秒.
        ak: 火山引擎 Access Key, 敏感信息。
        sk: 火山引擎 Secret Key, 敏感信息。
        collection_name: 默认知识库名称, 与 resource_id 二选一.
        project_name: 默认项目名称.
        resource_id: 默认知识库唯一 ID, 与 collection_name 二选一.
        strategy_resource_id: 上传文档使用的切片策略资源 ID,
            留空时不传该参数, 由知识库使用自身默认切片策略.
        service_resource_id: 知识问答使用的服务资源 ID,
            仅知识问答 (service_chat) 场景使用, 留空时不传该参数.
        api_key: 火山方舟 API Key, 仅知识问答 (service_chat)
            使用, 该接口强制 API Key 鉴权, IAM AK/SK 不可用.
    """

    host: str = 'api-knowledgebase.mlp.cn-beijing.volces.com'
    region: str = 'cn-beijing'
    scheme: str = 'https'
    timeout: int = 30
    ak: str = ''
    sk: str = ''
    collection_name: str = ''
    project_name: str = 'default'
    resource_id: str = 'kb-532b499a85fd935a'
    strategy_resource_id: str = ''
    service_resource_id: str = ''
    api_key: str = pydantic.Field(
        default='',
        description='火山方舟 API Key, 仅知识问答 (service_chat) 使用',
    )


class AliyunKnowledgeSettings(pydantic.BaseModel):
    """阿里云百炼知识库客户端配置.

    支持环境变量覆盖 (由顶层 Settings 的 env_prefix 与
    env_nested_delimiter 自动注入):
        IPO_KNOW_ALIYUN_KNOWLEDGE__AK=...
        IPO_KNOW_ALIYUN_KNOWLEDGE__SK=...
        IPO_KNOW_ALIYUN_KNOWLEDGE__ENDPOINT=...
        IPO_KNOW_ALIYUN_KNOWLEDGE__REGION_ID=...
        IPO_KNOW_ALIYUN_KNOWLEDGE__WORKSPACE_ID=...
        IPO_KNOW_ALIYUN_KNOWLEDGE__INDEX_ID=...
        IPO_KNOW_ALIYUN_KNOWLEDGE__CATEGORY_ID=...
        IPO_KNOW_ALIYUN_KNOWLEDGE__PARSER=...
        IPO_KNOW_ALIYUN_KNOWLEDGE__TIMEOUT=...
        IPO_KNOW_ALIYUN_KNOWLEDGE__API_KEY=...
        IPO_KNOW_ALIYUN_KNOWLEDGE__AGENT_ID=...

    Attributes:
        ak: 阿里云 AccessKey ID, 敏感信息。
        sk: 阿里云 AccessKey Secret, 敏感信息。
        endpoint: 百炼 OpenAPI 服务域名.
        region_id: 服务地域.
        workspace_id: 百炼业务空间 ID, 所有接口的必传路径参数.
        index_id: 目标知识库 ID, 即 CreateIndex 返回的 Data.Id.
        category_id: 数据中心分类 ID, 默认 default 系统分类.
        parser: 文档解析器类型, 如 DASHSCOPE_DOCMIND / DOCMIND.
        timeout: 请求超时时间, 单位秒.
        api_key: 百炼 API-Key, 仅知识问答使用, 该接口为
            Bearer 鉴权的独立 REST 链路, AK/SK 不可用.
        agent_id: 知识问答服务应用 ID (aid-xxx), 仅知识问答
            使用, 在百炼控制台知识问答页面创建并发布后获取.
    """

    ak: str = ''
    sk: str = ''
    endpoint: str = 'bailian.cn-beijing.aliyuncs.com'
    region_id: str = 'cn-beijing'
    workspace_id: str = ''
    index_id: str = ''
    category_id: str = 'default'
    parser: str = 'DASHSCOPE_DOCMIND'
    timeout: int = 30
    api_key: str = pydantic.Field(
        default='',
        description='百炼 API-Key, 仅知识问答使用',
    )
    agent_id: str = pydantic.Field(
        default='',
        description='知识问答服务应用 ID(aid-xxx), 仅知识问答使用',
    )


class EastmoneySettings(pydantic.BaseModel):
    """东方财富数据接口配置.

    支持环境变量覆盖:
        IPO_KNOW_EASTMONEY__BASE_URL=...
        IPO_KNOW_EASTMONEY__TIMEOUT=...

    Attributes:
        base_url: 东方财富数据中心 API 域名.
        timeout: HTTP 请求超时时间, 单位秒.
    """

    base_url: str = 'https://datacenter-web.eastmoney.com'
    timeout: int = 10


class BSESettings(pydantic.BaseModel):
    """北交所 IPO 审核信息披露平台配置.

    支持环境变量覆盖:
        IPO_KNOW_BSE__BASE_URL=...
        IPO_KNOW_BSE__TIMEOUT=...

    Attributes:
        base_url: 北交所官网域名.
        timeout: HTTP 请求超时时间, 单位秒.
    """

    base_url: str = 'https://www.bse.cn'
    timeout: int = 10


class SZSESettings(pydantic.BaseModel):
    """深交所注册制审核平台配置.

    支持环境变量覆盖:
        IPO_KNOW_SZSE__BASE_URL=...
        IPO_KNOW_SZSE__TIMEOUT=...

    Attributes:
        base_url: 深交所官网域名.
        timeout: HTTP 请求超时时间, 单位秒.
    """

    base_url: str = 'https://www.szse.cn'
    timeout: int = 15


class Settings(pydantic_settings.BaseSettings):
    """应用全局配置, 基于 pydantic-settings v2.

    **硬性约束: 严禁在 model_config 中设置 extra="ignore".**
    每一个 .env 变量必须在此类中显式声明为 Field, 否则拒载.
    原因: 类型安全、配置即文档、防止拼写错误被静默吞掉.

    加新环境变量的正确方式:
        1. 在此类声明 Field (带类型 + default + description)
        2. 在 .env 填值
        3. 业务代码通过 settings.xxx 使用

    ## AI 助手注意
    此配置类专用于 GUI 持久化存储。
    
    Attributes:
        database: 数据库配置.
        sse: 上交所 API 配置.
        deepseek_api_key: DeepSeek API 密钥.
        viking_knowledge: 火山引擎知识库配置.
        aliyun_knowledge: 阿里云百炼知识库配置.
        eastmoney: 东方财富数据接口配置.
        bse: 北交所 IPO 审核信息披露平台配置.
        szse: 深交所注册制审核平台配置.
    """

    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix='IPO_KNOW_',
        case_sensitive=False,
        env_nested_delimiter='__',
    )

    database: DatabaseConfig = pydantic.Field(
        default_factory=DatabaseConfig,
    )
    sse: SSESettings = pydantic.Field(
        default_factory=SSESettings,
    )
    deepseek_api_key: str = pydantic.Field(
        default='',
        description='DeepSeek API 密钥, 对应环境变量 IPO_KNOW_DEEPSEEK_API_KEY',
    )
    viking_knowledge: VikingKnowledgeSettings = pydantic.Field(
        default_factory=VikingKnowledgeSettings,
    )
    aliyun_knowledge: AliyunKnowledgeSettings = pydantic.Field(
        default_factory=AliyunKnowledgeSettings,
    )
    eastmoney: EastmoneySettings = pydantic.Field(
        default_factory=EastmoneySettings,
    )
    bse: BSESettings = pydantic.Field(
        default_factory=BSESettings,
    )
    szse: SZSESettings = pydantic.Field(
        default_factory=SZSESettings,
    )


settings = Settings()
