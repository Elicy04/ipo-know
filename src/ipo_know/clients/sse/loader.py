"""接口配置加载与校验模块.

提供 Pydantic 配置模型与 ConfigLoader 类, 用于从 YAML 文件加载、
校验并缓存上交所 SOA 接口的请求配置.
"""

from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError


# ==================================================
# 配置结构 Pydantic 校验模型
# ==================================================
class QueryParamConfig(BaseModel):
    """单条查询参数配置."""

    name: str = Field(description='参数名')
    type: str = Field(description='参数类型: string / integer / boolean')
    required: bool = Field(description='是否必填')
    default: Any | None = Field(None, description='默认值, 动态参数禁止设置')
    description: str = Field(description='参数功能说明')
    dynamic: bool = Field(False, description='是否运行时动态生成')


class HeadersConfig(BaseModel):
    """请求头配置."""

    inherit_global: bool = Field(True, description='是否继承全局请求头')
    extra: dict[str, str] = Field(
        default_factory=dict,
        description='接口专属请求头, 可覆盖全局',
    )


class ResponseConfig(BaseModel):
    """响应结构配置."""

    format: str = Field(description='响应格式: json / jsonp')
    data_list_path: str = Field(description='业务数据列表在响应中的 JSON 路径')
    total_field_path: str = Field(description='总条数字段在响应中的 JSON 路径')
    response_model: str = Field(description='响应外壳 Pydantic 模型名称')
    item_model: str = Field(description='单条业务数据 Pydantic 模型名称')
    expected_item_count: int | None = Field(
        None, description='预期返回条数, 详情接口固定为1'
    )
    file_base_url: str | None = Field(
        None, description='文件下载基础域名, 用于拼接完整下载 URL'
    )


class ApiMetaConfig(BaseModel):
    """接口元数据."""

    api_id: str = Field(description='接口唯一标识ID')
    api_name: str = Field(description='接口名称')
    description: str = Field(description='接口功能描述')
    endpoint: str = Field(description='接口相对路径')
    method: str = Field(description='HTTP 请求方法: GET / POST')
    sql_id: str = Field(description='后端 SQL 查询标识')


class ApiConfig(BaseModel):
    """单接口完整配置."""

    api_meta: ApiMetaConfig
    query_params: list[QueryParamConfig]
    headers: HeadersConfig
    response: ResponseConfig


# ==================================================
# 配置加载器主类
# ==================================================
class ConfigLoader:
    """YAML 接口配置加载与校验器.

    从 YAML 文件加载接口配置, 执行 Pydantic 模型校验与自定义业务规则校验,
    并提供按 api_id 检索的缓存机制.
    """

    def __init__(self, config_dir: str | None = None) -> None:
        """初始化配置加载器.

        Args:
            config_dir: 可选, 配置文件目录路径, 指定后自动批量加载.
        """
        self._config_store: dict[str, ApiConfig] = {}
        if config_dir:
            self.load_dir(config_dir)

    def load_file(self, file_path: str) -> ApiConfig:
        """加载单个 YAML 配置文件并执行全量校验.

        Args:
            file_path: YAML 配置文件路径.

        Returns:
            校验通过的 ApiConfig 实例.

        Raises:
            FileNotFoundError: 配置文件不存在时抛出.
            ValueError: 配置结构校验失败或业务规则不通过时抛出.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f'配置文件不存在: {file_path}')

        logger.debug('加载接口配置: {}', path.name)

        with open(path, encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)

        # 基础结构校验
        try:
            validated_config = ApiConfig(**raw_config)
        except ValidationError as e:
            logger.error(
                '配置文件校验失败: {} | 错误: {}',
                path.name, e,
            )
            raise ValueError(f'配置文件 [{file_path}] 结构校验失败: {e}') from e

        # 业务规则额外校验
        self._validate_param_rules(validated_config, file_path)

        # 存入缓存
        self._config_store[validated_config.api_meta.api_id] = validated_config
        logger.info(
            '接口配置加载成功 | api_id={} | {}',
            validated_config.api_meta.api_id,
            validated_config.api_meta.api_name,
        )
        return validated_config

    def load_dir(self, dir_path: str) -> dict[str, ApiConfig]:
        """批量加载目录下所有 .yaml/.yml 配置文件.

        Args:
            dir_path: 配置文件目录路径.

        Returns:
            所有已加载配置的字典副本, key 为 api_id.

        Raises:
            NotADirectoryError: 目录不存在时抛出.
        """
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            raise NotADirectoryError(f'配置目录不存在: {dir_path}')

        logger.info('开始加载接口配置目录: {}', dir_path)

        for yaml_file in dir_path.glob('*.yaml'):
            self.load_file(str(yaml_file))
        for yml_file in dir_path.glob('*.yml'):
            self.load_file(str(yml_file))

        logger.info(
            '接口配置目录加载完成 | 共 {} 个接口',
            len(self._config_store),
        )
        return self._config_store.copy()

    def get_config(self, api_id: str) -> ApiConfig:
        """根据 api_id 获取接口配置.

        Args:
            api_id: 接口唯一标识 ID.

        Returns:
            对应的 ApiConfig 实例.

        Raises:
            KeyError: api_id 不在缓存中时抛出.
        """
        if api_id not in self._config_store:
            raise KeyError(f'未找到接口配置, api_id: {api_id}')
        return self._config_store[api_id]

    @property
    def all_configs(self) -> dict[str, ApiConfig]:
        """获取所有已加载配置的副本."""
        return self._config_store.copy()

    # ------------------------------
    # 内部校验方法
    # ------------------------------
    @staticmethod
    def _validate_param_rules(config: ApiConfig, file_path: str) -> None:
        """自定义业务规则校验.

        Args:
            config: 待校验的接口配置.
            file_path: 配置文件路径, 用于错误信息.

        Raises:
            ValueError: 参数名重复或动态参数设置了默认值时抛出.
        """
        param_names = [p.name for p in config.query_params]

        # 1. 参数名不可重复
        if len(param_names) != len(set(param_names)):
            logger.error(
                '配置文件 [{}] 存在重复的参数名: {}',
                file_path, param_names,
            )
            raise ValueError(f'配置文件 [{file_path}] 存在重复的参数名')

        # 2. 动态参数禁止设置默认值
        for param in config.query_params:
            if param.dynamic and param.default is not None:
                logger.error(
                    '配置文件 [{}] 动态参数 [{}] 设置了禁止的默认值',
                    file_path, param.name,
                )
                raise ValueError(
                    f'配置文件 [{file_path}] 中动态参数 '
                    f'[{param.name}] 禁止设置 default 默认值'
                )
