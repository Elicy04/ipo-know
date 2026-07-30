"""上交所 IPO 文件表仓储类.

通用 CRUD 全部继承自基类, 仅实现业务特有的定制化查询方法.
"""

import sqlalchemy
from sqlalchemy import orm

from ipo_know.storage.models.sse_ipo_files import SseIpoFiles
from ipo_know.storage.repositories.base_repo import BaseRepository
from ipo_know.storage.session import SessionLocal


class SseIpoFilesRepo(BaseRepository[SseIpoFiles]):
    """上交所 IPO 文件表仓储.

    基础 CRUD (get_by_id/create/update/delete/分页) 全部继承自基类,
    仅需编写业务特有的定制化查询方法.

    单独业务逻辑多表操作（如与 sse_ipo_projects_review 联动）务必使用标准模式,
    由调用方传入同一 db 会话，确保在同一事务中提交或回滚.
    """

    def __init__(self) -> None:
        """初始化, 绑定 SseIpoFiles 模型."""
        super().__init__(model=SseIpoFiles)

    # -------------------- 业务定制查询 --------------------
    # 以下方法使用标准模式 (外部传入 db 会话),
    # 便于调用方组合多表操作在同一事务中.

    def list_by_audit_id(
        self,
        db: orm.Session,
        audit_id: str,
    ) -> list[SseIpoFiles]:
        """按审核编号查询所有关联文件.

        Args:
            db: 数据库会话.
            audit_id: 审核编号,
                逻辑外键 → sse_ipo_projects_review.stock_audit_num.

        Returns:
            该审核编号下的所有文件列表.
        """
        stmt = sqlalchemy.select(self.model).where(
            self.model.audit_id == audit_id,
        )
        return list(db.scalars(stmt).all())

    def auto_list_by_audit_id(
        self,
        audit_id: str,
    ) -> list[SseIpoFiles]:
        """便捷版: 自动开会话, 按审核编号查询.

        Args:
            audit_id: 审核编号.

        Returns:
            该审核编号下的所有文件列表.
        """
        with SessionLocal() as db:
            return self.list_by_audit_id(db, audit_id)


# 全局单例, 直接导入即可使用
sse_ipo_files_repo = SseIpoFilesRepo()
