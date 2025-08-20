import os
import json
from upstash_vector import Index
from groq import Groq
import asyncio
from dotenv import load_dotenv

try:
    import asyncpg
except Exception:
    asyncpg = None

# Load environment variables
load_dotenv()

# Constants
VECTOR_DB_TYPE = os.getenv("VECTOR_DB_TYPE")
LLM_PROVIDER = os.getenv("LLM_PROVIDER")
LLM_MODEL = os.getenv("GROQ_MODEL", "deepseek-r1-distill-llama-70b")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
UPSTASH_VECTOR_REST_URL = os.getenv("UPSTASH_VECTOR_REST_URL")
UPSTASH_VECTOR_REST_TOKEN = os.getenv("UPSTASH_VECTOR_REST_TOKEN")
EMBEDDING_MODEL = "MXBAI_EMBED_LARGE_V1"  # Upstash's default embedding model


# Initialize clients
if VECTOR_DB_TYPE != "upstash":
    raise ValueError("Only Upstash Vector is supported in this version")

import httpx

async def upstash_vector_request(endpoint, method="POST", json=None):
    """Make a request to Upstash Vector REST API"""
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {UPSTASH_VECTOR_REST_TOKEN}",
            "Content-Type": "application/json"
        }
        response = await client.request(
            method,
            f"{UPSTASH_VECTOR_REST_URL}/{endpoint}",
            headers=headers,
            json=json
        )
        return response.json()

if LLM_PROVIDER != "groq":
    raise ValueError("Only Groq is supported in this version")

groq_client = Groq(api_key=GROQ_API_KEY)

async def load_projects_from_db():
    """Load projects data from Postgres if DATABASE_URL is set. Returns a list of dicts from projects table."""
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return None
    if asyncpg is None:
        raise RuntimeError('asyncpg not installed; cannot load projects from Postgres')

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch('SELECT data FROM projects ORDER BY id')
        items = []
        for r in rows:
            try:
                d = r['data']
                if isinstance(d, str):
                    d = json.loads(d)
                items.append(d)
            except Exception:
                continue
        return items
    finally:
        await conn.close()


async def load_projects_from_db():
    """Load projects data from Postgres if DATABASE_URL is set. Returns a list of dicts from projects table."""
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return None
    if asyncpg is None:
        raise RuntimeError('asyncpg not installed; cannot load projects from Postgres')

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch('SELECT data FROM projects ORDER BY id')
        items = []
        for r in rows:
            try:
                d = r['data']
                if isinstance(d, str):
                    d = json.loads(d)
                # Mark source so migrate_data can format it correctly
                if isinstance(d, dict):
                    d['_source'] = 'project'
                items.append(d)
            except Exception:
                continue
        return items
    finally:
        await conn.close()

async def get_embedding(text):
    """Get embedding using Upstash's API with MXBAI_EMBED_LARGE_V1 model"""
    try:
        response = await upstash_vector_request("embed", "POST", {
            "input": text,
            "model": EMBEDDING_MODEL
        })
        return response["embedding"]
    except Exception as e:
        print(f"Error getting embedding: {str(e)}")
        raise

async def migrate_data():
    """Migrate data from local JSON to Upstash Vector"""
    print("🔄 Starting migration to Upstash Vector...")
    
    # Load projects only (no foods or JSON fallback)
    project_items = None
    try:
        project_items = await load_projects_from_db()
    except Exception as e:
        print('Warning: failed to load projects from DB:', e)

    if not project_items:
        print('No projects found in DB to migrate. Aborting migration.')
        return

    print(f"🆕 Adding {len(project_items)} project documents to Upstash Vector...")
    index = Index(
        url=UPSTASH_VECTOR_REST_URL,
        token=UPSTASH_VECTOR_REST_TOKEN,
    )
    for item in project_items:
        try:
            title = item.get('title') or item.get('text') or 'Untitled Project'
            summary = item.get('summary') or item.get('text', '')
            enriched_text = f"{title}. {summary}"
            metadata = {
                'title': title,
                'summary': summary,
                'tags': item.get('tags', []),
                'url': item.get('url', ''),
                'source': 'project',
                'data': item,
            }
            pid = f"project:{item.get('id') or title}"

            await asyncio.to_thread(index.upsert, [
                (str(pid), enriched_text, metadata)
            ])
        except Exception as e:
            try:
                ident = item.get('id') if isinstance(item, dict) else str(item)
            except Exception:
                ident = '<unknown>'
            print(f"Error adding project {ident}: {str(e)}")
            continue
    print("✅ Migration completed!")

async def get_completion(prompt):
    """Get completion from Groq"""
    try:
        # groq.Client returns a synchronous object; run it in a thread
        def sync_call():
            return groq_client.chat.completions.create(
                model=LLM_MODEL,  # Using model from environment variable
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )

        response = await asyncio.to_thread(sync_call)
        # response may be a ChatCompletion-like object or dict
        if hasattr(response, "choices"):
            # groq python client: choices[0].message.content
            return response.choices[0].message.content
        if isinstance(response, dict):
            return response.get("choices", [])[0].get("message", {}).get("content")
        return str(response)
    except Exception as e:
        print(f"Error getting completion: {str(e)}")
        raise

async def rag_query(question):
    """RAG query using Upstash Vector and Groq"""
    try:
        # Step 1: Query the vector DB with raw text
        index = Index(
            url=UPSTASH_VECTOR_REST_URL,
            token=UPSTASH_VECTOR_REST_TOKEN,
        )

        # Use the SDK's `data` keyword so Upstash will embed the text automatically
        results = await asyncio.to_thread(
            index.query, data=question, top_k=3, include_metadata=True
        )

        # Step 2: Extract documents (handle both attribute and dict-like responses)
        top_docs = []
        top_ids = []
        for r in results:
            try:
                # SDK may return objects with .metadata/.id
                meta = getattr(r, "metadata", None)
                rid = getattr(r, "id", None)
                if meta is None and isinstance(r, dict):
                    meta = r.get("metadata")
                    rid = r.get("id")
                text = None
                if isinstance(meta, dict):
                    text = meta.get("text")
                elif hasattr(meta, "get"):
                    text = meta.get("text")

                if text is None:
                    # Fallback: if the match itself is a simple string
                    text = str(r)

                top_docs.append(text)
                top_ids.append(str(rid))
            except Exception:
                continue

        if not top_docs:
            print("No results returned from vector DB.")
            return "I couldn't find any relevant documents."

        # Step 3: Show friendly explanation of retrieved documents
        print("\n🧠 Retrieving relevant information to reason through your question...\n")
        for i, doc in enumerate(top_docs):
            print(f"🔹 Source {i + 1} (ID: {top_ids[i]}):")
            print(f"    \"{doc}\"\n")

        print("📚 These seem to be the most relevant pieces of information to answer your question.\n")

        # Step 4: Build prompt from context
        context = "\n".join(top_docs)
        prompt = f"""Use the following context to answer the question.

Context:
{context}

Question: {question}
Answer:"""

        # Step 5: Generate answer with Groq
        answer = await get_completion(prompt)
        return answer.strip()

    except Exception as e:
        print(f"Error in RAG query: {str(e)}")
        return "I apologize, but I encountered an error processing your question. Please try again."


async def main():
    # First migrate data
    await migrate_data()

    # Interactive loop
    print("\n🧠 RAG is ready. Ask a question (type 'exit' to quit):\n")
    while True:
        question = input("You: ")
        if question.lower() in ["exit", "quit"]:
            print("👋 Goodbye!")
            break
        answer = await rag_query(question)
        print("🤖:", answer)

if __name__ == "__main__":
    asyncio.run(main())
