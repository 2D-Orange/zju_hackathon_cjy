# TODO

本清单按比赛 P0 闭环优先级拆分，先保证可演示、可复现、可追溯，再补 P1/P2。

## 阶段 1：项目骨架和上传界面

- [x] 建立 FastAPI 后端目录结构。
- [x] 建立 React + Vite + TypeScript 前端目录结构。
- [x] 提供 `GET /api/health`、`POST /api/textbooks/upload`、`GET /api/textbooks`。
- [x] 实现左侧教材上传区、文件列表、mock 解析状态。
- [x] 预留中间知识图谱区域和右侧整合 / RAG / 对话 / 报告 Tab。
- [x] 配置 `.gitignore`，排除 PDF、`textbooks/`、上传缓存、`.env`、`node_modules/`、构建产物。

## 阶段 2：教材解析

- [x] 支持 PDF、Markdown、TXT 的真实解析。
- [x] PDF 使用逐页解析，保留页码映射。
- [x] 识别“第 X 章”等章节标题并生成统一结构。
- [x] 过滤明显页眉页脚，缓存中间结果。
- [x] 前端展示解析状态、章节数量、页数和字数。

## 阶段 3：知识图谱

- [x] 定义知识节点和边的 Pydantic schema。
- [x] 按章节调用 LLM 或 mock fallback 提取知识点。
- [x] 关系类型至少覆盖 `prerequisite`、`parallel`、`contains`、`applies_to` 中三种。
- [x] 接入 Cytoscape.js 或 ECharts Graph 渲染图谱。
- [x] 支持节点点击查看定义、章节、页码、原文出处。

## 阶段 4：跨教材整合

- [ ] 为知识点生成 embedding 候选召回。
- [ ] 基于阈值或 LLM 复核生成 `merge`、`keep`、`remove` 决策。
- [ ] 输出 reason、confidence、affected_nodes、result_node。
- [ ] 展示原始字数、整合后字数和压缩比。
- [ ] 确保整合后内容不超过原始总字数 30%。

## 阶段 5：RAG 问答

- [ ] 以 500-800 字 chunk、50-100 字重叠切分教材。
- [ ] chunk 元数据包含 textbook、chapter、page_start、page_end。
- [ ] 建立向量索引并支持 top-5 检索。
- [ ] 回答只基于检索 chunk，并附教材、章节、页码引用。
- [ ] 找不到依据时固定返回“当前知识库中未找到相关信息”。

## 阶段 6：教师反馈

- [ ] 支持教师询问整合原因。
- [ ] 支持自然语言修改至少一项整合决策。
- [ ] 同一会话保留对话历史。
- [ ] 修改后前端决策列表或图谱实时反映。

## 阶段 7：报告和部署

- [ ] 完成 `docs/需求分析.md`。
- [ ] 完成 `docs/系统设计.md`。
- [ ] 完成 `docs/Agent 架构说明.md`。
- [ ] 完成 `report/整合报告.md`，统计数字来自系统真实输出。
- [ ] 补充部署说明或 Docker/docker-compose。
- [ ] 完成最终演示链路：上传 -> 解析 -> 图谱 -> 整合 -> RAG -> 反馈 -> 报告。
