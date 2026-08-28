查询用户某个账期内所有商品实例或计费项的消费汇总。

## 接口说明

-   当月数据查询结果仅供参考，不作为对账依据；当月最终账单在次月 3 日 12 点后支持查看/导出（月中会发生包括但不限于以下少数场景：延迟出账，退款，调账，欠费核销等）。
    
-   当月账单数据中不包含未结算（未出账，累账中）的后付费数据。
    
-   支持近 18 个月数据。
    
-   账单数据相对于实际费用消耗延迟 24 小时更新，其中实例 ID 相关的信息（ 实例配置，实例规格，实例昵称，资源组，公网 IP，私网 IP，可用区）延迟 48 小时更新。
    
-   账单数据不支持提供分拆型云产品（例如：CDN、OSS、共享带宽等）各个分拆项（例如：域名、Bucket、EIP 等）的具体费用（如需统计含分拆项数据，请前往分账账单）。
    
-   对于云通信产品，仅支持查询 2020 年 6 月及以后的明细数据，万网产品（包括域名、商标等）仅支持查询 2020 年 11 月及以后的明细数据。
    
-   单用户限流 10 笔/秒，如遇超时，请重试。
    

## 调试

[您可以在OpenAPI Explorer中直接运行该接口，免去您计算签名的困扰。运行成功后，OpenAPI Explorer可以自动生成SDK代码示例。](https://api.aliyun.com/api/BssOpenApi/2017-12-14/DescribeInstanceBill)

 [![](https://img.alicdn.com/tfs/TB16JcyXHr1gK0jSZR0XXbP8XXa-24-26.png) 调试](https://api.aliyun.com/api/BssOpenApi/2017-12-14/DescribeInstanceBill)

## **授权信息**

下表是API对应的授权信息，可以在RAM权限策略语句的`Action`元素中使用，用来给RAM用户或RAM角色授予调用此API的权限。具体说明如下：

-   操作：是指具体的权限点。
    
-   访问级别：是指每个操作的访问级别，取值为写入（Write）、读取（Read）或列出（List）。
    
-   资源类型：是指操作中支持授权的资源类型。具体说明如下：
    
    -   对于必选的资源类型，用前面加 \* 表示。
        
    -   对于不支持资源级授权的操作，用`全部资源`表示。
        
-   条件关键字：是指云产品自身定义的条件关键字。
    
-   关联操作：是指成功执行操作所需要的其他权限。操作者必须同时具备关联操作的权限，操作才能成功。
    

| **操作** | **访问级别** | **资源类型** | **条件关键字** | **关联操作** |
| --- | --- | --- | --- | --- |
| bssapi:DescribeInstanceBill | get | \\*全部资源 `*` | bssapi:ProductCode bssapi:ProductCode bssapi:ProductType bssapi:ProductType | 无   |

## 请求参数

| **名称** | **类型** | **必填** | **描述** | **示例值** |
| --- | --- | --- | --- | --- |
| BillingCycle | string | 是   | 账期 YYYY－MM。仅支持最近 18 个月账期。 | 2020-03 |
| ProductCode | string | 否   | 产品代码。 | rds |
| ProductType | string | 否   | 产品类型。 | rds |
| SubscriptionType | string | 否   | 订阅类型。取值： - Subscription：预付费。 - PayAsYouGo：后付费。 | PayAsYouGo |
| IsBillingItem | boolean | 否   | 是否按照计费项维度拉取数据。 - false（默认值）：与费用与成本-费用账单-账单明细-实例账单一致。 - true：与费用与成本-费用账单-账单明细-计费项账单一致。 | false |
| NextToken | string | 否   | 用来表示当前调用开始读取的位置，参数值必须为空或者使用返回结果中的 NextToken 设值，否则会报错。空代表从头开始读取。 | CAESEgoQCg4KCm |
| MaxResults | integer | 否   | 本次读取的最大数据记录数量。默认值：20，最大值：300。 | 20  |
| IsHideZeroCharge | boolean | 否   | 根据原价（PretaxGrossAmount）和应付（PretaxAmount）是否都为 0 做过滤。取值： - false。 - true。 | false |
| BillingDate | string | 否   | 账单日期，仅当 Granularity 为 DAILY 时必填，格式为 YYYY-MM-DD。 **说明** BillingDate 参数值需和 BillingCycle 参数月份保持一致，例如 BillingCycle 设置为 2020-03，BillingDate 需设置为 2020-03-DD。若月份设置不一致，查询的结果按 BillingCycle 设置的时间返回。 | 2020-03-02 |
| Granularity | string | 否   | 查询账单的颗粒度。取值如下： - MONTHLY：月。与费用与成本-费用账单-账单明细-账期账单一致。 - DAILY：日。与费用与成本-费用账单-账单明细-按天账单一致。 **说明** 选择 DAILY 需指定 BillingDate。 | MONTHLY |
| BillOwnerId | integer | 否   | 资源归属账号 ID，资源归属账号是实际使用资源的账号。 | 122 |
| InstanceID | string | 否   | 实例 ID。 | abc |
| PipCode | string | 否   | 产品 Code，与费用中心账单产品 Code 一致。 | rds |

## **返回参数**

| **名称** | **类型** | **描述** | **示例值** |
| --- | --- | --- | --- |
|     | object |     |     |
| Code | string | 状态码。 | Success |
| Message | string | 错误信息。 | Successful! |
| RequestId | string | 请求 ID。 | 79EE7556-0CFD-44EB-9CD6-B3B526E3A85F |
| Success | boolean | 是否成功。 | true |
| Data | object | 返回数据。 |     |
| NextToken | string | 用来表示当前调用返回读取到的位置，空代表数据已经读取完毕。下次调用时，需要将此设置到入参 NextToken 中。 | CAESEgoQCg4KCm |
| BillingCycle | string | 账单日期，格式：YYYY－MM。 | 2020-03 |
| MaxResults | integer | 本次请求所返回的最大记录条数。 | 20  |
| AccountID | string | 账号 ID。 | 122 |
| TotalCount | integer | 总记录数。 | 20  |
| AccountName | string | 用户账号。 | test@test.aliyunid.com |
| Items | array<object> | 账单详情。 |     |
|     | object |     |     |
| BillingDate | string | 账单日期，仅当 Granularity 为 DAILY 时有值，格式为 YYYY-MM-DD。 | 2020-03-20 |
| InstanceConfig | string | 实例详细配置。 | CPU：12 |
| InternetIP | string | 公网 IP。 | 34.xx.x.x |
| Item | string | 账单类型： - SubscriptionOrder （预付订单）。 - PayAsYouGoBill （后付账单）。 - Refund （退款）。 - Adjustment （调账）。 | PayAsYouGoBill |
| Tag | string | 资源标签。 | key:testKey value:testValue; key:testKey1 value:testValues1 |
| InstanceID | string | 实例 ID。 | i-dadada |
| Currency | string | 币种，取值： - CNY。 - USD。 - JPY。 | CNY |
| BillAccountName | string | 账单所属账号名称。 | test@test.aliyunid.com |
| DeductedByCashCoupons | number | 代金券抵扣。 | 0.1 |
| SubscriptionType | string | 订阅类型，取值： - Subscription：预付费。 - PayAsYouGo：后付费。 | PayAsYouGo |
| BizType | string | 业务类型。 | trusteeship |
| InstanceSpec | string | 实例规格。 | ecs.sn1ne.3xlarge |
| DeductedByCoupons | number | 优惠券优惠金额。 | 0.1 |
| BillingItem | string | 计费项。仅当 IsBillingItem=true 有值。 | 带宽  |
| BillingItemCode | string | 计费项代码。 | disk |
| Region | string | 地域。 | 杭州  |
| OutstandingAmount | number | 未结清金额。 | 0.1 |
| CostUnit | string | 财务单元。 | 未分配 |
| ListPriceUnit | string | 单价单位, 仅当 isBillingItem 为 true 时有效。 | 元   |
| ResourceGroup | string | 资源组。 | 默认资源组 |
| PipCode | string | 产品 Code，与费用中心账单产品 Code 一致。 | rds |
| ServicePeriodUnit | string | 服务时长单位。 | 秒   |
| PretaxAmount | number | 应付金额。 | 0.1 |
| CommodityCode | string | 商品 Code，与费用中心产品明细 Code 一致。 | rds |
| ProductName | string | 产品名称。 | 云数据库RDS |
| AdjustAmount | number | 信用额度退款抵扣。 | 0   |
| NickName | string | 实例昵称。 | test |
| ProductDetail | string | 产品明细。 | 云数据库RDS |
| Usage | string | 用量。 **说明** 仅当 isBillingItem 为 true 时有效。用量数据为该周期内所有账单的用量总和并非客户的实际购买量。如使用了 1G 的存储，每小时出账，则每小时用量为 1G，按天汇总的账单用量为 1G\\*24=24G。 | 100 |
| IntranetIP | string | 内网 IP。 | 192.xx.xx.xx |
| OwnerID | string | 资源 Owner 账号 AccountID（多账号代付场景）。 | 123 |
| DeductedByPrepaidCard | number | 储值卡抵扣。 | 0.1 |
| UsageUnit | string | 用量单位, 仅当 isBillingItem 为 true 时有效。 | GB  |
| BillAccountID | string | 账单所属账号 ID。 | 122 |
| PaymentAmount | number | 现金支付（含信用额度退款抵扣）。 | 0.1 |
| InvoiceDiscount | number | 优惠金额。 | 0.1 |
| DeductedByResourcePackage | string | 资源包抵扣, 仅当 isBillingItem 为 true 时有效。 | 0.1 |
| ProductType | string | 产品类型。 | rds |
| ServicePeriod | string | 服务时长。 | 3600 |
| Zone | string | 可用区。 | 杭州1 |
| ListPrice | string | 单价, 仅当 isBillingItem 为 true 时有效。 | 100 |
| PretaxGrossAmount | number | 原始金额。 | 0.1 |
| CashAmount | number | 现金支付（不包含信用额度退款抵扣）。 | 0   |
| ProductCode | string | 产品代码。 | rds |
| BillingType | string | 计费方式。 | 其它  |
| ItemName | string | 项目名称。 | iZ28bycvyb4Z |
| AfterDiscountAmount | number | 优惠后金额（包含券抵扣的应付金额数据。计算规则为：优惠后金额=官网目录价-优惠金额） |     |

## 示例

正常返回示例

`JSON`格式

```
{
  "Code": "Success",
  "Message": "Successful!",
  "RequestId": "79EE7556-0CFD-44EB-9CD6-B3B526E3A85F",
  "Success": true,
  "Data": {
    "NextToken": "CAESEgoQCg4KCm",
    "BillingCycle": "2020-03",
    "MaxResults": 20,
    "AccountID": "122",
    "TotalCount": 20,
    "AccountName": "test@test.aliyunid.com",
    "Items": [
      {
        "BillingDate": "2020-03-20",
        "InstanceConfig": "CPU：12",
        "InternetIP": "34.xx.x.x\t",
        "Item": "PayAsYouGoBill",
        "Tag": "key:testKey value:testValue; key:testKey1 value:testValues1",
        "InstanceID": "i-dadada",
        "Currency": "CNY",
        "BillAccountName": "test@test.aliyunid.com",
        "DeductedByCashCoupons": 0.1,
        "SubscriptionType": "PayAsYouGo",
        "BizType": "trusteeship",
        "InstanceSpec": "ecs.sn1ne.3xlarge\t",
        "DeductedByCoupons": 0.1,
        "BillingItem": "带宽",
        "BillingItemCode": "disk",
        "Region": "杭州",
        "OutstandingAmount": 0.1,
        "CostUnit": "未分配\t",
        "ListPriceUnit": "元",
        "ResourceGroup": "默认资源组\t",
        "PipCode": "rds",
        "ServicePeriodUnit": "秒",
        "PretaxAmount": 0.1,
        "CommodityCode": "rds",
        "ProductName": "云数据库RDS\t",
        "AdjustAmount": 0,
        "NickName": "test",
        "ProductDetail": "云数据库RDS\t",
        "Usage": "100",
        "IntranetIP": "192.xx.xx.xx",
        "OwnerID": "123",
        "DeductedByPrepaidCard": 0.1,
        "UsageUnit": "GB",
        "BillAccountID": "122",
        "PaymentAmount": 0.1,
        "InvoiceDiscount": 0.1,
        "DeductedByResourcePackage": "0.1",
        "ProductType": "rds",
        "ServicePeriod": "3600",
        "Zone": "杭州1",
        "ListPrice": "100",
        "PretaxGrossAmount": 0.1,
        "CashAmount": 0,
        "ProductCode": "rds",
        "BillingType": "其它",
        "ItemName": "iZ28bycvyb4Z",
        "AfterDiscountAmount": 0
      }
    ]
  }
}
```

## 错误码

访问[错误中心](https://api.aliyun.com/document/BssOpenApi/2017-12-14/errorCode)查看更多错误码。

## **变更历史**

更多信息，参考[变更详情](https://api.aliyun.com/document/BssOpenApi/2017-12-14/DescribeInstanceBill#workbench-doc-change-demo)。