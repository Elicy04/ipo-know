# IPO Know v0.2.0 Release Notes

## 🎯 本次发布亮点

### 1️⃣ **便携版重构 - 开箱即用的桌面应用**

从传统的 one-file 打包模式彻底重构为 **onedir 便携版**设计，所有配置和数据文件自动保存在与可执行文件同级的目录中：

```
ipo-know/                          ← 整个目录压缩分发给用户
├── ipo-know.exe                   ← 主程序（带图标）
├── data/                          ← ✅ 预创建目录（GUI 自动维护）
│   └── config.json                ← 知识库配置 + API Key
├── logs/                          ← ✅ 预创建目录（应用程序日志）
└── _internal/                     ← PyInstaller 解包目录（依赖）
```

**核心改进**:
- ✅ **移除 %LOCALAPPDATA% 路径依赖**：所有数据路径改为相对于 exe 所在目录的 `data/` 和 `logs/`
- ✅ **便携性强**：解压即用，无需安装，可放置在 U 盘或云同步文件夹
- ✅ **环境检测增强**：新增 `app_root()` 函数，自动识别 frozen/dev 环境并返回正确路径
- ✅ **构建流程统一**：合并 `build_onedir.ps1` 和 `ipo-know-crawler.spec`，仅保留 `build.ps1` 和 `ipo-know.spec`

### 2️⃣ **现代化的知识问答 UI**

完全重写了知识问答面板 (`chat_panel.py`)，采用类似 ChatGPT/Claude 的对话风格设计：

**视觉优化**:
- ✅ **居中限宽布局**：消息最大宽度 768px，阅读体验更佳
- ✅ **气泡式消息渲染**:
  - 用户消息：蓝色背景气泡，靠右显示，圆形头像
  - AI 回复：无背景框，左侧显示头像标识，Markdown 排版更优雅
- ✅ **Markdown 深度定制**：代码块深蓝底、分级标题、行距优化、列表缩进

**交互增强**:
- ✅ **思考过程折叠区**: 火山引擎推理模型（doubao-seed-2-0-pro）会输出 ~8s 思考阶段，新 UI 添加可折叠的灰色提示区域流式展示
- ✅ **引用来源置顶**: 多批次的文档引用来源自动合并，固定在最上方槽位，始终可见
- ✅ **智能滚动跟随**: 当用户滚动到距底部 120px 内时自动跟随新消息，避免手动回拉
- ✅ **输入区同位置按钮**: 发送/停止按钮成圆形互斥控件，位于 textarea 右下角，视觉紧凑

**后台完善**:
- ✅ **阿里云问答 SSE 客户端**: 完整实现 REST+SSE+API-Key 鉴权链路，支持规划→工具调用→生成的三阶段状态机
- ✅ **双平台前置校验**: 火山引擎需要 service_resource_id + api_key，阿里云需要 api_key + agent_id，未填则禁用提问

### 3️⃣ **知识库检索与上传功能增强**

#### **检索面板 (`search_panel.py`)** - 新建独立组件
- ✅ TabPanel 结构整合知识库同步和知识检索两个功能
- ✅ 知识检索支持关键词搜索、分页加载、上下文高亮
- ✅ 结果列表显示文档名称、更新时间、匹配片段

#### **操作面板 (`operation_panel.py`)** - 精简重构
- ✅ 移除冗余的逻辑分支，简化爬虫调度逻辑
- ✅ 统一使用 `LogPanel` 作为唯一的日志输出通道

### 4️⃣ **配置面板分组优化**

按照业务域将配置重新划分为四个卡片纵排：

| 卡片名 | 主要字段 | 高级配置位置 |
|--------|----------|--------------|
| **基本配置** | 密钥、资源 ID、API Key | - |
| **同步配置** | collection_name、resource_id、strategy_resource_id | 高级折叠区 |
| **检索配置** | 关键词过滤、分页参数 | 高级折叠区 |
| **问答配置** | workspace_id、agent_id、timeout | 高级折叠区 |

每个卡片都有独立的「保存」按钮，保存粒度虽仍为整平台段，但视觉上更清晰，用户可以逐步填充而不必一次性完成。

### 5️⃣ **运行日志页签独立 + 页签栏同行优化**

- ✅ **运行日志独立页签**: 在 TabPanels 末尾新增「运行日志」标签页，与配置/同步/检索/问答并列
- ✅ **日志填充页签高度**: 根容器采用 `h-full` 和 `flex-1` 布局，确保 `ui.log` 填满整个页签内容区
- ✅ **页签栏与平台选择同行**: 使用 Flex Row 布局，顶部工具栏水平排列，节省垂直空间
- ✅ **外层滚动条隐藏**: 问答页签单独设置 `overflow-y-hidden`，消除不必要的页面级滚动

### 6️⃣ **README 全面重写**

