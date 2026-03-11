# AI 赋能的智能简历分析系统

一个可直接验收的笔试项目实现：上传 PDF 简历，自动解析文本、提取关键信息，并与岗位 JD 做匹配评分。

## 项目亮点
- 覆盖题目 5 个必选模块，前后端可独立部署。
- 规则抽取 + AI 抽取双通道，保证“无 Key 可用、有 Key 增强”。
- 匹配评分支持分项评分（技能/经验/学历/岗位方向）+ AI 精评分融合。
- Redis 缓存 + 内存 TTL 回退，并复用匹配缓存避免重复计算。
- 前端已支持点击与拖拽上传 PDF，页面展示聚焦业务结果（不展示原始 JSON 代码块）。

## 评分标准对照
| 维度 | 权重 | 当前实现 |
| --- | --- | --- |
| 功能完整性 | 30% | 模块 1~5 全部实现，接口和页面可正常运行 |
| 代码质量 | 25% | API/Service/Utils/Schema 分层，命名清晰，含契约测试与缓存测试 |
| 工程化实践 | 20% | 完整 README、Makefile 统一命令、错误处理、GitHub Pages 自动部署 |
| 技术深度 | 15% | AI 多模型回退与重试、分项评分与融合、分层缓存与跨接口缓存复用 |
| 加分项 | 10% | 求职信息/背景提取、AI 精评分、缓存命中展示、线上可访问前端 |

## 功能覆盖（对应题目模块）

### 模块一：简历上传与解析（必选）
- `POST /api/v1/resumes/parse`
- 支持单个 PDF 上传
- 支持多页 PDF 文本提取（`pypdf`）
- 文本清洗与结构化分段（章节识别）

### 模块二：关键信息提取（必选）
- `POST /api/v1/resumes/extract`
- 必选字段：姓名、电话、邮箱、地址
- 加分字段：求职意向、期望薪资、工作年限、学历背景、项目经历、技能关键词
- 抽取策略：规则抽取（基础保障）+ AI 增强（Gemini/OpenAI）

### 模块三：简历评分与匹配（必选）
- `POST /api/v1/resumes/match`
- `POST /api/v1/jobs/keywords`
- `POST /api/v1/resumes/analyze`（一体化）
- 输出：`final_score`、`heuristic_score`、`ai_score`、分项评分、命中/缺失关键词、优势/短板

### 模块四：结果返回与缓存（必选）
- 全部接口返回结构化 JSON
- 缓存优先 Redis，失败自动回退内存 TTL
- 缓存键：
  - `parse:{resume_id}`
  - `extract:{resume_id}`
  - `match:{resume_id}:{jd_hash}`
  - `analyze:{resume_id}:{jd_hash}`
- `/resumes/analyze` 与 `/resumes/match` 复用 `match` 缓存，避免重复评分

### 模块五：前端页面（必选）
- 目录：`frontend/`
- 支持：点击上传 + 拖拽上传 PDF
- 支持：仅解析 / 仅提取 / 完整分析
- 展示：独立评分区（总分、规则分、AI 分、分项进度条、命中缺失关键词、优势短板）
- 部署：GitHub Pages（工作流已配置）

## 技术选型
- 后端：FastAPI（RESTful）
- PDF 解析：pypdf
- AI 调用：Gemini API + OpenAI-compatible Chat Completions（httpx）
- 缓存：Redis（可选）+ 内存 TTL fallback
- 前端：HTML + CSS + Vanilla JS
- 测试：pytest
- 部署：阿里云 FC（后端）+ GitHub Pages（前端）

## 项目结构
```text
.
├── backend
│   ├── app
│   │   ├── api/routes.py
│   │   ├── core/config.py
│   │   ├── services/
│   │   ├── utils/
│   │   ├── main.py
│   │   └── schemas.py
│   ├── tests
│   ├── Dockerfile
│   ├── fc/s.yaml
│   └── requirements.txt
├── frontend
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── .github/workflows/deploy-pages.yml
├── Makefile
└── README.md
```

## 快速开始（本地）

### 1) 安装依赖
```bash
make install
```

### 2) 启动后端
```bash
make run
```
- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/v1/health`

### 3) 启动前端
```bash
make run-frontend
```
- 前端地址：`http://127.0.0.1:5500`
- `Backend API Base` 填：`http://127.0.0.1:8000/api/v1`

### 4) 测试与检查
```bash
make check
```

## API 概览
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/resumes/parse` | PDF 解析 |
| POST | `/api/v1/resumes/extract` | 关键信息提取 |
| POST | `/api/v1/resumes/match` | 简历与 JD 匹配评分 |
| POST | `/api/v1/resumes/analyze` | 解析+提取+匹配一体化 |
| POST | `/api/v1/jobs/keywords` | JD 关键词分析 |
| GET | `/api/v1/health` | 健康检查 |

## 环境变量说明
见 `backend/.env.example`。

重点配置：
- `AI_PROVIDER=auto|gemini|openai`
- `GEMINI_API_KEY`、`GEMINI_MODEL`（默认 `gemini-2.0-flash`）
- `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`
- `REDIS_URL`
- `CACHE_TTL_SECONDS`
- `MAX_PDF_SIZE_MB`
- `CORS_ORIGINS`（逗号分隔，例如 `http://127.0.0.1:5500,http://localhost:5173`）

Gemini 免费 Key 常见问题：
- `503 UNAVAILABLE`：高峰拥塞，稍后重试。
- `429 quota exceeded`：超出免费额度/速率限制。
- `404 model not found`：模型名不可用，优先 `gemini-2.0-flash`。

## 部署说明

### 后端部署（阿里云 FC）
1. 构建并推送镜像到阿里云 ACR。
2. 修改 `backend/fc/s.yaml` 中镜像地址。
3. 使用 Serverless Devs 执行 `s deploy`。
4. 配置 HTTP Trigger，得到公网 API 地址。

### 前端部署（GitHub Pages）
仓库已提供工作流：`.github/workflows/deploy-pages.yml`。

操作步骤：
1. 将仓库设置为 Public，默认分支 `main`。
2. GitHub -> `Settings` -> `Pages` -> Source 选择 `GitHub Actions`。
3. 推送 `frontend/**` 到 `main`。
4. 在 `Actions` 确认 `Deploy Frontend to GitHub Pages` 成功。
5. 访问：`https://<your-github-username>.github.io/<repo-name>/`
6. 前端填写 `Backend API Base=<你的 FC 地址>/api/v1`
7. 后端 `CORS_ORIGINS` 要包含 `https://<your-github-username>.github.io`

## 验收清单（提交前）
- [ ] `make check` 通过
- [ ] 本地上传 PDF 可完成“解析/提取/完整分析”
- [ ] 同一 PDF + JD 重复请求出现 `cached: true`
- [ ] GitHub Pages 可公网访问
- [ ] README 与实际功能一致

## 提交给面试官的信息
1. GitHub 仓库地址
2. 前端演示地址（GitHub Pages）
3. 姓名与联系方式
4. （可选）后端 FC 地址与 Swagger 地址

## 已知限制
- 当前 PDF 解析依赖文本层，扫描件需 OCR（如 PaddleOCR）。
- AI 增强受外部模型可用性与 Key 配额影响。
