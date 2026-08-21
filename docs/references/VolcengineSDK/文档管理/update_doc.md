<span id="概述"></span>
# 概述
update_doc 用于更新某个文档信息，如文档标题，文档信息更新会自动触发索引中的数据更新。
<span id="请求参数"></span>
# **请求参数**

| | | | | | | \
|**参数** |**子参数** |**类型** |**是否必选** |**默认值** |**参数说明** |
|---|---|---|---|---|---|
| | | | | | | \
|collection_name |-- |string |否 |-- |**知识库名称** |
| | | | | | | \
|project_name |-- |string |否 |default |**知识库所属项目，获取方式参见文档**[API 接入与技术支持](/c8p1dfoq/y97x844a) |\
| | | | | |若需要操作指定项目下的知识库，需正确配置该字段。 |
| | | | | | | \
|resource_id |-- |string |否 |-- |**知识库唯一 ID** |\
| | | | | |可选择直接传 resource_id，或同时传 collection_name 和 project_name 作为知识库的唯一标识 |
| | | | | | | \
|doc_id |-- |string |是 |-- |**待更新文档的 id** |
| | | | | | | \
|doc_name |-- |string |是 |-- |**更新后的文档名称** |

<span id="响应消息"></span>
# **响应消息**

| | | | \
|**字段** |**类型** |**参数说明** |
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
|**状态码** |**http 状态码** |**返回信息** |**状态码说明** |
|---|---|---|---|
| | | | | \
|0 |200 |success |成功 |
| | | | | \
|1000001 |401 |unauthorized |鉴权失败 |
| | | | | \
|1000002 |403 |no permission |权限不足 |
| | | | | \
|1000003 |400 |invalid request：%s |非法参数 |
| | | | | \
|1000005 |400 |collection not exist |collection 不存在 |
| | | | | \
|1001001 |400 |doc not exist |doc 不存在 |
| | | | | \
|1000028 |500 |internal error |内部错误 |

<span id="请求示例"></span>
# 请求示例
首次使用知识库 SDK，可参考 [使用说明](https://www.volcengine.com/docs/84313/2277191?lang=zh)
本示例演示了知识库 Python SDK 中 UpdateDoc 的基础使用方法，通过指定知识库名称、文档 ID 和新文档名称实现文档名称修改，使用前需配置 API Key 鉴权参数。
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
    
    doc_id = "Your doc id"
    doc_name = "Your new doc name"
    
    try:
        collection.update_doc(doc_id=doc_id, doc_name=doc_name)
        print("UpdateDoc success")
    except Exception as e:
        print(f"UpdateDoc failed, err: {e}")

if __name__ == "__main__":
    main()
```


