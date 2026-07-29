# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, event
from alembic import context

# 1. 导入统一配置与模型元数据
from ipo_know.config.config import settings
from ipo_know.storage import Base

# 2. 初始化配置，统一注入真实数据库URL（唯一真值源）
config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

# 加载日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：生成纯SQL脚本，不连接数据库"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：直接连接数据库执行迁移"""
    # 独立创建迁移专用引擎，与业务引擎隔离
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # 对齐业务代码的SQLite兼容参数
        connect_args={"check_same_thread": False},
    )

    # SQLite 连接级配置：开启外键约束
    @event.listens_for(connectable, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
