"""通用仓储基类模块.

封装所有表通用的 CRUD 逻辑与会话管理,
子类仅需继承并传入 ORM 模型即可复用全部增删改查能力.
"""

from typing import Any
from typing import Generic
from typing import TypeVar

import sqlalchemy
from sqlalchemy import orm

from ipo_know.storage.session import SessionLocal


# 泛型参数: ORM 模型类型
ModelType = TypeVar('ModelType')


class BaseRepository(Generic[ModelType]):
    """通用 CRUD 仓储基类.

    提供两种调用模式:
    1. 标准模式: 方法接收外部传入的 db 会话.
       多表事务操作必须使用此模式, 由调用方统一管理会话生命周期,
       确保所有表操作在同一事务中提交或回滚.
    2. 便捷模式: auto_ 开头的方法, 内部自开自管会话与事务.
       仅适用于单表单步的独立操作, 严禁在多表联动场景下使用,
       否则各操作分属不同事务, 无法保证原子性.
    """

    def __init__(self, model: type[ModelType]) -> None:
        """初始化仓储, 绑定对应的 ORM 模型.

        Args:
            model: SQLAlchemy ORM 模型类.
        """
        self.model = model

    # ===================== 标准模式: 外部传入会话 =====================
    # 多表操作必须使用此模式, 由调用方统一管理 db 会话生命周期,
    # 保证所有操作在同一事务中, 避免跨表数据不一致.

    def get_by_id(
        self,
        db: orm.Session,
        obj_id: Any,  # noqa: ANN401  # 泛型基类, 主键类型由子模型决定
    ) -> ModelType | None:
        """按主键查询.

        Args:
            db: 数据库会话.
            obj_id: 主键值 (自动适配模型的主键字段名).

        Returns:
            查询到的模型对象, 未找到则返回 None.
        """
        return db.get(self.model, obj_id)

    def list_page(
        self,
        db: orm.Session,
        skip: int = 0,
        limit: int = 20,
        order_by: Any = None,  # noqa: ANN401  # 泛型基类, 排序列类型由子模型决定
    ) -> list[ModelType]:
        """分页查询.

        Args:
            db: 数据库会话.
            skip: 跳过条数, 默认 0.
            limit: 返回条数上限, 默认 20.
            order_by: 排序表达式 (ORM 列), 默认不排序.

        Returns:
            当前页的 ORM 对象列表.
        """
        stmt = sqlalchemy.select(self.model).offset(skip).limit(limit)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        return list(db.scalars(stmt).all())

    def create(
        self,
        db: orm.Session,
        obj_in: dict | ModelType,
    ) -> ModelType:
        """新增单条数据.

        Args:
            db: 数据库会话.
            obj_in: 字典 (字段映射) 或已构造的 ORM 对象.

        Returns:
            已刷新 (含数据库生成值) 的 ORM 对象.
        """
        db_obj = (
            self.model(**obj_in) if isinstance(obj_in, dict) else obj_in
        )
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def create_bulk(
        self,
        db: orm.Session,
        obj_list: list[dict | ModelType],
    ) -> None:
        """批量新增.

        Args:
            db: 数据库会话.
            obj_list: 字典或 ORM 对象列表.
        """
        orm_list = [
            self.model(**item) if isinstance(item, dict) else item
            for item in obj_list
        ]
        db.add_all(orm_list)
        db.flush()

    def update(
        self,
        db: orm.Session,
        db_obj: ModelType,
        update_data: dict,
    ) -> ModelType:
        """更新对象, 仅修改传入的字段.

        Args:
            db: 数据库会话.
            db_obj: 待更新的 ORM 对象.
            update_data: 字段名到新值的映射.

        Returns:
            已刷新的 ORM 对象.
        """
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def delete(
        self,
        db: orm.Session,
        obj_id: Any,  # noqa: ANN401  # 泛型基类, 主键类型由子模型决定
    ) -> bool:
        """按主键删除.

        Args:
            db: 数据库会话.
            obj_id: 主键值.

        Returns:
            True 表示删除成功, False 表示记录不存在.
        """
        db_obj = db.get(self.model, obj_id)
        if not db_obj:
            return False
        db.delete(db_obj)
        db.flush()
        return True

    # ===================== 便捷模式: 自动管理会话 =====================
    # 仅限单表单步独立操作使用.
    # 多表联动场景务必使用上方标准模式, 由调用方传入同一 db 会话.

    def auto_get_by_id(
        self,
        obj_id: Any,  # noqa: ANN401  # 泛型基类, 主键类型由子模型决定
    ) -> ModelType | None:
        """自动开会话, 按主键查询."""
        with SessionLocal() as db:
            return self.get_by_id(db, obj_id)

    def auto_create(self, obj_in: dict | ModelType) -> ModelType:
        """自动开会话新增, 内置事务提交与异常回滚.

        Args:
            obj_in: 字典或 ORM 对象.

        Returns:
            已持久化的 ORM 对象.

        Raises:
            Exception: 数据库操作失败时抛出, 事务已回滚.
        """
        with SessionLocal() as db:
            try:
                result = self.create(db, obj_in)
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise

    def auto_update_by_id(
        self,
        obj_id: Any,  # noqa: ANN401  # 泛型基类, 主键类型由子模型决定
        update_data: dict,
    ) -> ModelType | None:
        """自动开会话, 按主键更新.

        Args:
            obj_id: 主键值.
            update_data: 字段名到新值的映射.

        Returns:
            更新后的对象, 记录不存在则返回 None.
        """
        with SessionLocal() as db:
            try:
                db_obj = self.get_by_id(db, obj_id)
                if not db_obj:
                    return None
                result = self.update(db, db_obj, update_data)
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise

    def auto_delete(
        self,
        obj_id: Any,  # noqa: ANN401  # 泛型基类, 主键类型由子模型决定
    ) -> bool:
        """自动开会话, 按主键删除.

        Args:
            obj_id: 主键值.

        Returns:
            True 表示删除成功, False 表示记录不存在.
        """
        with SessionLocal() as db:
            try:
                result = self.delete(db, obj_id)
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise
