# 学科知识整合智能体

面向 AI 全栈极速黑客松的医学教材整合 Web 应用。当前第一阶段已跑通前后端骨架、教材上传 mock 流程和三栏单页界面。

## 环境依赖

- Python 3.10+
- Node.js 18+

## 后端启动

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --app-dir src/backend --host 127.0.0.1 --port 8000
```

接口：

- `GET /api/health`
- `POST /api/textbooks/upload`
- `GET /api/textbooks`

## 前端启动

```bash
cd src/frontend
npm install
npm run dev
```

默认访问地址：`http://127.0.0.1:5173`

## 配置

复制 `.env.example` 为 `.env` 后按需修改。前端通过 `VITE_API_BASE_URL` 指向后端。

## 数据规则

教材 PDF、上传缓存、向量索引、`.env` 和构建产物已在 `.gitignore` 中排除，不应提交到 GitHub。
