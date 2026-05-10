# 学科知识整合智能体

面向 AI 全栈极速黑客松的医学教材整合 Web 应用。已跑通上传解析、知识图谱、跨教材整合、RAG 问答、教师反馈和报告的完整闭环。

## 环境依赖

- Python 3.10+
- Node.js 18+

## 本地开发启动

后端：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
HOST=0.0.0.0 PORT=8000 .venv/bin/python src/backend/run.py
```

接口：

- `GET /api/health`
- `POST /api/textbooks/upload`
- `GET /api/textbooks`
- `GET /api/textbooks/{textbook_id}`
- `POST /api/graph/build`
- `GET /api/graph/{textbook_id}`
- `POST /api/integration/run`
- `GET /api/integration/decisions`
- `PATCH /api/integration/decisions/{decision_id}`
- `POST /api/rag/index`
- `POST /api/rag/query`
- `GET /api/rag/status`
- `POST /api/chat`
- `GET /api/report/summary`

前端：

```bash
cd src/frontend
npm install
npm run dev
```

默认访问地址：`http://0.0.0.0:5173`。本地开发时前端请求相对路径 `/api`，Vite 会把 `/api` 代理到 `VITE_DEV_API_TARGET`。

如需后端热重载，可使用：

```bash
.venv/bin/uvicorn app.main:app --reload --app-dir src/backend --host 0.0.0.0 --port 8000
```

## Docker 启动（推荐）

```bash
docker compose up -d
```

后端监听 `http://localhost:8000`，前端 `http://localhost:5173`。Docker 模式下前端 `/api` 通过 Vite proxy 转发到后端容器。

## 演示流程

```text
1. 打开 http://localhost:5173，看到三栏界面（左：教材管理 / 中：图谱 / 右：功能面板）
2. 上传 ≥2 本医学教材（PDF/MD/TXT），等待解析完成（列表出现绿色勾）
3. 点击教材 → 中间图谱自动渲染节点和关系
4. 切换到"整合"Tab → 点击"运行整合" → 查看决策列表和压缩比
5. 切换到"RAG"Tab → 点击"建立索引" → 输入问题 → 查看带引用的回答
6. 切换到"对话"Tab → 选择决策 → 发送反馈（如"把这个合并改为保留"） → 查看更新
7. 切换到"报告"Tab → 查看系统汇总统计
```

## 已知限制

- 教材列表、图谱缓存和 RAG 索引存储在进程内存中，服务重启后需重新上传/构建/索引
- 整合决策和对话会话通过 `data/processed/*.json` 持久化，重启后可恢复
- 本地 embedding 使用 hash 算法，语义精度低于真实 embedding 模型
- 教师反馈的意图解析为规则匹配，仅能识别明确的修改关键词

## 配置

复制 `.env.example` 为 `.env` 后按需修改。

- 后端默认读取 `HOST=0.0.0.0` 和 `PORT=8000`。
- 公网部署平台通常会自动注入 `PORT`，启动命令使用 `python src/backend/run.py` 即可。
- 前端默认 `VITE_API_BASE_URL=/api`，不要在代码中硬编码本机地址。
- 如果前后端分离部署，建议在前端平台配置 rewrite/proxy，把 `/api/*` 转发到后端服务。
- 知识图谱默认使用规则 mock fallback，完全基于解析后的章节原文提取。可选 LLM 模式通过 `GRAPH_EXTRACTOR_MODE=llm`、`GRAPH_LLM_BASE_URL`、`GRAPH_LLM_API_KEY`、`GRAPH_LLM_MODEL` 配置；LLM 返回内容仍会校验 `source_text` 是否来自章节原文。
- 跨教材整合默认使用本地轻量 embedding fallback。可选在线 embedding 通过 `INTEGRATION_EMBEDDING_BASE_URL`、`INTEGRATION_EMBEDDING_API_KEY`、`INTEGRATION_EMBEDDING_MODEL` 配置；不配置时不依赖外网。
- RAG 默认使用内存向量索引和本地轻量 embedding fallback，chunk 为 700 字、80 字重叠。可选在线 embedding 通过 `RAG_EMBEDDING_BASE_URL`、`RAG_EMBEDDING_API_KEY`、`RAG_EMBEDDING_MODEL` 配置；可选 OpenAI 兼容问答模型通过 `RAG_LLM_BASE_URL`、`RAG_LLM_API_KEY`、`RAG_LLM_MODEL` 配置。未配置 LLM 时返回基于检索 chunk 的摘录式答案，不使用模型医学常识补全。
- 教师反馈默认使用规则解析 fallback，可解释整合决策 reason、definition、source_text 和教材出处，也可将决策自然语言调整为合并、保留或移除。整合决策与对话会话写入 `data/processed/` 下的本地 JSON store，该目录不会提交到 GitHub。

## 文档

- [README](README.md) — 项目说明与启动指南
- [需求分析](docs/需求分析.md) — 赛题目标、用户角色、P0/P1 功能、验收标准
- [系统设计](docs/系统设计.md) — 架构、数据流、API、存储、容错
- [Agent 架构说明](docs/Agent 架构说明.md) — 模块职责、Mermaid 图、取舍、局限、创新点
- [整合报告](report/整合报告.md) — 系统真实统计数据
- [开发路线图](docs/开发路线图.md) — 分阶段计划
- [任务清单](docs/TODO.md) — 进度跟踪

## 公网部署建议

推荐优先选择能同时托管前端静态文件和后端 API 的平台，或能配置 `/api` 反向代理的平台。

- Render：仓库已提供 `render.yaml`，可在 Render 中选择 Blueprint 部署，自动创建 `zju-hackathon-cjy-api` 和 `zju-hackathon-cjy-web` 两个服务。
  - 后端 Web Service：`pip install -r requirements.txt`，启动命令 `python src/backend/run.py`，健康检查 `/api/health`。
  - 前端 Static Site：`cd src/frontend && npm ci && npm run build`，发布目录 `src/frontend/dist`。
  - 前端保持请求相对路径 `/api`，Render 静态站点 rewrite 会把 `/api/*` 转发到后端服务。
  - 如果 Render 实际分配的后端域名不是 `https://zju-hackathon-cjy-api.onrender.com`，请在前端静态站点的 rewrite 规则中把 `/api/*` 目标改成实际后端地址。
  - 免费实例磁盘是临时的，上传文件和解析结果不适合作为长期存储；比赛演示可现场上传，后续要持久化再加 Persistent Disk 或对象存储。
- 魔搭创空间：适合比赛提交，建议用一个后端服务启动 FastAPI，并用平台静态资源或 Nginx/前端构建产物代理 `/api`。
- Render / Railway / Zeabur：适合部署 FastAPI 后端，启动命令为 `python src/backend/run.py`，平台注入 `PORT`。
- Vercel / Netlify：适合部署前端，但需要配置 rewrite，将 `/api/*` 转发到后端公网地址，保持前端代码继续使用相对 `/api`。
- Docker：仓库已提供 `docker-compose.yml`，一键启动前后端。

部署验收时至少检查：

- 后端监听 `0.0.0.0`，端口来自 `PORT`。
- 前端页面请求路径是 `/api/...`。
- 浏览器 Network 面板中 `/api/health`、`/api/textbooks` 能正常返回。
- 仓库不包含 PDF、`.env`、上传缓存、向量索引、`node_modules/`、`dist/`。

## 数据规则

教材 PDF、上传缓存、向量索引、`.env` 和构建产物已在 `.gitignore` 中排除，不应提交到 GitHub。
