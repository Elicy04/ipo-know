"""上交所 IPO 项目审核表 ORM 模型."""

from sqlalchemy import Float
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from ipo_know.storage.models.base_model import Base


class SseIpoProjectsReview(Base):
    """上交所 IPO 项目审核表.

    存储上交所查询接口返回的 IPO 项目审核信息，不含中介机构（intermediary）
    和发行人（stockIssuer）数据。
    """

    __tablename__ = "sse_ipo_projects_review"

    # 主键：审核编号（如 "2160"），来自接口 stockAuditNum 字段
    stock_audit_num: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        comment="审核编号，主键",
    )

    # 审核名称 / 公司全称
    stock_audit_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="审核名称（公司全称）",
    )

    # 项目类型，0=IPO
    project_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="项目类型（0=IPO）",
    )

    # 当前审核状态
    curr_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="当前审核状态",
    )

    # 注册结果，1=通过，null=暂无
    registe_result: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="注册结果（1=通过，null=暂无）",
    )

    # 募集类型
    collect_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="募集类型",
    )

    # 发行市场类型，2=科创板
    issue_market_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="发行市场类型（2=科创板）",
    )

    # 计划发行资本，单位：亿元；接口返回浮点数，实际精度有限
    plan_issue_capital: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="计划发行资本（亿元）",
    )

    # 发行金额，接口返回为字符串（含空字符串），保留原始值
    issue_amount: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
        comment="发行金额",
    )

    # 中止状态
    suspend_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
        comment="中止状态",
    )

    # 文号
    wen_hao: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
        comment="文号",
    )

    # 提交结果
    commiti_result: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
        comment="提交结果",
    )

    # 统一社会信用代码
    uniform_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
        comment="统一社会信用代码",
    )

    # 更新日期，格式 YYYYMMDDHHMMSS，保留原始字符串以匹配接口数据
    update_date: Mapped[str] = mapped_column(
        String(14),
        nullable=False,
        default="",
        comment="更新日期（格式 YYYYMMDDHHMMSS）",
    )

    # 创建时间
    create_time: Mapped[str] = mapped_column(
        String(14),
        nullable=False,
        default="",
        comment="创建时间（格式 YYYYMMDDHHMMSS）",
    )

    # 审核申请日期
    audit_apply_date: Mapped[str] = mapped_column(
        String(14),
        nullable=False,
        default="",
        comment="审核申请日期（格式 YYYYMMDDHHMMSS）",
    )

    # 操作序列号，接口返回的哈希值，用于幂等校验
    operation_seq: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="操作序列号（接口返回的哈希值）",
    )

    __table_args__ = (
        Index("ix_sse_ipo_projects_review_curr_status", "curr_status"),
        Index("ix_sse_ipo_projects_review_project_type", "project_type"),
        Index(
            "ix_sse_ipo_projects_review_issue_market_type",
            "issue_market_type",
        ),
    )
