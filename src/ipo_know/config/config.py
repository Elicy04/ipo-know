"""从环境变量和默认值加载的应用配置.

基于 pydantic-settings v2 实现类型安全的配置管理.
提供单例实例供项目各处直接导入使用.
"""

import os
import pathlib

import pydantic
import pydantic_settings


class DatabaseConfig(pydantic.BaseModel):
    """数据库配置.

    管理 SQLite 数据库路径解析与连接 URL 生成.
    由顶层 Settings 通过 env_nested_delimiter 注入环境变量.

    Attributes:
        app_name: 应用名称, 用于拼接默认数据目录.
        database_path: 数据库文件路径, 留空则自动计算.
    """

    app_name: str = "ipo_know"
    database_path: str | None = None

    @pydantic.computed_field
    @property
    def database_url(self) -> str:
        """统一的 SQLite 连接 URL, 业务代码与 Alembic 共同使用."""
        db_path = self._resolve_db_path()
        db_path_str = str(db_path).replace("\\", "/")
        return f"sqlite:///{db_path_str}"

    def _resolve_db_path(self) -> pathlib.Path:
        """解析数据库文件真实路径, 自动创建父目录."""
        if self.database_path:
            db_path = pathlib.Path(self.database_path)
        else:
            app_data_root = os.getenv("LOCALAPPDATA")
            if app_data_root:
                base_dir = pathlib.Path(app_data_root) / self.app_name
            else:
                base_dir = pathlib.Path.home() / f".{self.app_name}"
            db_path = base_dir / "database" / f"{self.app_name}.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path


class Settings(pydantic_settings.BaseSettings):
    """应用全局配置, 基于 pydantic-settings v2.

    数据库配置嵌套在 database 字段中,
    通过 env_nested_delimiter 路由环境变量.

    Attributes:
        database: 数据库配置.
    """

    model_config = pydantic_settings.SettingsConfigDict(
        env_file=".env",
        env_prefix="IPO_KNOW_",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    database: DatabaseConfig = pydantic.Field(
        default_factory=DatabaseConfig,
    )


settings = Settings()