全新的 README.md 包含 118 行完整中文文档：
- ✅ **项目定位**: "IPO 信息披露领域桌面工具集，覆盖数据采集 → 知识库同步 → 智能问答"
- ✅ **主要功能表格**: 爬虫采集 / 知识库同步 / 知识检索 / 智能问答 / 桌面 GUI
- ✅ **便携版安装说明**: Releases 下载 → 解压 → GUI 配置 → 启动
- ✅ **配置详解**: GUI 配置面板使用说明
- ✅ **爬虫数据源**: 上交所 / 深交所 / 北交所 + 东方财富辅助
- ✅ **RAG 平台**: 火山引擎 VikingDB + 阿里云百炼
- ✅ **开发环境搭建**: `uv sync` + `uv run ipo-know`
- ✅ **构建命令**: `.\build.ps1` (增量/-Clean)
- ✅ **项目结构概要**: src/data/logs/tests/docs分区说明

### 7️⃣ **RAG 配置教程文档替代用户手册**

删除了旧的 `docs/manual/用户配置手册.md`，替换为两个平台的专属 RAG 配置教程：
- ✅ [`docs/user_manual/火山引擎 RAG 参数配置教程.md`](docs/user_manual/火山引擎 RAG 参数配置教程.md)
- ✅ [`docs/user_manual/阿里云 RAG 参数配置教程.md`](docs/user_manual/阿里云 RAG 参数配置教程.md)

涵盖：SDK IAM AK/SK vs API Key 鉴权区别、service_chat 强制 API Key、Bailian 知识库 workspace_index 创建步骤等实操指南。

---

## 📊 改动统计

### 核心提交汇总（自 v0.1.0 以来）

| PR # | 类型 | 描述 | 变更文件数 | 增减行数 |
|------|------|------|------------|----------|
| **#33** | chore | rename onedir build artifact to ipo-know-crawler | 5 | +26 / -9 |
| **#34** | feat | kb-query/search backend with retrieve and qa streaming | 13 | +1,339 |
| **#35** | feat | kb-query/search gui with tabs layout | 7 | +1,595 / -313 |
| **#36** | chore/feat | portable onedir build + QA experience improvements | 20 | +953 / -675 |
| **#37** | chore | pre-create portable directory structure (data/logs) for better UX | 1 | +32 / -2 |

### 关键文件变动

#### 📄 **UI 重构集中地** (`src/ipo_know/ui/`)
- `chat_panel.py`: 全新编写 (~1,030 行)，含 Markdown 定制、思考区折叠、智能滚动
- `config_panel.py`: 四卡片重组 (+399/-254 行)
- `main.py`: 页签布局调整 (+29 行)
- `log_panel.py`: h-full 高度链修复 (+37 行)
- `config_store.py`: data/config.json 路径迁移 (+10 行)

#### 🔧 **后端适配层** (`src/ipo_know/kb_query/`)
- `aliyun_backend.py`: SSE 流式问答实现 (+8 行)
- `volc_backend.py`: reasoning_delta 事件处理 (+4 行)
- `dto.py`: 新增 `ChatStreamEventKind.reasoning_delta` 枚举值

#### 🏗️ **构建与便携化**
- `build.ps1`: 完全重构为 unified onedir build script (+197/-145 行)
- `pack_main.py`: CWD 锚定 (`os.chdir(Path(sys.executable).parent)`)
- `ipo-know.spec`: 清理 onefile 引用，保留 onedir 配置
- `build_onedir.ps1`: 删除（已合并入统一脚本）
- `ipo-know-crawler.spec`: 删除（产物改名后不再需要旧 spec）

---

## 🚀 升级建议

### 对于老用户（v0.1.0 升级至 v0.2.0）

1. **配置文件迁移**：
   - 旧版：%LOCALAPPDATA%\ipo_know\config.json
   - 新版：便携版目录下的 `data/config.json`
   - **操作**: GUI 运行时会自动创建并保存配置
   
2. **数据库路径变化**：
   - 旧版：`%LOCALAPPDATA%\ipo_know\database\ipo_know.db`
   - 新版：便携版目录下的 `data/ipo_know.db`
   - **注意**: 如需迁移历史数据，需备份原数据库文件到新目录

3. **环境变量**：
   - 如果之前使用 `.env` 文件，请复制到便携版目录同级位置
   - 或者直接在 GUI 界面填写配置（推荐新手）

### 对于新用户

1. **下载方式**: GitHub Releases 页面下载最新 `ipo-know.zip`
2. **解压即用**: 解压到任意目录（推荐非系统盘，如 `D:\tools\ipo-know`）
3. **首次运行**: 
   - 双击 `ipo-know.exe`
   - GUI 弹出 → 平台选择（火山/阿里）→ 填写 API Key 和其他配置
   - 点击「保存配置」→ 开始使用知识库同步/检索/问答功能

---

## 📮 反馈渠道

如有任何问题、建议或 bug 报告，欢迎通过以下途径反馈：
- **GitHub Issues**: https://github.com/Elicy04/ipo-know/issues
- **Email**: Elicy04@outlook.com

期待你的反馈，帮助项目持续改进！🚀
