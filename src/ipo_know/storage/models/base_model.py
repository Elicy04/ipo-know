"""ORM 模型基类模块.

提供 SQLAlchemy ORM 的声明式基类 Base, 所有数据表模型均继承自该类.
"""

from sqlalchemy import orm


class Base(orm.DeclarativeBase):
    """ORM 模型基类."""
