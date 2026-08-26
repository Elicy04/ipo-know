查询用户收支明细。

## 调试

[您可以在OpenAPI Explorer中直接运行该接口，免去您计算签名的困扰。运行成功后，OpenAPI Explorer可以自动生成SDK代码示例。](https://api.aliyun.com/api/BssOpenApi/2017-12-14/QueryAccountTransactionDetails)

 [![](https://img.alicdn.com/tfs/TB16JcyXHr1gK0jSZR0XXbP8XXa-24-26.png) 调试](https://api.aliyun.com/api/BssOpenApi/2017-12-14/QueryAccountTransactionDetails)

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
| bssapi:QueryAccountTransactionDetails | get | \\*全部资源 `*` | 无   | 无   |

## 请求参数

| **名称** | **类型** | **必填** | **描述** | **示例值** |
| --- | --- | --- | --- | --- |
| TransactionNumber | string | 否   | 交易编号 | 410874027490089 |
| RecordID | string | 否   | 订单号/账单号 | 2022120336190912 |
| TransactionChannelSN | string | 否   | 交易渠道流水号 | 2022112122001470591458665933 |
| CreateTimeStart | string | 否   | 创建时间起始 | 2022-01-20 |
| CreateTimeEnd | string | 否   | 创建时间终止 | 2022-12-20 |
| TransactionType | string | 否   | 交易类型。 传入以下交易类型，查询返回对应类型结果，不存在时结果为空。不传默认返回所有类型。 充值：Payment。 提现：Withdraw。 退款：Refund。 消费：Consumption。 转账：Transfer。 调账：Adjust。 | Payment |
| TransactionChannel | string | 否   | 交易渠道。 传入以下交易渠道类型，查询返回对应类型结果，不存在时结果为空。不传默认返回所有类型。 用户余额：AccountBalance。 银行转账： BankTransfer。 支付宝：Alipay。 支付宝花呗：AntCreditPay。 线下汇款：OfflineRemittance。 信控额度退款：RegularBankCreditRefund。 信用卡：CreditCard。 网商银行信任付：MyBankCredit。 华夏银行分期付：HuaxiaBankCInstallment。 苹果支付：ApplePay | AccountBalance |
| NextToken | string | 否   | 分页查询 token | ABEDSDS124DASA |
| MaxResults | integer | 否   | 无效参数 | 0   |

## **返回参数**

| **名称** | **类型** | **描述** | **示例值** |
| --- | --- | --- | --- |
|     | object | 接口返回结果 |     |
| Code | string | 响应状态码 | 200 |
| Message | string | 结果描述 | SUCCESS |
| RequestId | string | 请求 ID | asadadad-edafafafaasd |
| Success | boolean | 是否成功标识 | true |
| Data | object | 请求结果内容 |     |
| NextToken | string | 分页标识 | ASHDADS |
| TotalCount | integer | 查询结果总数 | 100 |
| MaxResults | integer | 无效参数 | 0   |
| AccountName | string | 账户名 | yidi |
| AccountTransactionsList | object |     |     |
| AccountTransactionsList | array<object> | 明细列表 |     |
|     | object | 结果  |     |
| BillingCycle | string | 账期  | 2022-10 |
| TransactionChannel | string | 交易渠道 | Alipay |
| RecordID | string | 订单号/账单号 | 2022120336190912 |
| Remarks | string | 备注  | 测试  |
| Amount | string | 金额  | 1.00 |
| TransactionAccount | string | 对应交易账号 | fortune\\_test@xxx.com |
| TransactionTime | string | 交易时间 | 2022-10-01 |
| TransactionType | string | 交易类型。 传入以下交易类型，查询返回对应类型结果，不存在时结果为空。不传默认返回所有类型。 充值：Payment。 提现：Withdraw。 退款：Refund。 消费：Consumption。 转账：Transfer。 调账：Adjust。 | Consumption |
| TransactionFlow | string | 收支类型。 传入以下收支类型，查询返回对应类型结果，不存在时结果为空。不传默认返回所有类型。 收入：Income。 支出：Expense | Income |
| FundType | string | 资金形式。 现金：Cash。 保证金：Deposit。 信控额度退款：RegularBankCreditRefund。 订单直接支付：DirectPay。 | Cash |
| TransactionChannelSN | string | 交易渠道流水号 | 123232434343532 |
| TransactionNumber | string | 交易编号 | 43342334 |
| Balance | string | 余额  | 0   |

## 示例

正常返回示例

`JSON`格式

```
{
  "Code": "200",
  "Message": "SUCCESS",
  "RequestId": "asadadad-edafafafaasd",
  "Success": true,
  "Data": {
    "NextToken": "ASHDADS",
    "TotalCount": 100,
    "MaxResults": 0,
    "AccountName": "yidi",
    "AccountTransactionsList": {
      "AccountTransactionsList": [
        {
          "BillingCycle": "2022-10",
          "TransactionChannel": "Alipay",
          "RecordID": "2022120336190912",
          "Remarks": "测试",
          "Amount": "1.00",
          "TransactionAccount": "fortune_test@xxx.com",
          "TransactionTime": "2022-10-01",
          "TransactionType": "Consumption",
          "TransactionFlow": "Income",
          "FundType": "Cash",
          "TransactionChannelSN": "123232434343532",
          "TransactionNumber": "43342334",
          "Balance": "0"
        }
      ]
    }
  }
}
```

## 错误码

访问[错误中心](https://api.aliyun.com/document/BssOpenApi/2017-12-14/errorCode)查看更多错误码。

## **变更历史**

更多信息，参考[变更详情](https://api.aliyun.com/document/BssOpenApi/2017-12-14/QueryAccountTransactionDetails#workbench-doc-change-demo)。