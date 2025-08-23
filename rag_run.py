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

# Cache for system prompt to avoid DB hits on every request
_system_prompt_cache = None
_cache_timestamp = 0
CACHE_TTL = 300  # 5 minutes cache

# Default system prompt fallback
DEFAULT_SYSTEM_PROMPT = '''You are a helpful assistant, you should notify the developer to set the system prompt.'''

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

async def ensure_config_table():
    """Ensure config table exists and has default system prompt on startup."""
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL or asyncpg is None:
        print("⚠️  Database not available, using default system prompt")
        return
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            # Create config table if it doesn't exist
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            ''')
            
            # Check if system_prompt exists
            row = await conn.fetchrow("SELECT value FROM config WHERE key = 'system_prompt'")
            if not row:
                # Insert default system prompt
                await conn.execute('''
                    INSERT INTO config (key, value, updated_at) 
                    VALUES ('system_prompt', $1, NOW())
                ''', DEFAULT_SYSTEM_PROMPT)
                print("✅ Created config table and set default system prompt")
            else:
                print("✅ Config table exists with system prompt")
                
        finally:
            await conn.close()
    except Exception as e:
        print(f"⚠️  Failed to initialize config table: {e}, using default system prompt")

async def clear_system_prompt_cache():
    """Clear the system prompt cache to force reload from database on next request."""
    global _system_prompt_cache, _cache_timestamp
    _system_prompt_cache = None
    _cache_timestamp = 0

async def load_system_prompt_from_db():
    """Load system prompt from database with caching. Returns current system prompt."""
    global _system_prompt_cache, _cache_timestamp
    import time
    
    # Check cache first
    current_time = time.time()
    if _system_prompt_cache and (current_time - _cache_timestamp) < CACHE_TTL:
        return _system_prompt_cache
    
    # Try database
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL or asyncpg is None:
        return DEFAULT_SYSTEM_PROMPT
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            # Try to get system prompt from a config table or projects table
            try:
                row = await conn.fetchrow(
                    "SELECT value FROM config WHERE key = 'system_prompt' ORDER BY updated_at DESC LIMIT 1"
                )
                if row and row['value']:
                    prompt = row['value']
                    _system_prompt_cache = prompt
                    _cache_timestamp = current_time
                    return prompt
            except:
                return DEFAULT_SYSTEM_PROMPT
                
        finally:
            await conn.close()
    except Exception as e:
        print(f"Warning: failed to load system prompt from DB: {e}")
    
    # Fallback to default
    _system_prompt_cache = DEFAULT_SYSTEM_PROMPT
    _cache_timestamp = current_time
    return DEFAULT_SYSTEM_PROMPT

async def load_projects_from_db():
    """Load projects data from Postgres if DATABASE_URL is set. Returns a list of dicts from projects table."""
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return None
    if asyncpg is None:
        raise RuntimeError('asyncpg not installed; cannot load projects from Postgres')

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Select all fields including new date and priority fields, ordered by priority desc
        rows = await conn.fetch('''
            SELECT id, title, summary, tags, url, data, start_date, end_date, priority 
            FROM projects 
            ORDER BY priority DESC, id
        ''')
        items = []
        for r in rows:
            try:
                d = r['data']
                if isinstance(d, str):
                    d = json.loads(d)
                # Add database fields to the data object
                if isinstance(d, dict):
                    d['id'] = r['id']
                    d['title'] = r['title'] 
                    d['summary'] = r['summary']
                    d['tags'] = list(r['tags']) if r['tags'] else []
                    d['url'] = r['project_detail_url']
                    d['priority'] = r['priority']
                    if r['start_date']:
                        d['start_date'] = r['start_date'].isoformat()
                    if r['end_date']:
                        d['end_date'] = r['end_date'].isoformat()
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
                'priority': item.get('priority', 3),
                'start_date': item.get('start_date'),
                'end_date': item.get('end_date'),
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
        # Load system prompt dynamically from database
        system_prompt = await load_system_prompt_from_db()
        # groq.Client returns a synchronous object; run it in a thread
        def sync_call():
            # Include a system prompt to orient the assistant
            return groq_client.chat.completions.create(
                model=LLM_MODEL,  # Using model from environment variable
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
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
        error_str = str(e)
        print(f"Error getting completion: {error_str}")
        
        # 检测速率限制错误并提取等待时间
        if "rate_limit_reached" in error_str or "Rate limit reached" in error_str:
            # 尝试提取等待时间
            import re
            time_match = re.search(r'Please try again in ([\d\.]+[ms]?[\d\.]*[sm])', error_str)
            if time_match:
                wait_time = time_match.group(1)
                print(f"\n⚠️  API速率限制提醒 ⚠️")
                print(f"📊 您的Groq API今日token配额已用完")
                print(f"⏰ 请等待 {wait_time} 后再试")
                print(f"💡 提示：可考虑升级到Dev Tier获得更多配额")
                print(f"🔗 升级链接：https://console.groq.com/settings/billing\n")
            else:
                print(f"\n⚠️  API速率限制 - 请稍后再试 ⚠️\n")
        
        raise

async def rag_query(question):
    """RAG query using Upstash Vector and Groq"""
    # Ensure config table exists on first call
    global _system_prompt_cache
    if _system_prompt_cache is None:
        await ensure_config_table()
    
    try:
        # Step 1: Query the vector DB with raw text
        index = Index(
            url=UPSTASH_VECTOR_REST_URL,
            token=UPSTASH_VECTOR_REST_TOKEN,
        )

        # Use the SDK's `data` keyword so Upstash will embed the text automatically
        # Get more results initially to allow for priority filtering
        results = await asyncio.to_thread(
            index.query, data=question, top_k=10, include_metadata=True
        )

        # Step 2: Extract documents and apply priority filtering
        all_results = []
        for r in results:
            try:
                # SDK may return objects with .metadata/.id
                meta = getattr(r, "metadata", None)
                rid = getattr(r, "id", None)
                score = getattr(r, "score", 0)
                
                if meta is None and isinstance(r, dict):
                    meta = r.get("metadata")
                    rid = r.get("id")
                    score = r.get("score", 0)
                
                if isinstance(meta, dict):
                    priority = meta.get("priority", 3)
                    # 从metadata中构建文本内容，包含tags信息
                    title = meta.get("title", "")
                    summary = meta.get("summary", "")
                    tags = meta.get("tags", [])
                    
                    # 构建包含tags的完整文本
                    tags_text = f"[Tags: {', '.join(tags)}]" if tags else ""
                    if title and summary and tags_text:
                        text = f"{title}. {summary} {tags_text}"
                    elif title and summary:
                        text = f"{title}. {summary}"
                    elif title and tags_text:
                        text = f"{title}. {tags_text}"
                    else:
                        text = title or summary or tags_text or "No content available"
                    
                    # 对于优先级为0的结果，将score降低至一半
                    adjusted_score = score / 2 if priority == 0 else score
                    
                    all_results.append({
                        'text': text,
                        'id': str(rid),
                        'priority': priority,
                        'score': adjusted_score,
                        'original_score': score,
                        'metadata': meta
                    })
            except Exception:
                continue

        if not all_results:
            print("No results returned from vector DB.")
            return "I couldn't find any relevant documents."

        # Step 3: Apply new priority filtering logic
        # priority越大，优先级越高（3=最高，2=中，1=低，0=最低）
        # 先取前5个最相关的结果，然后在这5个中按优先级分组
        
        # 先按分数排序，取前5个最相关的结果
        top_5_results = sorted(all_results, key=lambda x: x['score'], reverse=True)[:5]
        
        # 在前5个结果中分别筛选高优先级（>=2）和低优先级（<=1）
        high_priority_filtered = [r for r in top_5_results if r['priority'] >= 2]
        low_priority_filtered = [r for r in top_5_results if r['priority'] <= 1]
        
        print(f"🔍 Debug: Top 5 most relevant results selected")
        print(f"🔍 Debug: Among top 5 - {len(high_priority_filtered)} high-priority (>=2), {len(low_priority_filtered)} low-priority (<=1)")
        
        # 在各自分组内按分数排序
        high_priority_filtered = sorted(high_priority_filtered, key=lambda x: x['score'], reverse=True)
        low_priority_filtered = sorted(low_priority_filtered, key=lambda x: x['score'], reverse=True)
        
        print(f"✅ Using {len(high_priority_filtered)} high-priority results + {len(low_priority_filtered)} low-priority results (all from top 5 most relevant)")
        
        # Step 4: Show friendly explanation of retrieved documents with priority info
        print("\n🧠 Retrieving relevant information to reason through your question...\n")
        
        if high_priority_filtered:
            print("📋 High Priority Sources (Priority 3 = Highest, Priority 2 = Medium):")
            for i, result in enumerate(high_priority_filtered):
                priority = result['priority']
                score = result['score']
                doc = result['text']
                doc_id = result['id']
                
                priority_label = "P3-Highest" if priority == 3 else "P2-Medium"
                print(f"🔹 Source {i + 1} [{priority_label}] (ID: {doc_id}, score={score:.4f}):")
                print(f"    \"{doc}\"\n")
        
        if low_priority_filtered:
            print("📌 Low Priority Backup Source:")
            for i, result in enumerate(low_priority_filtered):
                priority = result['priority']
                score = result['score']
                doc = result['text']
                doc_id = result['id']
                
                print(f"� Backup (ID: {doc_id}, priority={priority}, score={score:.4f}):")
                print(f"    \"{doc}\"\n")

        print("📚 These seem to be the most relevant pieces of information to answer your question.\n")

                # Step 5: Build prompt from context with priority guidance for LLM
        high_priority_context = "\n".join([r['text'] for r in high_priority_filtered]) if high_priority_filtered else ""
        low_priority_context = "\n".join([r['text'] for r in low_priority_filtered]) if low_priority_filtered else ""
        
        # 构建带有优先级指导的上下文
        if high_priority_filtered:
            priority_3_items = [r for r in high_priority_filtered if r['priority'] == 3]
            priority_2_items = [r for r in high_priority_filtered if r['priority'] == 2]
            
            context_with_priority = ""
            if priority_3_items:
                priority_3_context = "\n".join([r['text'] for r in priority_3_items])
                context_with_priority += f"[HIGHEST PRIORITY - Display these first if relevant]:\n{priority_3_context}\n\n"
            
            if priority_2_items:
                priority_2_context = "\n".join([r['text'] for r in priority_2_items])
                context_with_priority += f"[MEDIUM PRIORITY - Display after highest priority items]:\n{priority_2_context}\n\n"
        
        if high_priority_context and low_priority_context:
            prompt = f"""Use the following context to answer the question. When selecting information to display, prioritize items marked as [HIGHEST PRIORITY] over [MEDIUM PRIORITY].

Context:
{context_with_priority.strip()}

Question: {question}

If none of the context above solve the question, you may also reference the following backup context:
{low_priority_context}

Answer:"""
        elif high_priority_context:
            prompt = f"""Use the following context to answer the question. When selecting information to display, prioritize items marked as [HIGHEST PRIORITY] over [MEDIUM PRIORITY].

Context:
{context_with_priority.strip()}

Question: {question}
Answer:"""
        elif low_priority_context:
            prompt = f"""Use the following context to answer the question.

Context:
{low_priority_context}

Question: {question}
Answer:"""
        else:
            prompt = f"""Question: {question}
Answer:"""

        # Step 5: Generate answer with Groq
        answer = await get_completion(prompt)
        return answer.strip()

    except Exception as e:
        error_str = str(e)
        print(f"Error in RAG query: {error_str}")
        
        # 检测速率限制错误
        if "rate_limit_reached" in error_str or "Rate limit reached" in error_str:
            # 尝试提取等待时间
            import re
            time_match = re.search(r'Please try again in ([\d\.]+[ms]?[\d\.]*[sm])', error_str)
            if time_match:
                wait_time = time_match.group(1)
                return f"I apologize, now isn't a great time for me, may you come back in {wait_time}?"
            else:
                return "I apologize, but I encountered an error processing your question. Please try again later."
        
        return "I apologize, but I encountered an error processing your question. Please try again later."


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
