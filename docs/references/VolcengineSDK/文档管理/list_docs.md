<span id="概述"></span>
# 概述
list_docs 用于查询知识库中文档列表，默认按文档上传时间倒序排列。
<span id="请求参数"></span>
# **请求参数**

| | | | | | | \
|**参数** |子参数 |**类型** |**是否必选** |**默认值** |**参数说明** |
|---|---|---|---|---|---|
| | | | | | | \
|collection_name |-- |string |否 |-- |**知识库名称** |
| | | | | | | \
|project_name |-- |string |否 |default |**知识库所属项目，获取方式参见文档**[API 接入与技术支持](/c8p1dfoq/y97x844a) |\
| | | | | |若不指定该字段，则默认在 default 项目下查询。 |\
| | | | | |若需要操作指定项目下的知识库，需正确配置该字段。 |
| | | | | | | \
|resource_id |-- |string |否 |-- |**知识库唯一 id** |\
| | | | | |可选择直接传 resource_id，或同时传 collection_name 和 project_name 作为知识库的唯一标识 |
| | | | | | | \
|filter | |Optional[Dict[str, Any]] |否 |-- |**过滤条件** |\
| | | | | |用于对返回结果进行过滤 |
| | | | | | | \
|offset |-- |int |否 |0 |**查询起始位置** |\
| | | | | |表示从结果的第几个文档后开始取，需要大于等于0 |\
| | | | | |注：如果设置 offset ≥ 100，需同时传入 limit 参数才能生效 |
| | | | | | | \
|limit |-- |int |否 |-1 |**查询文档数** |\
| | | | | |-1 表示获取所有，最大值不超过 100，每次返回最多不超过 100 |
| | | | | | | \
|doc_type |-- |Optional[str] |否 |-- |**文档类型筛选** |
| | | | | | | \
|return_token_usage |-- |Optional[bool] |否 |false |**是否返回文档向量化和文档摘要生成所消耗的 tokens** |

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
|data |Optional[ListDocsResult] |ListDocsResult |

<span id="ListDocsResult"></span>
### **ListDocsResult**

| | | | \
|**字段** |**类型** |**参数说明** |
|---|---|---|
| | | | \
|doc_list |Sequence[DocInfo] |文档信息列表 |
| | | | \
|count |Optional[int] |本次查询返回的文档总数 |
| | | | \
|total_num |Optional[int] |该知识库下的文档总数 |

<span id="DocInfo"></span>
### **DocInfo**

| | | | \
|**字段** |**类型** |**参数说明** |
|---|---|---|
| | | | \
|collection_name |Optional[str] |知识库名称 |
| | | | \
|doc_name |Optional[str] |文档名称 |
| | | | \
|doc_id |Optional[str] |文档 id |
| | | | \
|doc_hash |Optional[str] |文档 hash |
| | | | \
|add_type |Optional[str] |导入方式 |
| | | | \
|doc_type |Optional[str] |文档类型 |
| | | | \
|description |Optional[str] |文档描述（当前仅支持图片文档） |
| | | | \
|create_time |Optional[int] |文档创建时间 |
| | | | \
|added_by |Optional[str] |添加人 |
| | | | \
|update_time |Optional[int] |文档更新时间 |
| | | | \
|url |Optional[str] |原始文档链接 |
| | | | \
|tos_path |Optional[str] |TOS 路径 |
| | | | \
|point_num |Optional[int] |切片数量 |
| | | | \
|status |Optional[DocStatus] |DocStatus |
| | | | \
|title |Optional[str] |文档标题 |
| | | | \
|source |Optional[str] |知识来源（url，tos 等） |
| | | | \
|total_tokens |Optional[int] |token 统计 |
| | | | \
|doc_summary_tokens |Optional[int] |摘要 token 统计 |
| | | | \
|doc_premium_status |Optional[DocPremiumStatus] |DocPremiumStatus |
| | | | \
|doc_summary |Optional[str] |文档摘要 |
| | | | \
|brief_summary |Optional[str] |简要摘要 |
| | | | \
|doc_size |Optional[int] |文档大小 |
| | | | \
|meta |Optional[str] |meta 信息 |
| | | | \
|labels |Optional[Dict[str, str]] |标签信息 |
| | | | \
|video_outline |Optional[Dict[str, Any]] |视频大纲 |
| | | | \
|audio_outline |Optional[Dict[str, Any]] |音频大纲 |
| | | | \
|statistics |Optional[Dict[str, Any]] |统计信息 |
| | | | \
|project |Optional[str] |项目名 |
| | | | \
|resource_id |Optional[str] |知识库唯一 id |

<span id="DocStatus"></span>
### **DocStatus**

| | | | \
|**字段** |**类型** |**参数说明** |
|---|---|---|
| | | | \
|process_status |Optional[int] |处理状态 |
| | | | \
|failed_code |Optional[int] |失败错误码 |
| | | | \
|failed_msg |Optional[str] |失败错误信息 |

<span id="DocPremiumStatus"></span>
### **DocPremiumStatus**

| | | | \
|**字段** |**类型** |**参数说明** |
|---|---|---|
| | | | \
|doc_summary_status_code |Optional[int] |摘要状态码 |

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
|1000005 |400 |collection not exist |collection不存在 |

<span id="请求示例"></span>
# 请求示例
首次使用知识库 SDK，可参考 [使用说明](https://www.volcengine.com/docs/84313/2277191?lang=zh)
本示例演示了知识库 Python SDK 中 ListDocs 的基础使用方法，通过指定知识库名实现文档列表查询，使用前需配置 API Key 鉴权参数。
```Python
import os

from vikingdb.knowledge import VikingKnowledge
from vikingdb.auth import APIKey
from vikingdb.knowledge.models.doc import ListDocsRequest

def main():
    api_key = os.getenv("VIKINGDB_API_KEY") or ""
    endpoint = "api-knowledgebase.mlp.cn-beijing.volces.com"
    region = "cn-beijing"
    
    # 1. Initialize client
    client = VikingKnowledge(
        host=endpoint,
        region=region,
        auth=APIKey(api_key=api_key),
        scheme="https"
    )
    
    # 2. Get collection
    collection = client.collection(
        collection_name="Your collection name",
        project_name="default",
    )
    
    # 3. List docs
    try:
        resp = collection.list_docs(ListDocsRequest(
            offset=0,
            limit=10
        ))
        print(f"Response: {resp}")
    except Exception as e:
        print(f"ListDocs failed, err: {e}")

if __name__ == "__main__":
    main()
```


