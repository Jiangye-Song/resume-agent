from flask import Flask, request, jsonify, send_from_directory
import asyncio
import os

app = Flask(__name__, static_folder='frontend', static_url_path='')

# Import rag_query from rag_run. If rag_run cannot be imported because of
# missing environment variables or optional dependencies, provide a fallback
# async rag_query that returns a helpful message so the frontend can still run.
try:
    from rag_run import rag_query  # type: ignore
    from rag_run import migrate_data  # type: ignore
except Exception as e:
    async def rag_query(question: str) -> str:
        return (
            "RAG backend is not available.\n"
            "Failed to import rag_run or initialize vector/LLM clients.\n"
            f"Error: {str(e)}\n\n"
            "To enable the full backend, set the required environment variables:"
            " UPSTASH_VECTOR_REST_URL, UPSTASH_VECTOR_REST_TOKEN, GROQ_API_KEY, VECTOR_DB_TYPE=upstash, LLM_PROVIDER=groq\n"
            "Then install dependencies from requirements.txt and restart the server."
        )


    def run_startup_migration():
        """Run migrate_data synchronously at startup if available."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # migrate_data may be async and handle Upstash upserts
            loop.run_until_complete(migrate_data())
            print('Startup migration completed')
        except Exception as exc:
            print('Startup migration failed:', exc)



# Migration endpoints removed: use serverless endpoint at api/upsert-projects.py


@app.route('/')
def index():
    return send_from_directory('frontend', 'index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    question = data.get('question', '')
    if not question:
        return jsonify({'error': 'question is required'}), 400

    # Run rag_query in asyncio loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        answer = loop.run_until_complete(rag_query(question))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'answer': answer})


if __name__ == '__main__':
    # NOTE: migration is no longer run automatically on startup.
    # To embed projects into Upstash Vector, either run the script:
    #   python upsert_projects_to_vector.py
    # or call the HTTP endpoint POST /api/upsert-projects (see route below).

    port = int(os.environ.get('PORT', 7860))
    app.run(host='0.0.0.0', port=port, debug=True)
