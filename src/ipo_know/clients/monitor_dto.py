"""监控数据传输对象.

统一阿里云与火山引擎两个平台的账户余额、知识库监控摘要、
账单明细等数据结构, 供监控面板展示使用.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class BalanceInfo:
    """账户余额信息.

    Attributes:
        platform: 来源平台标识.
        available_amount: 可用额度.
        cash_amount: 现金余额.
        credit_amount: 信控额度/欠费金额.
        currency: 币种 (CNY/USD 等).
    """

    platform: Literal['aliyun', 'volc']
    available_amount: str
    cash_amount: str
    credit_amount: str
    currency: str


@dataclass(frozen=True)
class KbMonitorSummary:
    """知识库监控摘要.

    Attributes:
        platform: 来源平台标识.
        kb_type: 知识库规格 (标准版/旗舰版).
        storage_limit_gb: 存储限额 GB (火山可能无此字段, 填 0.0).
        storage_usage_gb: 已用存储 GB.
        doc_num: 文档数.
        point_num: 切片数 (火山有, 阿里云可能无).
        create_time: 创建时间.
        update_time: 更新时间.
    """

    platform: Literal['aliyun', 'volc']
    kb_type: str
    storage_limit_gb: float
    storage_usage_gb: float
    doc_num: int | None
    point_num: int | None
    create_time: str | None
    update_time: str | None


@dataclass(frozen=True)
class BillDetailItem:
    """账单明细条目（基础摘要）.

    Attributes:
        record_id: 记录 ID.
        date: 账单日期.
        product: 产品名称.
        amount: 扣费金额.
        payment_method: 付款方式.
        remark: 备注/说明.
    """

    record_id: str
    date: str
    product: str
    amount: str
    payment_method: str
    remark: str
