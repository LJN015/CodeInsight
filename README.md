# CodeInsight

CodeInsight 是一个基于 FastAPI 的代码仓库理解助手。它可以克隆 GitHub 仓库、分析项目结构、构建 FAISS 代码索引，并结合检索到的源码上下文回答自然语言问题。

当前示例仓库是 Flask，但整体流程可以用于其他代码仓库。

## 功能

- 克隆 GitHub 仓库到 `repos/`
- 统计仓库文件数量和顶层目录
- 使用 DeepSeek 总结 README
- 加载并切分源码文件
- 在 `indexes/` 中持久化 FAISS 索引
- 优先使用本地 sentence-transformers 向量模型
- 向量模型不可用时回退到 HashingVectorizer
- 混合检索：语义检索 + 关键词重排
- `/ask` 返回答案、置信度、来源、耗时和可选调试上下文
- 提供 Streamlit 前端用于演示

## 技术栈

- FastAPI
- Uvicorn
- OpenAI SDK + DeepSeek API
- sentence-transformers
- FAISS
- LangChain text splitters
- scikit-learn
- Streamlit
- pytest

## 项目结构

```text
CodeInsight/
|-- app.py                     # FastAPI 路由
|-- settings.py                # 路径、环境变量、DeepSeek 客户端
|-- schemas.py                 # 请求模型
|-- code_loader.py             # 源码加载和切分
|-- embedding_service.py       # 向量模型和降级方案
|-- index_store.py             # FAISS 持久化和索引过期检测
|-- retrieval.py               # 查询扩展和混合检索
|-- llm_service.py             # Prompt 和 DeepSeek 调用
|-- frontend.py                # Streamlit 前端
|-- download_embedding_model.py
|-- tests/
|   `-- test_api.py
|-- repos/                     # 克隆的仓库
`-- indexes/                   # 生成的索引
```

## 安装

创建并激活虚拟环境后安装依赖：

```powershell
pip install -r requirements.txt
```

创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_CHAT_MODEL=deepseek-chat
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_LOCAL_ONLY=true
```

首次使用前下载本地向量模型：

```powershell
python download_embedding_model.py --model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

## 启动 API

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8001
```

打开 Swagger 文档：

```text
http://127.0.0.1:8001/docs
```

## 启动前端

先启动 FastAPI 服务，再运行：

```powershell
streamlit run frontend.py
```

Streamlit 通常会打开：

```text
http://localhost:8501
```

## 推荐流程

1. 使用 `POST /clone` 克隆仓库
2. 使用 `GET /repos` 检查本地仓库
3. 使用 `POST /index` 构建索引
4. 使用 `POST /ask` 提问
5. 根据 `confidence` 和 `sources` 判断答案可靠性

示例 `/index` 请求：

```json
{
  "repo_name": "flask",
  "force_rebuild": true
}
```

示例 `/ask` 请求：

```json
{
  "repo_name": "flask",
  "question": "Flask 是如何把 @app.route 注册成 URL 规则的？",
  "top_k": 8,
  "debug": false
}
```

## 主要接口

- `GET /health`：服务、模型和密钥状态
- `GET /repos`：本地仓库列表
- `POST /clone`：克隆 GitHub 仓库
- `GET /analyze`：仓库结构统计
- `GET /summarize`：README 摘要
- `POST /index`：构建或加载 FAISS 索引
- `DELETE /index`：删除指定索引
- `GET /indexes`：索引元数据和过期状态
- `GET /chunks`：预览索引片段
- `POST /search`：检索相关代码片段
- `POST /ask`：检索上下文并调用 DeepSeek 回答

## `/ask` 返回字段

- `answer`：模型回答或降级提示
- `confidence`：基于检索质量估算的可靠性
- `sources`：被引用的代码片段来源
- `timing`：检索、模型调用和总耗时
- `contexts`：当 `debug=true` 时返回原始检索上下文

## 支持的文件类型

CodeInsight 会索引常见源码和文本文件：

```text
.py .js .ts .tsx .jsx .java .go .rs .cpp .c .h .hpp .cs .php .rb .kt .scala .swift
.md .rst .txt .toml .yaml .yml
```

## 测试

运行：

```powershell
pytest
```

测试会检查核心 API 是否可用，并验证 Flask 示例问题能检索到关键源码文件。

## 检索评测

项目提供了 `eval_cases.json` 作为轻量评测集，用于验证固定问题能否召回期望的源码文件。

运行：

```powershell
python evaluate_retrieval.py
```

输出 JSON：

```powershell
python evaluate_retrieval.py --json
```

设置最低通过阈值：

```powershell
python evaluate_retrieval.py --fail-under 0.8
```

评测指标包括：

- `macro_recall`：每个问题召回率的平均值
- `micro_recall`：所有期望文件整体命中率
- `missed_paths`：未命中的期望源码文件

## 当前限制

- 回答质量依赖索引覆盖范围和问题是否具体。
- 通用检索规则已经扩展，但仍无法保证所有仓库、所有问题都完全准确。
- 跨模块架构类问题通常需要提高 `top_k`，并结合 `sources` 判断。
- 当 `confidence` 较低或来源不相关时，应把回答视为线索而不是最终结论。

## 适合演示的问题

```text
Flask 是如何把 @app.route 注册成 URL 规则的？
Flask 配置对象如何从文件、环境变量或对象中加载配置？
Flask 测试客户端如何构造 environ 并模拟 HTTP 请求？
Flask 的应用上下文和请求上下文分别在哪里创建和释放？
```
