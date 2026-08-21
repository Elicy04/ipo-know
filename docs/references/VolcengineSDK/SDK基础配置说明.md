Viking 知识库支持通过 Python SDK、Java SDK、Golang SDK 操作知识库，SDK 提供了高层次的抽象和易于使用的接口，简化开发人员的工作。在使用 SDK 之前，需要先完成安装 SDK 和初始化 SDK 的步骤。
**知识库 SDK 更新！！！**
此前知识库 SDK 基于火山引擎统一 SDK 提供，由于该包聚合了多个产品，耦合度高、历史问题较多，因此知识库 SDK 已完成整体重构，升级为新版 SDK。新版 SDK 对齐最新 API 参数，后续将持续维护迭代。旧版 SDK 将不再新增功能或提供维护，**建议尽快迁移至新版。** 如需查看旧版文档，请参考 [旧版 SDK 文档](https://www.volcengine.com/docs/84313/1269145?lang=zh)。
<span id="前提条件"></span>
### 前提条件

1. 已通过 [注册账号及开通服务](https://www.volcengine.com/docs/84313/1254444) 操作完成注册账号及开通服务。
2. 获取安全凭证。知识库 SDK 支持使用火山引擎 API Key 或 AK/SK 进行鉴权。可登录火山引擎控制台并前往【访问控制】—【API 访问密钥】，在 API Key 区域创建和管理 API Key，或查看当前账号的 AK/SK。更多详情请参考 [Access Key（密钥）管理](https://www.volcengine.com/docs/6291/65568)。

<div style="text-align: center"><img src="https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/7c7f4665537f428c8b5461e4092e0389~tplv-goo7wpa0wc-image.image" width="337px" /></div>

<span id="安装-sdk"></span>
### 安装 SDK
<span id="python"></span>
#### Python
```Python
pip install vikingdb-python-sdk
```

<span id="golang"></span>
#### Golang
```Go
go get github.com/volcengine/vikingdb-go-sdk
```

<span id="java"></span>
#### Java
```XML
<dependency>
    <groupId>com.volcengine</groupId>
    <artifactId>vikingdb-java-sdk</artifactId>
    <version>{version}</version>
    <!-- 推荐使用最新版本 -->
    <!-- 版本号可以参考https://central.sonatype.com/artifact/com.volcengine/vikingdb-java-sdk/versions -->
</dependency>
```

Maven 仓库：
[https://central.sonatype.com/artifact/com.volcengine/vikingdb-java-sdk/versions](https://central.sonatype.com/artifact/com.volcengine/vikingdb-java-sdk/versions)
源码地址：
[https://github.com/volcengine/vikingdb-java-sdk](https://github.com/volcengine/vikingdb-java-sdk)
<span id="使用提示"></span>
### 使用提示

* 各接口函数的示例代码已在后续对应文件中提供。使用前请根据实际场景完成以下参数配置：
   * 鉴权参数：AK/SK 或 APIKey
   * 连接参数：服务域名 Host、超时时间 Timeout
* 当前支持华北区域，域名为 api-knowledgebase.mlp.cn-beijing.volces.com

<span id="faq"></span>
### FAQ
**Q1**：知识库的 SDK 调用支持哪些语言？
**A1**：知识库目前支持通过 Python SDK、Java SDK、Golang SDK 操作。鉴权方式可参考：[API 签名鉴权与调用示例](https://www.volcengine.com/docs/84313/1254485)
**Q2**：知识库的 API 调用支持哪些语言？
**A2**：知识库支持 RESTful API，可以使用多种语言进行调用，例如 Python、Go、Java 等。

