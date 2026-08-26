查询账户余额信息





## 调试
<APILink link="https://api.volcengine.com/api-explorer/?action=QueryBalanceAcct&groupName=%E8%B5%84%E9%87%91%E6%9C%8D%E5%8A%A1&serviceCode=billing&version=2022-01-01"></APILink>

## 请求参数

下表仅列出该接口特有的请求参数和部分公共参数。更多信息请见[公共参数](https://www.volcengine.com/docs/6369/67268)。



```mixin-react
const columns = [
  {
    width: '20%',
    title: '参数',
    dataIndex: 'Name',
    className: 'openapi-doc-parameter-table-name'
  },
  {
    width: 130,
    title: '类型',
    dataIndex: 'DataType',
    className: 'openapi-doc-parameter-table-type'
  },
  {
    width: 90,
    title: '是否必填',
    dataIndex: 'IsRequired',
    className: 'openapi-doc-parameter-table-required'
  },
  {
    width: '20%',
    title: '示例值',
    dataIndex: 'Example',
    className: 'openapi-doc-parameter-table-example'
  },
  {
    title: '描述',
    dataIndex: 'Description',
    className: 'openapi-doc-parameter-table-description'
  },
];

const data = [
  {
    rowKey: '->Action',
    Name: 'Action',
    DataType: 'String',
    IsRequired: '是',
    Example: <RenderMd content={"QueryBalanceAcct"} />,
    Description: <RenderMd content={"要执行的操作，取值：QueryBalanceAcct。"} />,
    children: [
    ]
  },
  {
    rowKey: '->Version',
    Name: 'Version',
    DataType: 'String',
    IsRequired: '是',
    Example: <RenderMd content={"2022-01-01"} />,
    Description: <RenderMd content={"API的版本，取值：2022-01-01。"} />,
    children: [
    ]
  },

];

return (<Table
  rowKey="rowKey"
  className="openapi-doc-parameter-table"
  columns={columns}
  data={data}
  border={ { cell: true, wrapper: true } }
  scroll={ { x: "auto" } }
  pagination={false}
/>);
```

## 返回参数


下表仅列出本接口特有的返回参数。更多信息请参见[返回结构](https://www.volcengine.com/docs/6369/80336)。


```mixin-react
const columns = [
  {
    width: '25%',
    title: '参数',
    dataIndex: 'Name',
    className: 'openapi-doc-parameter-table-name',
  },
  {
    width: 130,
    title: '类型',
    dataIndex: 'DataType',
    className: 'openapi-doc-parameter-table-type'
  },
  {
    width: '25%',
    title: '示例值',
    dataIndex: 'Example',
    className: 'openapi-doc-parameter-table-example'
  },
  {
    title: '描述',
    dataIndex: 'Description',
    className: 'openapi-doc-parameter-table-description'
  },
];

const data = [
  {
    rowKey: "->ArrearsBalance",
    Name: "ArrearsBalance",
    DataType: "String",
    Example: <RenderMd content={"1.01"} />,
    Description: <RenderMd content={"欠费金额\n"} />,
    children: [
    ]
  },
  {
    rowKey: "->AvailableBalance",
    Name: "AvailableBalance",
    DataType: "String",
    Example: <RenderMd content={"1.01"} />,
    Description: <RenderMd content={"可用余额\n"} />,
    children: [
    ]
  },
  {
    rowKey: "->CashBalance",
    Name: "CashBalance",
    DataType: "String",
    Example: <RenderMd content={"1.01"} />,
    Description: <RenderMd content={"现金余额"} />,
    children: [
    ]
  },
  {
    rowKey: "->CreditLimit",
    Name: "CreditLimit",
    DataType: "String",
    Example: <RenderMd content={"1.01"} />,
    Description: <RenderMd content={"信控额度"} />,
    children: [
    ]
  },
  {
    rowKey: "->FreezeAmount",
    Name: "FreezeAmount",
    DataType: "String",
    Example: <RenderMd content={"1.01"} />,
    Description: <RenderMd content={"冻结金额"} />,
    children: [
    ]
  },
  {
    rowKey: "->AccountID",
    Name: "AccountID",
    DataType: "Integer",
    Example: <RenderMd content={"21000000X"} />,
    Description: <RenderMd content={"账号ID"} />,
    children: [
    ]
  },
];

return (<Table
  rowKey="rowKey"
  className="openapi-doc-parameter-table"
  columns={columns}
  data={data}
  border={ { cell: true, wrapper: true } }
  scroll={ { x: "auto" } }
  pagination={false}
/>);
```

## 请求示例 
```text
GET /?Action=QueryBalanceAcct&Version=2022-01-01 HTTP/1.1
Host: https://open.volcengineapi.com?Action=QueryBalanceAcct&Version=2022-01-01
--header 'Authorization: Basic QUtUQWIwQTRhaxxxxxxxxxxxxxxxxxxxxxxxx' 
```
## 返回示例 
```json
{
    "ResponseMetadata": {
        "RequestId": "202308231151163C400BE8545DED89B87D",
        "Action": "QueryBalanceAcct",
        "Version": "2022-01-01",
        "Service": "billing"
    },
    "Result": {
        "AccountID": 210xxxxxxx,
        "ArrearsBalance": "1.01",
        "AvailableBalance": "77.01",
        "CashBalance": "83.01",
        "CreditLimit": "0.01",
        "FreezeAmount": "5.01",
    }
}
```


## 错误码
下表为您列举了该接口与业务逻辑相关的错误码。公共错误码请参见[公共错误码](https://www.volcengine.com/docs/6369/68677)文档。
```mixin-react
const columns = [
  {
    title: '状态码',
    dataIndex: 'HttpCode',
    width: '12%',
    className: 'openapi-doc-errorcode-table-httpcode'
  },
  {
    title: '错误码',
    dataIndex: 'ErrorCode',
    width: '22%',
    className: 'openapi-doc-errorcode-table-errorcode'
  },
  {
    title: '错误信息',
    dataIndex: 'ErrorMessage',
    width: '33%',
    className: 'openapi-doc-errorcode-table-errormessage'
  },
  {
    title: '说明',
    dataIndex: 'Description',
    width: '33%',
    className: 'openapi-doc-errorcode-table-description'
  },
];

const data = [
  {
    HttpCode: 400,
    ErrorCode: 'RecordNoFound',
    ErrorMessage: <RenderMd content={"The Record No Found."} />,
    Description: <RenderMd content={"查询无记录"} />,
  },
  {
    HttpCode: 400,
    ErrorCode: 'InvalidParam',
    ErrorMessage: <RenderMd content={"The parameter is invalid"} />,
    Description: <RenderMd content={"请求参数非法"} />,
  },
  {
    HttpCode: 500,
    ErrorCode: 'InternalError',
    ErrorMessage: <RenderMd content={"The request has failed due to an unknown error"} />,
    Description: <RenderMd content={"系统未知异常，请重试"} />,
  },
];

return (<Table
  columns={columns}
  data={data}
  border={ { cell: true, wrapper: true } }
  scroll={ { x: "auto" } }
  pagination={false}
/>);
```




<style>
.volc-md-viewer .arco-table-th {
	min-width: 100px;
}
.volc-md-viewer .openapi-doc-parameter-table-description{
  min-width: 150px;
}
.volc-md-viewer .openapi-doc-errorcode-table-errorcode {
  min-width: 150px;
}
.volc-md-viewer .openapi-doc-errorcode-table-errormessage {
  min-width: 150px;
}
.volc-md-viewer .openapi-doc-errorcode-table-description{
  min-width: 150px;
}
.volc-md-viewer .openapi-doc-parameter-table .arco-table-tr>.arco-table-td:first-child .arco-table-cell {
  display: flex;
}
.volc-md-viewer .openapi-doc-parameter-table .arco-table-tr>.arco-table-td:nth-child(2) .arco-table-cell {
  word-break: normal;
}
</style>
