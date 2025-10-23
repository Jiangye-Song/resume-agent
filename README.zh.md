# 🧾 Resume Agent — 简明说明

**语言:** [English](README.md) | [简体中文](README.zh.md)

这是一个小型的 RAG / resume assistant 项目（简称 Resume Agent）。
核心想法：把结构化的项目或简历信息（保存在 Neon/Postgres 的 `projects` 表）转为向量并保存在 Upstash Vector，前端/Serverless 在查询时检索相关内容并由 LLM 生成基于数据的回答。

本仓库包含：
- 数据读取与迁移工具：`migrate_utils.py`（可被 CLI、CI、serverless 调用）
- 本地 upsert 脚本：`upsert_projects_to_vector.py`（可本地手动运行或在 CI 中执行）
- 本地开发用前端/服务：`app.py` 与 `frontend/`（简单聊天 UI，用于本地开发）
- Serverless endpoint（可部署到 Vercel）：`api/upsert-projects.py`（用于触发一次性 upsert）

## 主要功能

- 从 `projects` 表读取项目/简历信息并构建用于向量化的文本与 metadata
- 将构建好的文档上载（upsert）到 Upstash Vector
- 提供本地 demo 前端（chat UI）用于对接已部署的向量检索 + LLM

---

## 快速开始（本地开发）

1. 克隆仓库并进入目录：

```powershell
git clone <your-repo-url>
cd resume_agent
```

2. 安装依赖（推荐使用 venv）：

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

3. 准备环境变量（示例 `.env` 或 PowerShell）：

必要环境变量：

- `DATABASE_URL` — Neon/Postgres 连接字符串（例如：postgresql://...）
- `UPSTASH_VECTOR_REST_URL` — Upstash Vector REST API URL
- `UPSTASH_VECTOR_REST_TOKEN` — Upstash Vector REST token
- `VECTOR_DB_TYPE` — 默认为 `upstash`

可选（视你使用 LLM 的方式而定）：

- `GROQ_API_KEY`（如果使用 Groq）
- `MIGRATION_KEY`（如果你想在 serverless endpoint 使用密钥保护）

在 PowerShell 的临时示例：

```powershell
$env:DATABASE_URL = "postgresql://user:pw@host:port/dbname"
$env:UPSTASH_VECTOR_REST_URL = "https://..."
$env:UPSTASH_VECTOR_REST_TOKEN = "xxxx"
```

4. （可选）初始化/填充示例数据到 `projects` 表：

如果你需要快速填充示例项目，运行仓库中的 `db_seed_projects.py`（确保 `DATABASE_URL` 已设置）：

```powershell
python db_seed_projects.py
```

5. 本地运行 upsert（把 `projects` 表上载到 Upstash Vector）：

```powershell
python upsert_projects_to_vector.py
```

脚本会读取数据库并调用 `migrate_utils` 中的逻辑，上载文档到 Upstash，并在控制台打印统计信息（总条目、已 upsert、错误数）。

6. 启动本地前端（开发用）

```powershell
python app.py
# 然后在浏览器打开 http://127.0.0.1:5000
```

---

## 在 GitHub Actions 上手动触发 upsert

仓库已包含一个手动触发的 workflow：`.github/workflows/upsert.yml`，用于在 CI 中执行 `upsert_projects_to_vector.py`。

使用步骤：

1. 在仓库 Settings → Secrets 中添加：
   - `DATABASE_URL`
   - `UPSTASH_VECTOR_REST_URL`
   - `UPSTASH_VECTOR_REST_TOKEN`
   - 可选：`GROQ_API_KEY`, `MIGRATION_KEY`

2. 在 GitHub 仓库页面，打开 Actions → 选择 "Upsert Projects to Vector" → 点击 `Run workflow`。

该 workflow 会 checkout、安装依赖并运行 `python upsert_projects_to_vector.py`（你可以在后续把 workflow 改为接受参数，例如 `--dry-run` 或 `project_id`）。

---

## Serverless / 部署 注意事项

- `api/upsert-projects.py` 是一个 FastAPI 的 serverless endpoint（适用于 Vercel），用于手动触发一次 upsert。Serverless 通常不适合长时间运行的批量任务（超时限制），因此建议把大规模或定期的 upsert 放在 CI / Agent 中运行。
- 如果你把前端部署到 Vercel（静态 + serverless 读 API），请确保 Upstash 与 Postgres 是可访问的（Vercel 应配置相应 Secrets），且上载动作由 CI 或定期 agent 执行。

---

## 调试与扩展建议

- dry-run：我可以为 `upsert_projects_to_vector.py` 添加 `--dry-run` 标志，打印出待上载的 enriched_text 与 metadata，而不进行写入。这个对内容审核非常有用。
- 分批与重试：如果项目数量很多，应在迁移逻辑中采用批处理与重试策略（已在 `migrate_utils.py` 中预留扩展点）。
- id 命名空间：迁移时使用了 namespaced id（例如 `project:<id>`）以避免与其它数据集冲突。

---

## 开发者提示

- 代码入口：`migrate_utils.py`（迁移逻辑），`upsert_projects_to_vector.py`（CLI），`api/upsert-projects.py`（serverless endpoint），`app.py`（本地前端）。
- 若需我把 `--dry-run`、按 project id upsert 或 Actions 输入参数化的功能实现到 workflow，请告诉我你想要的参数与默认行为，我会继续实现并验证。

---

如果你需要我现在就：

1) 为 `upsert_projects_to_vector.py` 添加 `--dry-run`；
2) 让 workflow 支持 `project_id` 或 `dry-run` 参数；
3) 把本地前端改为调用 serverless read API（代替本地 rag 查询），

告诉我序号，我会继续实现并做一次本地验证（语法检查 / 快速运行）。