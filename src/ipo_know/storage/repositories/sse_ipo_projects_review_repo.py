"""上交所 IPO 项目审核表仓储类.

通用 CRUD 全部继承自基类, 仅实现业务特有的定制化查询方法.
"""

import sqlalchemy
from sqlalchemy import orm

from ipo_know.storage.models.sse_ipo_projects_review import SseIpoProjectsReview
from ipo_know.storage.repositories.base_repo import BaseRepository
from ipo_know.storage.session import SessionLocal


class SseIpoProjectsReviewRepo(BaseRepository[SseIpoProjectsReview]):
    """上交所 IPO 项目审核表仓储.

    基础 CRUD (get_by_id/create/update/delete/分页) 全部继承自基类,
    仅需编写业务特有的定制化查询方法.

    单独业务逻辑多表操作（如与 sse_ipo_files 联动）务必使用标准模式,
    由调用方传入同一 db 会话，确保在同一事务中提交或回滚.
    """

    def __init__(self) -> None:
        """初始化, 绑定 SseIpoProjectsReview 模型."""
        super().__init__(model=SseIpoProjectsReview)

    # -------------------- 业务定制查询 --------------------
    # 以下方法使用标准模式 (外部传入 db 会话),
    # 便于调用方组合多表操作在同一事务中.

    def get_by_stock_audit_num(
        self,
        db: orm.Session,
        stock_audit_num: str,
    ) -> SseIpoProjectsReview | None:
        """按审核编号查询项目 (语义别名, 等价于 get_by_id).

        Args:
            db: 数据库会话.
            stock_audit_num: 审核编号 (主键).

        Returns:
            项目对象, 未找到则返回 None.
        """
        return db.get(self.model, stock_audit_num)

    def list_by_curr_status(
        self,
        db: orm.Session,
        curr_status: int,
    ) -> list[SseIpoProjectsReview]:
        """按当前审核状态查询项目列表.

        Args:
            db: 数据库会话.
            curr_status: 当前审核状态码.

        Returns:
            匹配状态的所有项目列表.
        """
        stmt = sqlalchemy.select(self.model).where(
            self.model.curr_status == curr_status,
        )
        return list(db.scalars(stmt).all())

    def auto_get_by_stock_audit_num(
        self,
        stock_audit_num: str,
    ) -> SseIpoProjectsReview | None:
        """便捷版: 自动开会话, 按审核编号查询.

        Args:
            stock_audit_num: 审核编号.

        Returns:
            项目对象, 未找到则返回 None.
        """
        with SessionLocal() as db:
            return self.get_by_stock_audit_num(db, stock_audit_num)


# 全局单例, 直接导入即可使用
sse_ipo_projects_review_repo = SseIpoProjectsReviewRepo()
