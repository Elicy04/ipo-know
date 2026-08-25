## IPO知识库爬虫接入工具箱

面向 IPO 信息披露领域的桌面工具集，覆盖 **数据采集 → 知识库同步 → 智能问答** 完整链路，
支持接入阿里云百炼与火山引擎 VikingDB 两套云端 RAG 平台。

### 主要功能

| 模块 | 说明 |
|------|------|
| 爬虫采集 | 从上交所、深交所、北交所三大交易所抓取 IPO 项目申报文件与元数据 |
| 知识库同步 | 将本地采集的文件对齐上传至云端 RAG 知识库（增量 / 全量） |
| 知识检索 | 基于 RAG 平台的向量检索能力，对 IPO 文档进行语义搜索 |
| 智能问答 | 通过 RAG 平台的 Chat 接口，对检索结果进行自然语言问答 |
| 桌面 GUI | 基于 NiceGUI + pywebview 的桌面界面，提供配置、操作、问答、日志面板 |

### 便携版安装

项目通过 PyInstaller onedir 模式打包，产物为完整目录，属于**便携版**安装——无需安装 Python 环境。

1. 前往 [Releases](../../releases) 下载对应版本的 `ipo-know` 目录压缩包并解压
2. 目录结构：

```
ipo-know/
├── ipo-know.exe      # 主程序（双击启动）
├── data/             # 配置文件和数据库存储位置（自动创建）
│   ├── config.json   # GUI 配置 + API Key
│   └── ipo_know.db   # SQLite 数据库
├── logs/             # 运行日志（自动创建）
│   └── app.log
└── _internal/        # 运行时依赖（勿修改）
```

3. 双击 `ipo-know.exe` 即可启动 GUI
4. 在 GUI 的**配置面板**中填写 RAG 平台凭证，点击「保存」即生效

### 配置说明

所有配置项通过 GUI 的**配置面板**管理，支持火山引擎和阿里云两套 RAG 平台。

### 爬虫目标数据源

| 交易所 | 数据来源 |
|--------|---------|
| 上交所 (SSE) | 科创板 IPO 项目审核信息 |
| 深交所 (SZSE) | 创业板 IPO 项目审核信息 |
| 北交所 (BSE) | 北交所 IPO 项目审核信息 |

辅助数据源：东方财富（EastMoney）用于补充北交所项目查询。

### 支持的 RAG 平台

- **云端 RAG 知识库服务**
    - 火山引擎 VikingDB —— 知识库文档管理、向量检索、智能问答
    - 阿里云百炼 —— 知识库索引、文档检索、AI 问答
- **本地 RAG 知识库构建**：暂不支持（需要专用解析算力或大体积解析产物分发）

### 开发环境搭建

本项目使用 [uv](https://docs.astral.sh/uv/) 管理依赖，要求 **Python ≥ 3.11**。

```bash
# 1. 克隆仓库并进入目录
git clone <repo-url> && cd ipo-know

# 2. 同步依赖（自动生成 .venv）
uv sync

# 3. 启动应用
uv run ipo-know
```

代码格式化检查（提交前必须执行）：

```bash
uv run ruff check .
```

### 构建

使用 PowerShell 一键打包脚本（PyInstaller onedir 模式）：

```powershell
.\build.ps1           # 增量构建
.\build.ps1 -Clean    # 清理缓存后全量构建
```

产物输出至 `dist/ipo-know/` 目录，分发时需将整个目录一起打包，不可只复制 exe。

### 项目结构

```
src/ipo_know/
├── clients/          # 外部 API 客户端（交易所、RAG 平台）
├── config/           # 配置管理与日志
├── crawler/          # 三所爬虫实现
├── downloader/       # 文件下载器
├── kb_align/         # 知识库对齐同步（阿里云 / 火山引擎）
├── kb_query/         # 知识库检索与问答后端
├── storage/          # SQLAlchemy ORM 模型与仓库
└── ui/               # NiceGUI 桌面界面（配置、操作、问答、日志面板）
```
