# Ragfood Production Migration Guide

## 1. Migrate from ChromaDB to Upstash Vector

### Prerequisites
- Create an Upstash account and set up a Vector database
- Get your Upstash Vector API credentials

### Implementation Steps
1. Install Upstash Vector SDK:
```bash
pip install upstash-vector
```

2. Update vector store implementation:
```python
from upstash_vector import Index

# Initialize Upstash Vector client
vector_client = Index(
    url="YOUR_UPSTASH_URL",
    token="YOUR_UPSTASH_TOKEN"
)

# Migrate existing embeddings
async def migrate_embeddings():
    # Fetch existing embeddings from ChromaDB
    existing_docs = chroma_client.get_collection("foods").get()
    
    # Upload to Upstash Vector
    for doc, embedding in zip(existing_docs["documents"], existing_docs["embeddings"]):
        await vector_client.upsert(
            vectors=[{
                "id": generate_unique_id(),
                "vector": embedding,
                "metadata": {"text": doc}
            }]
        )
```

## 2. Replace Ollama with Groq

### Prerequisites
- Create a Groq account
- Get API key from Groq dashboard

### Implementation Steps
1. Install Groq SDK:
```bash
pip install groq
```

2. Update the inference code:
```python
from groq import Groq

groq_client = Groq(api_key="YOUR_GROQ_API_KEY")

async def get_completion(prompt):
    try:
        response = await groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",  # Groq's fastest model
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {str(e)}")
        raise
```

## 3. Implement Error Handling & Retry Mechanisms

### Implementation Steps
1. Add retry decorator:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((TimeoutError, ConnectionError))
)
async def robust_api_call(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(f"API call failed: {str(e)}")
        raise
```

## 4. Monitoring & Observability

### Implementation Steps
1. Set up logging with OpenTelemetry:
```python
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider

# Initialize tracing
tracer_provider = TracerProvider()
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# Initialize metrics
meter_provider = MeterProvider()
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter(__name__)

# Create metrics
inference_duration = meter.create_histogram(
    name="inference_duration",
    description="Time taken for inference",
    unit="ms"
)

embedding_requests = meter.create_counter(
    name="embedding_requests",
    description="Number of embedding requests"
)
```

## 5. Cost & Performance Optimization

### Implementation Steps
1. Implement caching:
```python
from redis import Redis
import json

redis_client = Redis(
    host="YOUR_REDIS_HOST",
    port=6379,
    password="YOUR_REDIS_PASSWORD"
)

async def cached_embedding(text):
    cache_key = f"embedding:{hash(text)}"
    
    # Check cache first
    if cached := redis_client.get(cache_key):
        return json.loads(cached)
    
    # Generate new embedding
    embedding = await generate_embedding(text)
    
    # Cache for future use
    redis_client.setex(
        cache_key,
        3600,  # Cache for 1 hour
        json.dumps(embedding)
    )
    
    return embedding
```

2. Implement batch processing where possible:
```python
async def batch_process_embeddings(texts, batch_size=10):
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = await vector_client.embed_batch(batch)
        results.extend(embeddings)
    return results
```

## 6. Vercel Deployment

### Prerequisites
- Install Vercel CLI
- Configure Vercel project

### Environment Configuration
1. Set up environment variables in Vercel:
```
UPSTASH_VECTOR_URL=your_upstash_url
UPSTASH_VECTOR_TOKEN=your_upstash_token
GROQ_API_KEY=your_groq_api_key
REDIS_URL=your_redis_url
REDIS_PASSWORD=your_redis_password
```

2. Update `vercel.json`:
```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/*.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "api/$1"
    }
  ]
}
```

### Deployment Steps
1. Configure build settings:
```bash
vercel build
```

2. Deploy to production:
```bash
vercel deploy --prod
```

## Monitoring Implementation

Set up monitoring dashboards using Vercel Analytics and custom metrics:

1. API Response Times
2. Embedding Generation Latency
3. Vector Search Performance
4. Cache Hit Rates
5. Error Rates and Types
6. Cost per Request

## Cost Management

1. Implement tiered caching:
   - In-memory cache for frequent requests
   - Redis cache for distributed caching
   - Persistent storage for long-term data

2. Set up cost alerts and monitoring:
   - Daily API usage limits
   - Cost thresholds for each service
   - Automated scaling based on usage patterns

## Next Steps

1. Set up CI/CD pipeline with GitHub Actions
2. Implement A/B testing for different models
3. Add performance monitoring and alerting
4. Set up automated backups
5. Create disaster recovery plan