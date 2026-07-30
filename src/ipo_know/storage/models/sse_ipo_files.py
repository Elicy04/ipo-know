"""上交所 IPO 项目文件表 ORM 模型."""

from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from ipo_know.storage.models.base_model import Base


class SseIpoFiles(Base):
    """上交所 IPO 项目文件表.

    存储上交所查询接口返回的 IPO 项目关联文件信息。
    audit_id 为逻辑外键，关联 sse_ipo_projects_review.stock_audit_num，
    不建立物理外键约束（SQLite 环境下外键默认关闭，且逻辑外键更灵活）。
    """

    __tablename__ = "sse_ipo_files"

    # 主键：文件ID，接口返回两种格式：
    #   纯数字（如 "493941"）或哈希（如 "c8f0e6..."）
    file_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="文件ID，主键",
    )

    # 逻辑外键：审核编号 → sse_ipo_projects_review.stock_audit_num
    # 不设置 ForeignKey，仅在应用层维护引用关系
    audit_id: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="审核编号，逻辑外键 → sse_ipo_projects_review.stock_audit_num",
    )

    # 文件名（如 "002160_20260709_WVTN.pdf"）
    file_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="文件名",
    )

    # 文件标题，内容为中文描述（如 "关于同意...注册的批复"）
    file_title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="文件标题",
    )

    # 文件路径，相对于静态资源根路径
    # （如 "/disclosure/announcement/c/202607/..."）
    # 使用时需在应用层拼接完整 URL
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="文件相对路径，需在应用层拼接完整 URL",
    )

    # 文件类型编码
    file_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="文件类型",
    )

    # 文件类型映射编码（如 "I1010"、"I0033"），用于分类与筛选
    file_type_map: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="文件类型映射编码",
    )

    # 文件版本，接口可能返回 null，表示无版本信息
    file_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="文件版本",
    )

    # 文件大小，单位：字节
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="文件大小（字节）",
    )

    # 文件更新时间，格式 YYYYMMDDHHMMSS
    file_upd_time: Mapped[str] = mapped_column(
        String(14),
        nullable=False,
        comment="文件更新时间（格式 YYYYMMDDHHMMSS）",
    )

    # 市场类型
    market_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="市场类型",
    )

    # 是否预览文件，接口返回空字符串为主，仅做标记预留
    is_preview_file: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="",
        comment="是否预览文件",
    )

    # 冗余字段：公司全称，与主表 stock_audit_name 对应，方便文件表独立查询
    company_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="公司全称（冗余字段）",
    )

    # 冗余字段：公司简称
    company_abbr: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="公司简称（冗余字段）",
    )

    # 公司代码，接口中可能为空字符串
    company_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="",
        comment="公司代码",
    )

    __table_args__ = (
        Index("ix_sse_ipo_files_audit_id", "audit_id"),
        Index("ix_sse_ipo_files_file_type", "file_type"),
    )
