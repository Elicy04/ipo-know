"""Session 模块, 负责管理 SQLAlchemy 数据库连接与会话工厂.

提供数据库引擎和会话工厂的初始化配置.
"""

import sqlalchemy
from sqlalchemy import orm

from ipo_know.config import config


engine = sqlalchemy.create_engine(
    config.settings.database.database_url,
    connect_args={"check_same_thread": False},
)

SessionLocal = orm.sessionmaker(
    autocommit=False, autoflush=False, bind=engine,
)
