# 学科知识整合智能体

面向 AI 全栈极速黑客松的医学教材整合 Web 应用。当前第一阶段已跑通前后端骨架、教材上传 mock 流程和三栏单页界面。

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

## 配置

复制 `.env.example` 为 `.env` 后按需修改。

- 后端默认读取 `HOST=0.0.0.0` 和 `PORT=8000`。
- 公网部署平台通常会自动注入 `PORT`，启动命令使用 `python src/backend/run.py` 即可。
- 前端默认 `VITE_API_BASE_URL=/api`，不要在代码中硬编码本机地址。
- 如果前后端分离部署，建议在前端平台配置 rewrite/proxy，把 `/api/*` 转发到后端服务。

## 开发文档

- [任务清单](docs/TODO.md)
- [开发路线图](docs/开发路线图.md)

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
- Docker / docker-compose：后续可作为一键复现方案，用 Nginx 同源代理前端和 `/api`，减少跨域问题。

部署验收时至少检查：

- 后端监听 `0.0.0.0`，端口来自 `PORT`。
- 前端页面请求路径是 `/api/...`。
- 浏览器 Network 面板中 `/api/health`、`/api/textbooks` 能正常返回。
- 仓库不包含 PDF、`.env`、上传缓存、向量索引、`node_modules/`、`dist/`。

## 数据规则

教材 PDF、上传缓存、向量索引、`.env` 和构建产物已在 `.gitignore` 中排除，不应提交到 GitHub。
