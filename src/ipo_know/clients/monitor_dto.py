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


@dataclass(frozen=True)
class InstanceBillItem:
    """实例级消费账单条目 (DescribeInstanceBill).

    对应阿里云费用中心产品/实例粒度的消费账单, 与账户资金
    流水 (BillDetailItem) 互补: 前者见消费构成, 后者见充值/退款.
    金额字段统一为 float (None 安全, 缺省 0.0), 其余为 str.

    Attributes:
        billing_cycle: 账期, 格式 'YYYY-MM'.
        billing_date: 账单日, 格式 'YYYY-MM-DD';
            MONTHLY 粒度时为空串.
        product_name: 产品名称 (如「大模型服务平台百炼」).
        product_detail: 产品明细 (计费模块/商品描述).
        instance_id: 实例 ID.
        instance_spec: 实例规格/配置.
        billing_item: 计费项 (仅 IsBillingItem=true 时有值).
        item_type: 账单类型原始枚举 (SubscriptionOrder/
            PayAsYouGoBill/Refund/Adjustment 等).
        subscription_type: 订阅类型原始枚举 (Subscription/
            PayAsYouGo).
        pretax_amount: 应付金额.
        pretax_gross_amount: 原价 (目录价总额).
        invoice_discount: 优惠金额.
        payment_amount: 现金支付金额.
        deducted_by_cash_coupons: 代金券抵扣金额.
        deducted_by_prepaid_card: 储值卡抵扣金额.
        currency: 币种 (CNY 等).
        usage: 用量 (仅 IsBillingItem=true 时有值).
        usage_unit: 用量单位.
    """

    billing_cycle: str
    billing_date: str
    product_name: str
    product_detail: str
    instance_id: str
    instance_spec: str
    billing_item: str
    item_type: str
    subscription_type: str
    pretax_amount: float
    pretax_gross_amount: float
    invoice_discount: float
    payment_amount: float
    deducted_by_cash_coupons: float
    deducted_by_prepaid_card: float
    currency: str
    usage: float
    usage_unit: str
