"""Session 模块, 负责管理 SQLAlchemy 数据库连接与会话工厂.

提供数据库引擎和会话工厂的初始化配置, 包括 SQLite 外键约束启用.
"""

import sqlite3

import sqlalchemy
from sqlalchemy import event
from sqlalchemy import orm

from ipo_know.config import config


engine = sqlalchemy.create_engine(
    config.settings.database.database_url,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_conn: sqlite3.Connection,
    connection_record: object,
) -> None:
    """启用 SQLite 外键约束支持."""
    del connection_record  # 由 SQLAlchemy 事件系统传入, 本函数未使用.
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.close()


SessionLocal = orm.sessionmaker(
    autocommit=False, autoflush=False, bind=engine,
)
