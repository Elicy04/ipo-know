提供包含用量、价格、优惠折扣、计费规则等的计费明细信息；请于每月第2个自然日12点后获取上月完整账单数据；

<span id=".5rOo5oSP5LqL6aG5"></span>
## 注意事项


1. 查询QPS限制为5QPS，超过限流将报错；


<span id=".6LCD6K-V"></span>
## 调试

[去调试](https://api.volcengine.com/api-explorer/?action=ListBillDetail&groupName=%E8%B4%A6%E5%8D%95%E4%B8%AD%E5%BF%83&serviceCode=billing&version=2022-01-01)


<span id=".6K-35rGC5Y-C5pWw"></span>
## 请求参数

下表仅列出该接口特有的请求参数和部分公共参数。更多信息请见[公共参数](https://www.volcengine.com/docs/6369/67268)。

<div data-tips="true" data-tips-type="warning" data-tips-is-title="true">注意</div>


<div data-tips="true" data-tips-type="warning">为了提升查询效率和成功率，您可使用账单日期"ExpenseDate"指定获取某日数据、或使用统计周期"GroupPeriod"获取按日/按月聚合口径数据；</div>




**Action** <span data-label="purple">string</span> <span data-api-tag="require|DjUl2h">必选</span> `示例值：ListBillDetail`

要执行的操作，取值：ListBillDetail。



**Version** <span data-label="purple">string</span> <span data-api-tag="require|yJOUtR">必选</span> `示例值：2022-01-01`

API的版本，取值：2022\-01\-01。



**PayerID** <span data-label="purple">long[]</span> `可选` `示例值：[2100057673]`

Payer账号ID



**OwnerID** <span data-label="purple">long[]</span> `可选` `示例值：[2100057673]`

Owner账号ID



**Project** <span data-label="purple">string[]</span> `可选` `示例值：["project1","project2"]`

项目筛选，目前只支持计费项明细维度生效，其他维度默认不生效。



**Product** <span data-label="purple">string[]</span> `可选` `示例值：[ECS]`

产品名称，默认不选为全部



**BillingMode** <span data-label="purple">string[]</span> `可选` `示例值：[1]`

计费模式：1：包年包月，代表预付费；2：按量计费，代表后付费；3：合同计费，代表线下计费；4：履约计费；默认不选为全部；



**BillCategory** <span data-label="purple">string[]</span> `可选` `示例值：[consume-use]`

账单类型：consume\-use：消费\-使用；consume\-new：消费\-新购；consume\-renew：消费\-续费；consume\-formalize：消费\-转正；consume\-modify：消费\-更配；consume\-trial：消费\-试用；refund\-terminate：退款\-退订；refund\-modify：退款\-更配；transfer\-manual：调账\-人工；transfer\-system：调账\-系统；默认不选为全部



**Offset** <span data-label="purple">integer</span> `可选` `示例值：10`

用于在分页查询中指定“从结果集的第几条记录开始返回”（也就是先跳过多少条记录），通常与 **limit** 搭配使用实现翻页：例如每页 `limit=300` 时，第 1 页传 `offset=0` 获取第 1–300 条，第 2 页传 `offset=300` 获取第 301–600 条，第 3 页传 `offset=600` 获取第 601–900 条；因此每往后一页，`offset` 按固定步长累加：`offset = offset + limit`（等价于 `offset = (page-1) * limit`）。



**Limit** <span data-label="purple">integer</span> <span data-api-tag="require|Uersjj">必选</span> `示例值：10`

数量：[1\-300]，用于指定接口响应中返回记录的最大数量（上限），例如Limit=20表示每次请求最多返回20条



**BillPeriod** <span data-label="purple">string</span> <span data-api-tag="require|zF2MTu">必选</span> `示例值：2023-08`

账期：格式为YYYY\-MM；仅支持单月查询；所查账期至多距今 24 个月



**ExpenseDate** <span data-label="purple">string</span> `可选` `示例值：2023-03-15`

账单日期，在GroupPeriod=1或2时支持账单日期传参，必须与账期在同一月份。该参数可提升查询性能，建议填写。



**GroupTerm** <span data-label="purple">integer</span> `可选` `示例值：0`

统计项：0：计费项；1：实例；2：产品；3：账号



**GroupPeriod** <span data-label="purple">integer</span> `可选` `示例值：0`

统计周期；0：账期；1：按天；2：明细；不传时默认按月汇总费用，若需按天分别汇总每日费用可传1；



**InstanceNo** <span data-label="purple">string</span> `可选` `示例值：i-ycjlq77tdg8rx6ib4v1s`

实例id：云产品计费实例id，承载购买的云资源或资产的计费实体；



**IgnoreZero** <span data-label="purple">integer</span> `可选` `示例值：1`

是否忽略折后价为0的数据：0：不忽略；1忽略；默认为不忽略



**NeedRecordNum** <span data-label="purple">integer</span> `可选` `示例值：1`

是否需要访问列表的总记录数：用于前端分页；1：表示需要； 0：表示不需要；默认为不需要，Total返回\-1



&nbsp;

<span id=".6L-U5Zue5Y-C5pWw"></span>
## 返回参数

下表仅列出本接口特有的返回参数。更多信息请参见[返回结构](https://www.volcengine.com/docs/6369/80336)



**List** <span data-label="purple">object[]</span> `示例值：-`

账单明细列表


**RealValue** <span data-label="purple">string</span>

真实金额



**TagRemark** <span data-label="purple">string</span>

标签备注



**PointDeductAmount** <span data-label="purple">string</span> `示例值：0.00`

积分抵扣金额



**TaxRate** <span data-label="purple">string</span>

税率



**PretaxAmount** <span data-label="purple">string</span>

税前应付金额



**PickupVoucherDeductCount** <span data-label="purple">string</span>

提货券抵扣量



**PickupVoucherID** <span data-label="purple">string</span>

提货券ID



**PickupVoucherCountUnit** <span data-label="purple">string</span>

提货券抵扣量单位



**PriceFactor** <span data-label="purple">string</span>

算价因子



**SavingPlanDeductionDiscountTotalAmount** <span data-label="purple">string</span>

节省计划抵扣总额



**ChargeItemCode** <span data-label="purple">string</span> `示例值：hourly_sum`

计费项code



**ResourceID** <span data-label="purple">string</span>

资源ID



**OriginalOrderNo** <span data-label="purple">string</span>

原订单号



**MainContractNumber** <span data-label="purple">string</span>

合同号



**CurrencySettlement** <span data-label="purple">string</span> `示例值：CNY`

结算币种



**ExchangeRate** <span data-label="purple">string</span> `示例值：1.00`

汇率



**SettlePreTaxPayableAmount** <span data-label="purple">string</span> `示例值：0.66`

税前应付金额（结算币种）



**SettlePayableAmount** <span data-label="purple">string</span> `示例值：0.66`

税后应付金额（结算币种）



**PreTaxPayableAmount** <span data-label="purple">string</span> `示例值：0.66`

税前应付金额（定价币种）



**DiscountInfo** <span data-label="purple">string</span> `示例值：节省计划：Spn-2000000036383219200,超额累进单价,(0,2),(200,1.8),CN202505201929261`

优惠信息



**SavingPlanDeductionDiscountAmount** <span data-label="purple">string</span> `示例值：576.400000`

节省计划抵扣金额



**SavingPlanOriginalAmount** <span data-label="purple">string</span> `示例值：621.946905`

节省计划抵扣原价



**SavingPlanDeductionSpID** <span data-label="purple">string</span> `示例值：Spn-2000000036383219200`

节省计划实例ID



**SettlePretaxAmount** <span data-label="purple">string</span>

结算币种税前应付金额



**CountryRegion** <span data-label="purple">string</span>

国家地区



**ProjectDisplayName** <span data-label="purple">string</span> `示例值：默认项目`

项目中文名



**ProjectRemark** <span data-label="purple">string</span>

项目备注



**SettlePretaxRealValue** <span data-label="purple">string</span>

结算币种税前真实金额



**SettleRealValue** <span data-label="purple">string</span>

结算币种真实金额



**PretaxRealValue** <span data-label="purple">string</span>

税前真实金额



**SettleTax** <span data-label="purple">string</span>

结算币种税额



**Tax** <span data-label="purple">string</span>

税额



**SettlePosttaxAmount** <span data-label="purple">string</span>

结算币种税后应付金额



**PosttaxAmount** <span data-label="purple">string</span>

税后应付金额



**Formula** <span data-label="purple">string</span> `示例值：（333）【单价】 * （2419200秒）【使用时长】 * （1/2419200）【时长转化系数】 - （0.000000）【优惠金额】 - （0.000000）【抹零金额】 - （0.000000）【代金券抵扣】`

应付金额计费公式



**DiscountBizUnitPrice** <span data-label="purple">string</span> `示例值：1.3`

优惠价格/折扣



**DiscountBizUnitPriceInterval** <span data-label="purple">string</span> `示例值：1,2,3`

优惠价格区间



**DiscountBizMeasureInterval** <span data-label="purple">string</span> `示例值：0,100,200`

优惠用量区间



**EffectiveFactor** <span data-label="purple">string</span> `示例值：1`

有效因子



**PriceInterval** <span data-label="purple">string</span> `示例值：1,2,3`

单价价格区间



**MeasureInterval** <span data-label="purple">string</span> `示例值：0,100,200`

单价用量区间



**BillingMethodCode** <span data-label="purple">string</span> `示例值：按加和量小时结`

计费方式



**DiscountBizBillingFunction** <span data-label="purple">string</span> `示例值：全额累进单价`

代表优惠类型；当DiscountBizBillingFunction为固定单价和单一折扣时，优惠内容取DiscountBizUnitPrice字段；当DiscountBizBillingFunction为阶梯价时，单价取DiscountBizMeasureInterval和DiscountBizUnitPriceInterval字段，表达各个用量区间的不同优惠内容



**Price** <span data-label="purple">string</span> `示例值：640.00`

单价



**MarketPrice** <span data-label="purple">string</span> `示例值：2.716`

市场价



**BillingFunction** <span data-label="purple">string</span> `示例值：固定单价`

代表单价价格类型；当BillingFunction为固定单价时，单价取Price字段；当BillingFunction为阶梯价时，单价取MeasureInterval和PriceInterval字段，表达各个用量区间的不同价格



**CreditCarriedAmount** <span data-label="purple">string</span> `示例值：0.000`

信控额度退款抵扣



**PreferentialBillAmount** <span data-label="purple">string</span> `示例值：5.036185`

优惠金额



**InstanceName** <span data-label="purple">string</span> `示例值：ECS-fEaG`

实例名称



**ConfigName** <span data-label="purple">string</span> `示例值：低配`

配置名称



**Element** <span data-label="purple">string</span> `示例值：BE000232`

计费单元



**Region** <span data-label="purple">string</span> `示例值：华北2（北京`

地域



**Zone** <span data-label="purple">string</span> `示例值：可用区B`

可用区



**Factor** <span data-label="purple">string</span> `示例值：{"type":"zanya"}`

影响因子



**ExpandField** <span data-label="purple">string</span> `示例值：按加和量小时结`

扩展字段



**PriceUnit** <span data-label="purple">string</span> `示例值：块`

单价单位



**BusiPeriod** <span data-label="purple">string</span> `示例值：2023-08`

业务账期



**Count** <span data-label="purple">string</span> `示例值：0`

用量



**Unit** <span data-label="purple">string</span> `示例值：GB`

用量单位



**BillDetailId** <span data-label="purple">string</span> `示例值：Detail7039533873751019820`

账单明细ID



**DeductionCount** <span data-label="purple">string</span> `示例值：0`

资源包抵扣量



**OriginalBillAmount** <span data-label="purple">string</span> `示例值：5.711200`

原价



**RoundAmount** <span data-label="purple">double</span> `示例值：0.00`

抹零金额



**DiscountBillAmount** <span data-label="purple">string</span> `示例值：0.66`

折后价



**CouponAmount** <span data-label="purple">string</span> `示例值：0.00`

代金券抵扣



**PayableAmount** <span data-label="purple">string</span> `示例值：0.66`

应付金额



**PaidAmount** <span data-label="purple">string</span> `示例值：0.00`

现金支付



**UnpaidAmount** <span data-label="purple">string</span> `示例值：0.66`

欠费金额



**Currency** <span data-label="purple">string</span> `示例值：CNY`

币种



**SettlementType** <span data-label="purple">string</span> `示例值：结算类型，settle：结算，non-settle：非结算，quota-settle：Quota结算`

非结算



**Project** <span data-label="purple">string</span> `示例值：default`

项目：资源实例所属的项目信息，通常可定义为企业内部的部门、业务线等以便厘清成本归属与进行分账管理；取值为结算周期所在小时末实例所属的项目；按天/账期聚合时，项目展示为最新的项目；



**Tag** <span data-label="purple">string</span> `示例值：{"voKey1":["v1"],"voKey101":["v5"],"voKey2":["v2"],"volc:vke:cluster-id":["valu3"],"volc:vke:createdby-vke-flag":["valu4"],"volc:vke:used-by-vke-cluster":["value5"]}`

标签：资源实例的标识；同一资源可绑定多个标签键值对，如资源创建者、资源使用部门、资源应用系统或环境等来标识资源费用信息；取值为结算周期的最后一小时内资源实例存在过的标签信息；按天/账期聚合时，标签展示为最新的标签；



**SellingMode** <span data-label="purple">string</span> `示例值：0`

售卖模式，0：普通实例，1：竞价实例



**SolutionZh** <span data-label="purple">string</span> `示例值：测试方案`

解决方案中文名称



**SubjectName** <span data-label="purple">string</span> `示例值：北京火山引擎科技有限公司`

主体名



**OwnerUserName** <span data-label="purple">string</span> `示例值：Doooo`

Owner账户名



**BillCategory** <span data-label="purple">string</span> `示例值：消费-使用`

账单类型



**ReservationInstance** <span data-label="purple">string</span> `示例值：0`

售卖模式，0：普通实例，1：弹性预约实例



**ElementCode** <span data-label="purple">string</span> `示例值：BE000137`

计费单元Code



**RegionCode** <span data-label="purple">string</span> `示例值：R000671`

地域Code



**ZoneCode** <span data-label="purple">string</span> `示例值：Zone1`

可用区Code



**FactorCode** <span data-label="purple">string</span> `示例值：{"type":"large"}`

影响因子Code



**ConfigurationCode** <span data-label="purple">string</span> `示例值：ecs.g1.large`

配置Code



**DeductionUseDuration** <span data-label="purple">string</span> `示例值：0.0`

抵扣量



**BillPeriod** <span data-label="purple">string</span> `示例值：2023-08`

账期



**ExpenseDate** <span data-label="purple">string</span> `示例值：2023-08-14`

日期



**PayerID** <span data-label="purple">string</span> `示例值：2100153894`

支付账号ID



**PayerUserName** <span data-label="purple">string</span> `示例值：Doooo`

支付账户名



**PayerCustomerName** <span data-label="purple">string</span> `示例值：北京火山引擎科技有限公司`

支付账号客户名称



**SellerID** <span data-label="purple">string</span> `示例值：3423`

Seller账号ID



**SellerUserName** <span data-label="purple">string</span> `示例值：火山引擎`

Seller账户名



**SellerCustomerName** <span data-label="purple">string</span> `示例值：北京火山引擎科技有限公司`

Seller账号客户名称



**OwnerID** <span data-label="purple">string</span> `示例值：2100153894`

Owner账号ID



**OwnerCustomerName** <span data-label="purple">string</span> `示例值：北京火山引擎科技有限公司`

Owner账号客户名称



**BusinessMode** <span data-label="purple">string</span> `示例值：普通业务`

业务类型



**Product** <span data-label="purple">string</span> `示例值：ECS`

产品英文名称



**ProductZh** <span data-label="purple">string</span> `示例值：云服务器`

使用的产品/服务的商品中文名称；



**BillingMode** <span data-label="purple">string</span> `示例值：按量计费`

计费模式：1：包年包月，代表预付费；2：按量计费，代表后付费；3：合同计费，代表线下计费；4：履约计费；



**ExpenseBeginTime** <span data-label="purple">string</span> `示例值：2023-08-14`

消费开始时间



**ExpenseEndTime** <span data-label="purple">string</span> `示例值：-`

消费结束时间



**UseDuration** <span data-label="purple">string</span> `示例值：0`

使用时长



**UseDurationUnit** <span data-label="purple">string</span> `示例值：秒`

时长单位



**TradeTime** <span data-label="purple">string</span> `示例值：2023-08-01 01:28:14`

交易时间，格式：2006\-01\-02 15:04:05



**BillID** <span data-label="purple">string</span> `示例值：Bill7262035879529697551`

订单号/账单号



**InstanceNo** <span data-label="purple">string</span> `示例值：i-ycjlq77tdg8rx6ib4v1s`

实例ID




**Total** <span data-label="purple">integer</span> `示例值：100`

总数，默认返回\-1（NeedRecordNum=0时）



**Limit** <span data-label="purple">integer</span> `示例值：100`

步长



**Offset** <span data-label="purple">integer</span> `示例值：0`

偏移量



&nbsp;

<span id=".6K-35rGC56S65L6L"></span>
## 请求示例

```text
// 以下示例不包含签名，建议直接使用API Explorer或下载SDK调试。
curl --location 'https://open.volcengineapi.com?Action=ListBillDetail&Version=2022-01-01' \
--header 'AccessKey: AK***mE' \
--header 'SecretKey: T0***RQ==' \
--header 'Region: cn-north-1' \
--header 'ServiceName: billing' \
--header 'Content-Type: application/json' \
--header 'User-Agent: volcengine-go-sdk' \
--data '{
    "BillPeriod": "2024-01",
    "Limit": 10,
    "Offset": 0,
    "NeedRecordNum": 1,
    "IgnoreZero": 0
}'
```


<span id=".6L-U5Zue56S65L6L"></span>
## 返回示例

```json
{
    "ResponseMetadata": {
        "RequestId": "202404021750412C935003765CD553A37B",
        "Action": "ListBillDetail",
        "Version": "20220101",
        "Service": "billing"
    },
    "Result": {
        "List": [
            {
                "BillPeriod": "2024-02",
                "ExpenseDate": "2024-02-29",
                "PayerID": "2100153894",
                "PayerUserName": "Doooo",
                "PayerCustomerName": "北京火山引擎科技有限公司",
                "SellerID": "3423",
                "SellerUserName": "火山引擎",
                "SellerCustomerName": "北京火山引擎科技有限公司",
                "OwnerID": "2100153894",
                "OwnerUserName": "Doooo",
                "OwnerCustomerName": "北京火山引擎科技有限公司",
                "BusinessMode": "普通业务",
                "Product": "volume",
                "ProductZh": "弹性块存储",
                "BillingMode": "按量计费",
                "ExpenseBeginTime": "2024-02-29 23:00:00",
                "ExpenseEndTime": "2024-03-01 00:00:00",
                "UseDuration": "3600",
                "UseDurationUnit": "秒",
                "TradeTime": "2024-03-01 00:24:14",
                "BillID": "Bill7341060462455001381",
                "BillCategory": "消费-使用",
                "InstanceNo": "vol-50mgf1r2g7l6hswihmfg",
                "InstanceName": "vol-50mgf1r2g7l6hswihmfg",
                "ConfigName": "系统盘-极速型SSD-PL0-按量计费",
                "Element": "EBS系统盘",
                "Region": "华北2（北京）",
                "Zone": "可用区B",
                "Factor": "类型-ESSD_PL0",
                "ExpandField": "",
                "Price": "0.001050",
                "PriceUnit": "GiB/时",
                "Count": "40",
                "Unit": "GiB",
                "DeductionCount": "0",
                "OriginalBillAmount": "0.042000",
                "PreferentialBillAmount": "0.036120",
                "DiscountBillAmount": "0.01",
                "CouponAmount": "0.00",
                "PayableAmount": "0.01",
                "PaidAmount": "0.00",
                "UnpaidAmount": "0.00",
                "Currency": "CNY",
                "SettlementType": "非结算",
                "Project": "default",
                "Tag": "",
                "SellingMode": "0",
                "SolutionZh": "",
                "SubjectName": "北京火山引擎科技有限公司",
                "RoundAmount": -0.00412,
                "BusiPeriod": "2024-02",
                "ReservationInstance": "0",
                "BillDetailId": "Detail7341060462454968613",
                "ElementCode": "BE001551",
                "RegionCode": "R000305",
                "ZoneCode": "cn-beijing-b",
                "FactorCode": "type-ESSD_PL0",
                "ConfigurationCode": "system-EBS_ESSD_PL0",
                "DeductionUseDuration": "0.0000000000",
                "CreditCarriedAmount": "0.00",
                "BillingFunction": "固定单价",
                "MarketPrice": "",
                "DiscountBizBillingFunction": "单一折扣",
                "DiscountBizUnitPrice": "0.14",
                "DiscountBizUnitPriceInterval": "-",
                "DiscountBizMeasureInterval": "-",
                "EffectiveFactor": "1",
                "PriceInterval": "-",
                "MeasureInterval": "-",
                "BillingMethodCode": "按配置小时结",
                "ProjectDisplayName": "默认项目"
            }
        ],
        "Total": 7721,
        "Limit": 1,
        "Offset": 0
    }
}
```


<span id=".6ZSZ6K-v56CB"></span>
## 错误码

下表为您列举了该接口与业务逻辑相关的错误码。公共错误码请参见[公共错误码](https://www.volcengine.com/docs/6369/68677)文档。


|状态码 |错误码 |错误信息 |说明 |
|---|---|---|---|
|400 |RequestInvalid |Request Invalid | |
|500 |InternalError |Service has some internal Error. Pls Contact With Admin. |服务内部异常 |




