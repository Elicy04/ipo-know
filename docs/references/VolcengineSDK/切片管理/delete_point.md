<span id="概述"></span>
# 概述
delete_point 用于删除知识库下的某个切片。
<span id="请求参数"></span>
# **请求参数**

| | | | | | \
|**参数** |**类型** |**必选** |**默认值** |**备注** |
|---|---|---|---|---|
| | | | | | \
|collection_name |string |否 |-- |**知识库名称** |\
| | | | | |\
| | | | |* 只能使用英文字母、数字、下划线_，并以英文字母开头，不能为空 |\
| | | | |* 长度要求：[1, 64] |
| | | | | | \
|project_name |string |否 |default |**知识库所属项目，获取方式参见文档**[API 接入与技术支持](/c8p1dfoq/y97x844a) |\
| | | | |若不指定该字段，则在 default 项目下创建。 |\
| | | | |若需要操作指定项目下的知识库，需正确配置该字段。 |
| | | | | | \
|resource_id |string |否 |-- |**知识库唯一 ID** |\
| | | | | |\
| | | | |* 可选择直接传 resource_id，或同时传 collection_name 和 project_name 作为知识库的唯一标识 |
| | | | | | \
|point_id |string |是 |-- |**要删除的切片 ID** |

<span id="响应消息"></span>
# **响应消息**

| | | | \
|字段 |类型 |备注 |
|---|---|---|
| | | | \
|code |Optional[int] |状态码 |
| | | | \
|message |Optional[str] |返回信息 |
| | | | \
|request_id |Optional[str] |每个请求的唯一标识符 |
| | | | \
|data |Optional[Any] |返回数据（通常为空） |

<span id="请求示例"></span>
# 请求示例
首次使用知识库 SDK，可参考 [使用说明](https://www.volcengine.com/docs/84313/2277191?lang=zh)
本示例演示了知识库 Python SDK 中 DeletePoint 函数的基础使用方法，通过指定知识库名称和切片 ID 实现切片删除，使用前需配置 API Key 鉴权参数。
```Python
import os

from vikingdb.knowledge import VikingKnowledge
from vikingdb.auth import APIKey
from vikingdb.knowledge.models.point import DeletePointRequest

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
    
    point_id = "your_point_id"
    
    try:
        collection.delete_point(DeletePointRequest(point_id=point_id))
        print("DeletePoint success")
    except Exception as e:
        print(f"DeletePoint failed, err: {e}")

if __name__ == "__main__":
    main()
```


