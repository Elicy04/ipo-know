<span id="概述"></span>
# 概述
delete_doc 用于删除知识库下的文档
<span id="请求参数"></span>
# **请求参数**

| | | | | | \
|**参数** |**类型** |**是否必选** |**默认值** |**参数说明** |
|---|---|---|---|---|
| | | | | | \
|collection_name |string |否 |-- |**知识库名称** |
| | | | | | \
|project_name |string |否 |default |**知识库所属项目，获取方式参见文档**[API 接入与技术支持](/c8p1dfoq/y97x844a) |\
| | | | |若不指定该字段，则默认在 default 项目下操作。 |\
| | | | |若需要操作指定项目下的知识库，请正确配置该字段。 |
| | | | | | \
|resource_id |string |否 |-- |**知识库唯一 id** |\
| | | | |可选择直接传 resource_id，或同时传 collection_name 和 project_name 作为知识库的唯一标识 |
| | | | | | \
|doc_id |string |是 |-- |**要删除的文档 id** |

<span id="响应消息"></span>
# **响应消息**

| | | | \
|**参数** |**类型** |**参数说明** |
|---|---|---|
| | | | \
|code |Optional[int] |状态码 |
| | | | \
|message |Optional[str] |返回信息 |
| | | | \
|request_id |Optional[str] |标识每个请求的唯一标识符 |
| | | | \
|data |Optional[Any] |返回数据（通常为空） |

<span id="状态码说明"></span>
## **状态码说明**

| | | | | \
|**状态码** |**HTTP 状态码** |**返回信息** |**状态码说明** |
|---|---|---|---|
| | | | | \
|0 |200 |success |成功 |
| | | | | \
|1000001 |401 |unauthorized |鉴权失败 |
| | | | | \
|1000002 |403 |no permission |权限不足 |
| | | | | \
|1000003 |400 |invalid request: %s |非法参数 |
| | | | | \
|1000005 |400 |collection not exist |collection 不存在 |
| | | | | \
|1001001 |400 |doc not exist |doc 不存在 |

<span id="请求示例"></span>
# 请求示例
首次使用知识库 SDK，可参考 [使用说明](https://www.volcengine.com/docs/84313/2277191?lang=zh)
本示例演示了知识库 Python SDK 中 `delete_doc` 方法的基础使用方法，通过指定知识库名称和文档 ID 实现文档删除，使用前需配置 API Key 鉴权参数。
```Python
import os

from vikingdb.knowledge import VikingKnowledge
from vikingdb.auth import APIKey

def main():
    api_key = os.getenv("VIKINGDB_API_KEY") or ""
    endpoint = "api-knowledgebase.mlp.cn-beijing.volces.com"
    region = "cn-beijing"
    
    client = VikingKnowledge(
        host=endpoint,
        region=region,
        auth=APIKey(api_key=api_key),
        scheme="https"
    )
    
    collection = client.collection(
        collection_name="Your collection name",
        project_name="default",
    )
    
    # Replace with a valid doc ID from your collection
    doc_id = "example_doc_id"
    
    try:
        collection.delete_doc(doc_id)
        print("DeleteDoc success")
    except Exception as e:
        print(f"DeleteDoc failed, err: {e}")

if __name__ == "__main__":
    main()
```


