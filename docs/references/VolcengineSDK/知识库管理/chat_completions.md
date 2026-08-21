本节将说明如何基于多轮历史对话，使用大语言模型进行回答生成。
<span id="概述"></span>
# 概述
chat_completions 用于向大模型发起一次对话请求，与新升级的 search_knowledge 联通，可以完成标准的检索生成链路。
<span id="请求参数"></span>
# **请求参数**

| | | | | | | \
|**参数** |**子参数** |**类型** |**是否必选** |**默认值** |**参数说明** |
|---|---|---|---|---|---|
| | | | | | | \
|model |-- |str |是 |Doubao-1-5-pro-32k |**想要用于在线生成的大模型** |\
| | | | | | |\
| | | | | |* 当指定为 doubao 系列模型时默认使用系统的公共推理接入点，适合调试场景，有 tpm 限流 |\
| | | | | |* 或指定为在方舟上创建的推理接入点 ID，适合生产场景，tpm 配置可在创建推理接入点时自行调整 |\
| | | | | | |\
| | | | | |公共推理接入点模型可选范围详见下表。 |\
| | | | | |私有推理接入点 ID 形如： |\
| | | | | |*ep-202406040*****-***** |\
| | | | | |注意，当使用私有接入点时，需要配合传入 API key 进行鉴权 |\
| | | | | |> 注：默认值可能随版本更新而变化。为确保产品效果稳定，建议用户指定模型版本 |
| | | | | | | \
|model_version |-- |Optional[str] |否 |-- |对话模型和图像理解模型的可选范围详见下表。 |
| | | | | | | \
|thinking |-- |Optional[Dict[str, Any]] |否 |enabled |**控制模型是否开启深度思考模式** |\
| | | | | |取值范围： |\
| | | | | | |\
| | | | | |* enabled：开启思考模式，模型一定先思考后回答。 |\
| | | | | |* disabled：关闭思考模式，模型直接回答问题，不会进行思考。 |\
| | | | | |* auto：自动思考模式，模型根据问题自主判断是否需要思考，简单题目直接回答。 |\
| | | | | | |\
| | | | | |当前支持的模型详情见：[thinking](https://www.volcengine.com/docs/82379/1449737#%E5%85%B3%E9%97%AD%E6%B7%B1%E5%BA%A6%E6%80%9D%E8%80%83) |\
| | | | | |**示例：** |\
| | | | | |```bash |\
| | | | | |extra_body={ |\
| | | | | |         "thinking": { |\
| | | | | |             "type": "disabled",  # 不使用深度思考能力 |\
| | | | | |             # "type": "enabled", # 使用深度思考能力 |\
| | | | | |             # "type": "auto", # 模型自行判断是否使用深度思考能力 |\
| | | | | |         } |\
| | | | | |     } |\
| | | | | |``` |\
| | | | | | |
| | | | | | | \
|api_key |-- |Optional[str] |否 |-- |**接入点 API Key** |\
| | | | | |当需要使用私有模型接入点时，需传入对应 API key 进行鉴权 |
| | | | | | | \
|messages |-- |List[ChatMessage] |是 |-- |发出消息的对话参与者角色，可选值包括： |\
| | | | | | |\
| | | | | |* system：System Message 系统消息 |\
| | | | | |* user：User Message 用户消息 |\
| | | | | |* assistant：Assistant Message 对话助手消息 |\
| | | | | | |\
| | | | | |**多轮文本问答**：串联脚本示例可参考[知识库多轮检索问答样例](https://www.volcengine.com/docs/84313/1392553?lang=zh) |\
| | | | | |```json |\
| | | | | |[ |\
| | | | | |     {"role": "system", "content": "你是一位在线客服，你的首要任务是通过巧妙的话术回复用户的问题，你需要根据「参考资料」来回答接下来的「用户问题」，这些信息在 <context></context> XML tags 之内，你需要根据参考资料给出准确，简洁的回答。"}, |\
| | | | | |     {"role": "user", "content": "推荐一个适合 3 岁小孩的玩具"}, |\
| | | | | |     {"role": "assistant", "content": "您好！3 岁宝宝正处于身体、智力、情感多方面快速发展的阶段，您可以看看以下几款类型的玩具：乐高积木、拼图、消防局与消防直升机套装、医疗玩具套装、儿童滑板车"} |\
| | | | | |     {"role": "user", "content": "详细介绍下乐高积木有哪些合适的系列"}, |\
| | | | | | ] |\
| | | | | |``` |\
| | | | | | |\
| | | | | |**多轮图文理解**：串联脚本示例可参考[知识库图文问答样例](https://www.volcengine.com/docs/84313/1403979?lang=zh) |\
| | | | | |```plain-text |\
| | | | | |[ |\
| | | | | |     { |\
| | | | | |         "role": "system", |\
| | | | | |         "content": "你是一位在线客服，你的首要任务是通过巧妙的话术回复用户的问题，你需要根据「参考资料」来回答接下来的「用户问题」，这些信息在 <context></context> XML tags 之内，你需要根据参考资料给出准确，简洁的回答。参考资料中可能会包含图片信息，图片的引用说明在<img></img>XML tags 之内，参考资料内的图片顺序与用户上传的图片顺序一致。" |\
| | | | | |     }, |\
| | | | | |     { |\
| | | | | |         "role": "user", |\
| | | | | |         "content": [ |\
| | | | | |             { |\
| | | | | |                 "type": "text", |\
| | | | | |                 "text": "推荐一个适合 3 岁小孩的玩具" |\
| | | | | |             }, |\
| | | | | |             { |\
| | | | | |                 "type": "image_url", |\
| | | | | |                 "image_url": { |\
| | | | | |                     "url": "https://ark-project.tos-cn-beijing.volces.XXX.jpeg" # 从知识库中召回的 top1 图片 url |\
| | | | | |                 } |\
| | | | | |             }, |\
| | | | | |             { |\
| | | | | |                 "type": "image_url", |\
| | | | | |                 "image_url": { |\
| | | | | |                     "url": "https://ark-project.tos-cn-beijing.volcess.XXX.jpeg" # 从知识库中召回的 top2 图片 url |\
| | | | | |                 } |\
| | | | | |             } |\
| | | | | |         ] |\
| | | | | |     } |\
| | | | | | ] |\
| | | | | |``` |\
| | | | | | |
| | | | | | | \
|stream |-- |Optional[bool] |否 |False |**响应内容是否流式返回** |\
| | | | | | |\
| | | | | |* false：模型生成完所有内容后一次性返回结果 |\
| | | | | |* true：按 SSE 协议逐块返回模型生成内容，并以一条 data: [DONE] 消息结束 |
| | | | | | | \
|max_tokens |-- |Optional[int] |否 |4096 |**模型可以生成的最大 token 数量** |\
| | | | | |> 注意 |\
| | | | | | |\
| | | | | |> * **模型回复最大长度（单位 token），取值范围各个模型不同，详细见**[模型列表](https://www.volcengine.com/docs/82379/1330310)。 |\
| | | | | |> * **输入 token 和输出 token 的总长度还受模型的上下文长度限制。** |
| | | | | | | \
|return_token_usage |-- |Optional[bool] |否 |False |**是否返回token用量统计** |
| | | | | | | \
|temperature |-- |Optional[float] |否 |0.1 |**采样温度** |\
| | | | | |控制了生成文本时对每个候选词的概率分布进行平滑的程度。取值范围为 [0, 1]。当取值为 0 时模型仅考虑对数概率最大的一个 token。 |\
| | | | | |较高的值（如 0.8）会使输出更加随机，而较低的值（如 0.2）会使输出更加集中确定。通常建议仅调整 temperature 或 top_p 其中之一，不建议两者都修改。 |

<span id="3ff9feda"></span>
## **对话模型**

| | | \
|模型名称 |可选版本 |
|---|---|
| | | \
|Doubao-1-5-pro-32k |250115, character-250715 |
| | | \
|Doubao-1-5-lite-32k |250115 |

<span id="54ec1b06"></span>
## **图像理解模型**

| | | \
|模型名称 |可选版本 |
|---|---|
| | | \
|Doubao-seed-2-0-pro |260215 |
| | | \
|Doubao-seed-2-0-lite |260215 |
| | | \
|Doubao-seed-2-0-mini |260215 |
| | | \
|Doubao-seed-1-8 |251228 |
| | | \
|Doubao-seed-1-6-vision |250815 |
| | | \
|Doubao-seed-1-6 |251015, 250615 |
| | | \
|Doubao-seed-1-6-flash |250828, 250615 |
| | | \
|Doubao-1-5-vision-pro-32k |250115 |

方舟模型下线说明：[https://www.volcengine.com/docs/82379/1350667?lang=zh](https://www.volcengine.com/docs/82379/1350667?lang=zh)
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
|data |Optional[ChatCompletionResult] |ChatCompletionResult |

<span id="ChatCompletionResult"></span>
### **ChatCompletionResult**

| | | | \
|**字段** |**类型** |**参数说明** |
|---|---|---|
| | | | \
|reasoning_content |Optional[str] |推理模型生成的内容 |
| | | | \
|generated_answer |Optional[str] |模型生成的回答 |
| | | | \
|usage |Optional[Dict[str, Any]] |token 用量统计 |
| | | | \
|prompt |Optional[str] |prompt 内容 |
| | | | \
|model |Optional[str] |模型名称 |
| | | | \
|finish_reason |Optional[str] |结束原因 |
| | | | \
|total_tokens |Optional[int] |总 token 数量 |

<span id="状态码说明"></span>
## **状态码说明**

| | | | | \
|**状态码** |**http状态码** |**返回信息** |**状态码说明** |
|---|---|---|---|
| | | | | \
|0 |200 |success |成功 |
| | | | | \
|1000001 |401 |unauthorized |缺乏鉴权信息 |
| | | | | \
|1000002 |403 |no permission |权限不足 |
| | | | | \
|1000003 |400 |invalid request：%s |非法参数 |

<span id="请求示例"></span>
# 请求示例
首次使用知识库 SDK，可参考 [使用说明](https://www.volcengine.com/docs/84313/2277191?lang=zh)
本示例使用 AK/SK（IAM）鉴权方式调用 `chat_completions`，当前该接口不支持 APIKey 作为知识库 SDK 鉴权。
```Python
import os
from vikingdb.knowledge import VikingKnowledge
from vikingdb.auth import IAM
from vikingdb.knowledge.models.chat import ChatCompletionRequest, ChatMessage


def main():
    access_key = os.getenv("VIKINGDB_AK")
    secret_key = os.getenv("VIKINGDB_SK")
    endpoint = "api-knowledgebase.mlp.cn-beijing.volces.com"
    region = "cn-beijing"
    
    client = VikingKnowledge(
        host=endpoint,
        region=region,
        auth=IAM(ak=access_key, sk=secret_key),
        scheme="https"
    )
    
    # 1. Prepare messages
    messages = [
        ChatMessage(role="user", content="Hello, who are you?")
    ]
    
    # 2. Call ChatCompletion
    try:
        resp = client.chat_completion(ChatCompletionRequest(
            model="Doubao-1-5-pro-32k", # Replace with your model endpoint
            messages=messages
        ))
        print(f"Response: {resp}")
    except Exception as e:
        print(f"ChatCompletion failed, err: {e}")

    # 3. Call ChatCompletion Stream
    stream = True
    try:
        resp = client.chat_completion(ChatCompletionRequest(
            model="Doubao-1-5-pro-32k", # Replace with your model endpoint
            messages=messages,
            stream=stream
        ))
        for chunk in resp:
            print(f"Chunk: {chunk}")
    except Exception as e:
        print(f"ChatCompletionStream failed, err: {e}")

if __name__ == "__main__":
    main()
```


