查询用户账户余额信息。

## 调试

[您可以在OpenAPI Explorer中直接运行该接口，免去您计算签名的困扰。运行成功后，OpenAPI Explorer可以自动生成SDK代码示例。](https://api.aliyun.com/api/BssOpenApi/2017-12-14/QueryAccountBalance)

 [![](https://img.alicdn.com/tfs/TB16JcyXHr1gK0jSZR0XXbP8XXa-24-26.png) 调试](https://api.aliyun.com/api/BssOpenApi/2017-12-14/QueryAccountBalance)

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
| bss:DescribeAcccount | get | \\*全部资源 `*` | 无   | 无   |

## 请求参数

| **名称** | **类型** | **必填** | **描述** | **示例值** |
| --- | --- | --- | --- | --- |

当前API无需请求参数

## **返回参数**

| **名称** | **类型** | **描述** | **示例值** |
| --- | --- | --- | --- |
|     | object |     |     |
| Code | string | 状态码。 | 200 |
| Message | string | 错误信息。 | success |
| RequestId | string | 请求 ID。 | 16176743-6DC7-4CB3-BB25-A13982D8DFAD |
| Success | boolean | 是否成功。 | true |
| Data | object | 返回数据。 |     |
| AvailableAmount | string | 可用额度。 | 10000.00 |
| CreditAmount | string | 信控额度。 | 0.00 |
| MybankCreditAmount | string | 网商银行信用额度。 | 0.00 |
| Currency | string | 币种。取值范围： - CNY：人民币。 - USD：美元。 - JPY：日元。 | CNY |
| AvailableCashAmount | string | 现金余额。 | 10000.00 |
| QuotaLimit | string | 生态客户 Quota 限额 | 10000.00 |

## 示例

正常返回示例

`JSON`格式

```
{
  "Code": "200",
  "Message": "success",
  "RequestId": "16176743-6DC7-4CB3-BB25-A13982D8DFAD",
  "Success": true,
  "Data": {
    "AvailableAmount": "10000.00",
    "CreditAmount": "0.00",
    "MybankCreditAmount": "0.00",
    "Currency": "CNY",
    "AvailableCashAmount": "10000.00",
    "QuotaLimit": "10000.00"
  }
}
```

## 错误码

| **HTTP status code** | **错误码** | **错误信息** | **描述** |
| --- | --- | --- | --- |
| 400 | NotApplicable | This API is not applicable for caller. |     |
| 400 | NotAuthorized | This API is not authorized for caller. |     |
| 400 | MissingParameter | Some parameters arte mandatoryfor this request. |     |
| 400 | InvalidParameter | Some parametersare not valid. |     |
| 400 | InvalidOwner | The specifiedowner doesn’t belong to caller |     |
| 400 | InternalError | The request processing has failed due to some unknown error, exception or failure. |     |
| 400 | NoPermission | You are not authorized to perform this action. | 您无权执行此操作。 |
| 400 | AuthSiteFail | auth site failed. |     |
| 500 | UndefinedError | The request processing has failed due to some unknown error. |     |

访问[错误中心](https://api.aliyun.com/document/BssOpenApi/2017-12-14/errorCode)查看更多错误码。

## **变更历史**

更多信息，参考[变更详情](https://api.aliyun.com/document/BssOpenApi/2017-12-14/QueryAccountBalance#workbench-doc-change-demo)。