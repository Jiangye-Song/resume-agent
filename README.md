Here’s a clear, beginner-friendly `README.md` for your RAG project, designed to explain what it does, how it works, and how someone can run it from scratch.

---

## 📄 `README.md`

````markdown
# 🧠 RAG-Food: Simple Retrieval-Augmented Generation with ChromaDB + Ollama

This is a **minimal working RAG (Retrieval-Augmented Generation)** demo using:

- ✅ Local LLM via [Ollama](https://ollama.com/)
- ✅ Local embeddings via `mxbai-embed-large`
- ✅ [ChromaDB](https://www.trychroma.com/) as the vector database
- ✅ A simple food dataset in JSON (Indian foods, fruits, etc.)

---

## 🎯 What This Does

This app allows you to ask questions like:

- “Which Indian dish uses chickpeas?”
- “What dessert is made from milk and soaked in syrup?”
- “What is masala dosa made of?”

It **does not rely on the LLM’s built-in memory**. Instead, it:

1. **Embeds your custom text data** (about food) using `mxbai-embed-large`
2. Stores those embeddings in **ChromaDB**
3. For any question, it:
   - Embeds your question
   - Finds relevant context via similarity search
   - Passes that context + question to a local LLM (`llama3.2`)
4. Returns a natural-language answer grounded in your data.

---

## 📦 Requirements

### ✅ Software

- Python 3.8+
- Ollama installed and running locally
- ChromaDB installed

### ✅ Ollama Models Needed

Run these in your terminal to install them:

```bash
ollama pull llama3.2
ollama pull mxbai-embed-large
````

> Make sure `ollama` is running in the background. You can test it with:
>
> ```bash
> ollama run llama3.2
> ```

---

## 🛠️ Installation & Setup

### 1. Clone or download this repo

```bash
git clone https://github.com/yourname/rag-food
cd rag-food
```

### 2. Install Python dependencies

```bash
pip install chromadb requests
```

### 3. Run the RAG app

```bash
python rag_run.py
```

If it's the first time, it will:

* Create `foods.json` if missing
* Generate embeddings for all food items
* Load them into ChromaDB
* Run a few example questions

---

## 📁 File Structure

```
rag-food/
├── rag_run.py       # Main app script
├── foods.json       # Food knowledge base (created if missing)
├── README.md        # This file
```

---

## 🧠 How It Works (Step-by-Step)

1. **Data** is loaded from `foods.json`
2. Each entry is embedded using Ollama's `mxbai-embed-large`
3. Embeddings are stored in ChromaDB
4. When you ask a question:

   * The question is embedded
   * The top 1–2 most relevant chunks are retrieved
   * The context + question is passed to `llama3.2`
   * The model answers using that info only

---

## 🔍 Try Custom Questions

You can update `rag_run.py` to include your own questions like:

```python
print(rag_query("What is tandoori chicken?"))
print(rag_query("Which foods are spicy and vegetarian?"))
```

---

## 🚀 Next Ideas

* Swap in larger datasets (Wikipedia articles, recipes, PDFs)
* Add a web UI with Gradio or Flask
* Cache embeddings to avoid reprocessing on every run

---

## 👨‍🍳 Credits

Made by Callum using:

* [Ollama](https://ollama.com)
* [ChromaDB](https://www.trychroma.com)
* [mxbai-embed-large](https://ollama.com/library/mxbai-embed-large)
* Indian food inspiration 🍛

---

## 手动触发 Upsert（GitHub Actions）与本地运行说明

你可以通过两种方式把 `projects` 表的数据上载到 Upstash Vector（或重新执行 upsert）：

1) 在 GitHub 上手动触发（推荐，用于远端 agent / CI）

- 仓库已包含一个手动触发的 Actions workflow：`.github/workflows/upsert.yml`。
- 在使用之前，请在仓库 Settings → Secrets 中添加下列 secrets：
  - `DATABASE_URL`（Neon/Postgres 连接字符串）
  - `UPSTASH_VECTOR_REST_URL`
  - `UPSTASH_VECTOR_REST_TOKEN`
  - 可选：`GROQ_API_KEY`（如果迁移逻辑需要调用 LLM）
  - 可选：`MIGRATION_KEY`（如果你在 serverless endpoint 中启用了密钥校验）

- 在 GitHub 仓库页面，进入 Actions → 选择 “Upsert Projects to Vector” workflow → 点击 `Run workflow` 即可手动运行。

2) 在本地手动运行（备用或调试用）

- 在本地环境中，请确保安装依赖并把必要的环境变量加入你的 shell（或放入 `.env` 文件）。例如在 PowerShell 中：

```powershell
python -m pip install -r requirements.txt
$env:DATABASE_URL = "your_database_url"
$env:UPSTASH_VECTOR_REST_URL = "https://..."
$env:UPSTASH_VECTOR_REST_TOKEN = "xxxxx"
# 可选
$env:GROQ_API_KEY = "xxxxx"
python upsert_projects_to_vector.py
```

- 脚本 `upsert_projects_to_vector.py` 会调用仓库中的迁移工具（`migrate_utils.py`），并在控制台输出上载统计（例如：总条目、已 upsert 数量、错误数）。

小提示：如果你想先预览将要 upsert 的内容（dry-run），我可以为 `upsert_projects_to_vector.py` 添加一个 `--dry-run` 选项，打印出 enriched_text 和 metadata，而不实际调用 Upstash。

---

如果你需要我同时把 `--dry-run` 选项添加到 upsert 脚本，或把 workflow 改成可以选择只 upsert 指定 project id 的形式，告诉我你想要的参数，我会继续实现.
````

