import os
import json
from upstash_vector import Index
from groq import Groq
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
JSON_FILE = "foods.json"
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

# Load data
with open(JSON_FILE, "r", encoding="utf-8") as f:
    food_data = json.load(f)

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
    
    # Add all items (Upstash will handle duplicates)
    new_items = food_data


    if new_items:
        print(f"🆕 Adding {len(new_items)} new documents to Upstash Vector...")
        index = Index(
            url=UPSTASH_VECTOR_REST_URL,
            token=UPSTASH_VECTOR_REST_TOKEN,
        )
        for item in new_items:
            try:
                enriched_text = item["text"]
                if "region" in item:
                    enriched_text += f" This food is popular in {item['region']}."
                if "type" in item:
                    enriched_text += f" It is a type of {item['type']}."
                await asyncio.to_thread(index.upsert, [
                    (str(item["id"]), enriched_text, {
                        "text": item["text"],
                        "region": item.get("region", ""),
                        "type": item.get("type", "")
                    })
                ])
            except Exception as e:
                print(f"Error adding item {item['id']}: {str(e)}")
                continue
        print("✅ Migration completed!")
    else:
        print("✅ All documents already in Upstash Vector.")

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
