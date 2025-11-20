# AI Agent Architecture Plan

## Problem Statement

### Current Limitations
1. **Single-Tool RAG**: Current system only performs vector similarity search
   - Cannot handle temporal queries like "most recent project" effectively
   - Vector embeddings don't prioritize recency/temporal relationships
   - No ability to filter by specific domains (projects vs education vs experience)

2. **Limited Query Understanding**: 
   - "Most recent project" relies on keyword matching in embeddings
   - Cannot execute structured queries based on dates, types, or other metadata
   - No multi-step reasoning capability

3. **Inflexible Response Generation**:
   - Single RAG call → single response pattern
   - Cannot combine multiple data sources (vector + SQL + structured filters)
   - No ability to chain operations (e.g., "find recent projects in Python, then explain the most complex one")

## Proposed Solution: Multi-Tool AI Agent

### Architecture Overview

```
User Question
     ↓
AI Agent (LLM with Tool-Calling)
     ↓
 [Decision Layer]
     ↓
┌────────────────────────────────────────┐
│  Available Tools:                      │
│  1. rag_search_by_domain()            │
│  2. get_records_by_date()              │
│  3. get_records_by_type()              │
│  4. search_records_by_tags()           │
│  5. get_record_details()               │
│  6. aggregate_statistics()             │
└────────────────────────────────────────┘
     ↓
Multiple Tool Calls (Sequential/Parallel)
     ↓
Synthesized Response
```

## Implementation Plan

### Phase 1: Tool Infrastructure (Week 1)

#### 1.1 Define Tool Interface
```python
# tools/base.py
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class ToolResult(BaseModel):
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}

class Tool:
    name: str
    description: str
    parameters_schema: Dict
    
    async def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError
```

#### 1.2 Implement Core Tools

**Tool 1: RAG Search by Domain**
```python
# tools/rag_search_tool.py
class RAGSearchTool(Tool):
    name = "rag_search_by_domain"
    description = """
    Performs semantic vector search within a specific domain.
    Use this for:
    - General knowledge queries about projects/education/experience
    - Finding conceptually similar items
    - Keyword-based searches
    
    Domains:
    - "project": Work projects and personal projects
    - "education": Academic degrees, certifications, courses
    - "experience": Work experience, internships
    - "all": Search across all domains
    """
    
    async def execute(self, query: str, domain: str = "all", top_k: int = 5):
        # Filter vector search by metadata.type field
        # Use existing Upstash Vector infrastructure
        pass
```

**Tool 2: Get Records by Date Range**
```python
# tools/date_query_tool.py
class DateQueryTool(Tool):
    name = "get_records_by_date"
    description = """
    Retrieves records sorted by date within a date range.
    Use this for:
    - "Most recent" or "latest" queries
    - "Oldest" or "earliest" queries
    - Specific time period queries (e.g., "projects in 2024")
    - Timeline construction
    
    Returns records sorted by start_date (DESC by default)
    """
    
    async def execute(
        self, 
        record_type: Optional[str] = None,
        start_date_after: Optional[str] = None,
        start_date_before: Optional[str] = None,
        end_date_after: Optional[str] = None,
        end_date_before: Optional[str] = None,
        sort_order: str = "DESC",
        limit: int = 10
    ):
        # Direct SQL query with date filtering
        # SELECT * FROM records 
        # WHERE type = $1 
        #   AND start_date >= $2 
        #   AND start_date <= $3
        # ORDER BY start_date DESC
        # LIMIT $4
        pass
```

**Tool 3: Get Records by Type/Tags**
```python
# tools/filter_tool.py
class FilterTool(Tool):
    name = "filter_records"
    description = """
    Filters records by type, tags, priority.
    Use this for:
    - Type-specific queries ("show me all projects")
    - Technology stack queries ("Python projects")
    - Priority-based filtering
    
    Can combine with other filters.
    """
    
    async def execute(
        self,
        record_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        priority_min: Optional[int] = None,
        limit: int = 20
    ):
        # SQL query with WHERE clauses
        # tags ANY($1::text[]) for tag matching
        pass
```

**Tool 4: Get Record Details**
```python
# tools/detail_tool.py
class DetailTool(Tool):
    name = "get_record_details"
    description = """
    Fetches complete details for a specific record by ID.
    Use this when:
    - You have a record ID from previous tool calls
    - User asks for detailed information about a specific item
    - Need to expand summary with full context
    """
    
    async def execute(self, record_id: str):
        # SELECT * FROM records WHERE id = $1
        pass
```

**Tool 5: Aggregate Statistics**
```python
# tools/stats_tool.py
class StatsTool(Tool):
    name = "get_statistics"
    description = """
    Computes aggregate statistics across records.
    Use this for:
    - "How many projects do I have?"
    - "What are my most used technologies?"
    - "Projects by year"
    - Duration calculations
    """
    
    async def execute(
        self,
        stat_type: str,  # "count", "tags_distribution", "timeline"
        filters: Optional[Dict] = None
    ):
        # Aggregate SQL queries
        # SELECT COUNT(*), type FROM records GROUP BY type
        # SELECT unnest(tags), COUNT(*) FROM records GROUP BY unnest(tags)
        pass
```

### Phase 2: Agent Implementation (Week 2)

#### 2.1 Choose Agent Framework

**Option A: LangGraph (Recommended)**
- Pros: Built for multi-step reasoning, state management, cyclic workflows
- Cons: Additional dependency
- Best for: Complex multi-turn interactions

**Option B: Function Calling with Groq/OpenAI**
- Pros: Native function calling support, simpler implementation
- Cons: Less control over execution flow
- Best for: Single-turn tool selection

**Option C: Custom Agent Loop**
- Pros: Full control, no extra dependencies
- Cons: More code to maintain
- Best for: Learning/customization

**Recommendation**: Start with **Option B (Function Calling)**, migrate to **Option A (LangGraph)** if complex workflows needed.

#### 2.2 Agent Core Implementation

```python
# agent/core.py
from groq import Groq
from typing import List, Dict, Any
import json

class ResumeAgent:
    def __init__(self, tools: List[Tool], llm_client: Groq):
        self.tools = {tool.name: tool for tool in tools}
        self.llm_client = llm_client
        self.conversation_history = []
    
    def get_tools_schema(self) -> List[Dict]:
        """Convert tools to OpenAI function calling format"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema
                }
            }
            for tool in self.tools.values()
        ]
    
    async def execute_tool(self, tool_name: str, arguments: Dict) -> ToolResult:
        """Execute a tool by name with arguments"""
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                error=f"Tool {tool_name} not found"
            )
        
        tool = self.tools[tool_name]
        return await tool.execute(**arguments)
    
    async def run(self, user_query: str, max_iterations: int = 5) -> str:
        """Main agent loop with tool calling"""
        
        # Add user query to conversation
        self.conversation_history.append({
            "role": "user",
            "content": user_query
        })
        
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            
            # Call LLM with available tools
            response = self.llm_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    *self.conversation_history
                ],
                tools=self.get_tools_schema(),
                tool_choice="auto",
                temperature=0.1
            )
            
            message = response.choices[0].message
            
            # Check if LLM wants to call tools
            if message.tool_calls:
                # Execute all tool calls
                tool_results = []
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    
                    result = await self.execute_tool(tool_name, arguments)
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "result": result
                    })
                
                # Add assistant's tool calls to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": message.tool_calls
                })
                
                # Add tool results to history
                for tr in tool_results:
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tr["tool_call_id"],
                        "content": json.dumps(tr["result"].dict())
                    })
                
                # Continue loop to let LLM synthesize response
                continue
            
            # No more tool calls - return final response
            return message.content
        
        return "I apologize, but I couldn't complete your request within the allowed steps."
    
    def get_system_prompt(self) -> str:
        return """You are an intelligent resume assistant with access to tools for querying a resume database.

Your goal is to accurately answer user questions about projects, education, experience, and skills.

Guidelines:
1. For temporal queries ("most recent", "latest", "oldest"), ALWAYS use get_records_by_date tool
2. For semantic/concept queries ("machine learning projects"), use rag_search_by_domain
3. For specific filters (tags, type), use filter_records
4. Combine multiple tools when needed (e.g., filter by date, then get details)
5. Always cite the source (project name, dates) in your response
6. If data is missing or unclear, acknowledge it honestly

Available domains for RAG search:
- "project": Technical projects
- "education": Degrees, certifications
- "experience": Work history
- "all": Search everything
"""
```

#### 2.3 Integration with FastAPI

```python
# main.py modifications
from agent.core import ResumeAgent
from tools.rag_search_tool import RAGSearchTool
from tools.date_query_tool import DateQueryTool
from tools.filter_tool import FilterTool
from tools.detail_tool import DetailTool
from tools.stats_tool import StatsTool

# Initialize agent on startup
agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, agent
    
    # ... existing db_pool initialization ...
    
    # Initialize agent with tools
    tools = [
        RAGSearchTool(db_pool),
        DateQueryTool(db_pool),
        FilterTool(db_pool),
        DetailTool(db_pool),
        StatsTool(db_pool)
    ]
    
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    agent = ResumeAgent(tools=tools, llm_client=groq_client)
    
    print("✅ AI Agent initialized with 5 tools")
    
    yield
    
    # ... existing cleanup ...

@app.post('/api/chat')
async def chat(request: Request):
    """Chat endpoint using AI Agent with tools"""
    body = await request.json()
    question = body.get('question', '')
    
    if not question:
        return JSONResponse({'error': 'question is required'}, status_code=400)
    
    try:
        answer = await agent.run(question)
        return JSONResponse({'answer': answer})
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)
```

### Phase 3: Enhanced Features (Week 3)

#### 3.1 Multi-Domain RAG Architecture

```python
# Update Upstash Vector to use namespaces or metadata filtering
# Current: Single index with all records
# Enhanced: Filter by type in metadata during query

class RAGSearchTool(Tool):
    async def execute(self, query: str, domain: str = "all", top_k: int = 5):
        index = Index(
            url=UPSTASH_VECTOR_REST_URL,
            token=UPSTASH_VECTOR_REST_TOKEN
        )
        
        # Build filter based on domain
        filter_dict = {}
        if domain != "all":
            filter_dict = {"type": domain}
        
        # Query with metadata filter
        results = await asyncio.to_thread(
            index.query,
            data=query,
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict  # Upstash metadata filtering
        )
        
        return ToolResult(
            success=True,
            data=[{
                "id": r.id,
                "score": r.score,
                "title": r.metadata.get("title"),
                "summary": r.metadata.get("summary"),
                "type": r.metadata.get("type")
            } for r in results]
        )
```

#### 3.2 Query Classification

Add a pre-processing step to optimize tool selection:

```python
class QueryClassifier:
    """Classify query intent to guide tool selection"""
    
    TEMPORAL_KEYWORDS = [
        "recent", "latest", "newest", "oldest", "earliest",
        "last year", "in 2024", "when", "timeline"
    ]
    
    SEMANTIC_KEYWORDS = [
        "about", "related to", "similar to", "like",
        "machine learning", "web development", "skills in"
    ]
    
    AGGREGATION_KEYWORDS = [
        "how many", "count", "total", "list all",
        "what technologies", "statistics"
    ]
    
    def classify(self, query: str) -> Dict[str, float]:
        """Return confidence scores for query types"""
        query_lower = query.lower()
        
        return {
            "temporal": sum(kw in query_lower for kw in self.TEMPORAL_KEYWORDS),
            "semantic": sum(kw in query_lower for kw in self.SEMANTIC_KEYWORDS),
            "aggregation": sum(kw in query_lower for kw in self.AGGREGATION_KEYWORDS),
            "detail": "detail" in query_lower or "tell me more" in query_lower
        }
```

#### 3.3 Caching Layer

```python
# Add Redis/in-memory cache for frequent queries
from functools import lru_cache
import hashlib

class CachedTool:
    def __init__(self, tool: Tool, ttl: int = 300):
        self.tool = tool
        self.ttl = ttl
        self.cache = {}
    
    async def execute(self, **kwargs):
        cache_key = hashlib.md5(
            json.dumps(kwargs, sort_keys=True).encode()
        ).hexdigest()
        
        if cache_key in self.cache:
            cached_result, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.ttl:
                return cached_result
        
        result = await self.tool.execute(**kwargs)
        self.cache[cache_key] = (result, time.time())
        return result
```

### Phase 4: Testing & Optimization (Week 4)

#### 4.1 Test Cases

Create comprehensive test suite:

```python
# tests/test_agent.py
import pytest

@pytest.mark.asyncio
async def test_temporal_query():
    """Test: 'What is my most recent project?'"""
    response = await agent.run("What is my most recent project?")
    
    # Should use get_records_by_date tool
    assert "get_records_by_date" in agent.tool_calls_history
    assert response  # Non-empty response

@pytest.mark.asyncio
async def test_semantic_query():
    """Test: 'Projects related to machine learning'"""
    response = await agent.run("Projects related to machine learning")
    
    # Should use rag_search_by_domain tool
    assert "rag_search_by_domain" in agent.tool_calls_history

@pytest.mark.asyncio
async def test_combined_query():
    """Test: 'Most recent Python projects'"""
    response = await agent.run("Show me my most recent Python projects")
    
    # Should use both date filtering and tag filtering
    assert len(agent.tool_calls_history) >= 1

@pytest.mark.asyncio
async def test_aggregation_query():
    """Test: 'How many projects do I have?'"""
    response = await agent.run("How many projects do I have?")
    
    # Should use get_statistics tool
    assert "get_statistics" in agent.tool_calls_history
```

#### 4.2 Performance Metrics

Track and optimize:
- Average response time per query type
- Tool call frequency distribution
- Cache hit rate
- Token usage per query
- User satisfaction (if feedback available)

#### 4.3 Error Handling

```python
class AgentError(Exception):
    """Base exception for agent errors"""
    pass

class ToolExecutionError(AgentError):
    """Tool execution failed"""
    pass

class MaxIterationsError(AgentError):
    """Agent exceeded max iterations"""
    pass

# Add retry logic with exponential backoff
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
async def execute_tool_with_retry(self, tool_name: str, arguments: Dict):
    return await self.execute_tool(tool_name, arguments)
```

## Migration Strategy

### Backward Compatibility

1. **Keep existing `/api/chat` endpoint**
   - Add flag: `use_agent=true/false` (default: false)
   - Gradual rollout to users

2. **Dual mode operation**
   ```python
   @app.post('/api/chat')
   async def chat(request: Request):
       body = await request.json()
       question = body.get('question', '')
       use_agent = body.get('use_agent', False)
       
       if use_agent and agent:
           answer = await agent.run(question)
       else:
           answer = await rag_query(question)  # Legacy
       
       return JSONResponse({'answer': answer})
   ```

3. **A/B Testing**
   - Track performance metrics for both approaches
   - Gradually increase agent usage based on success rate

### Deployment Plan

1. **Week 1**: Implement tools locally, test with direct calls
2. **Week 2**: Implement agent core, test in development
3. **Week 3**: Deploy to staging with `use_agent=false` default
4. **Week 4**: Enable agent for 10% of users, monitor metrics
5. **Week 5**: Full rollout if metrics are positive

## Expected Improvements

### Query Type Performance Comparison

| Query Type | Current Approach | Agent Approach | Expected Improvement |
|-----------|------------------|----------------|---------------------|
| "Most recent project" | ❌ RAG embedding match (poor) | ✅ SQL ORDER BY start_date DESC | **90%+ accuracy** |
| "Python projects" | ⚠️ RAG tag match (okay) | ✅ SQL tag filter + RAG | **50% better precision** |
| "Project about X" | ✅ RAG semantic search (good) | ✅ Same (RAG tool) | **Same quality** |
| "How many projects?" | ❌ Cannot answer | ✅ SQL COUNT(*) | **New capability** |
| "2024 projects in Python" | ❌ Poor match | ✅ SQL date + tag filter | **New capability** |

### Benefits

1. **Accuracy**: Structured queries (dates, counts) use SQL, not embeddings
2. **Flexibility**: Can combine multiple data sources
3. **Extensibility**: Easy to add new tools (GitHub API, LinkedIn, etc.)
4. **Transparency**: Tool calls are logged and debuggable
5. **User Experience**: More natural, conversational interactions

## Cost Considerations

### Token Usage
- **Current**: ~500-1000 tokens per query (prompt + context)
- **Agent**: ~1500-3000 tokens per query (system prompt + tools + iterations)
- **Cost increase**: 2-3x per query
- **Mitigation**: Use cheaper models (llama-3.3-70b vs GPT-4), aggressive caching

### Latency
- **Current**: Single LLM call (~1-2s)
- **Agent**: Multiple LLM calls + tool execution (~2-5s)
- **Mitigation**: Parallel tool execution, streaming responses

## Alternative Approaches

### Option 1: Hybrid Classifier
Instead of full agent, use LLM to classify query type first:
```
Query → Classifier LLM → Route to appropriate function
```
- Pros: Lower cost, faster
- Cons: Less flexible, fixed routing logic

### Option 2: SQL-First Approach
Always query SQL first, use RAG only for semantic expansion:
```
Query → SQL filter → RAG on results → LLM synthesis
```
- Pros: Simpler, more predictable
- Cons: Less intelligent, may miss semantic nuances

### Option 3: Semantic Search + Post-Processing
Keep RAG, add post-processing filters:
```
Query → RAG → Filter results by date/tags → Return
```
- Pros: Minimal changes to existing system
- Cons: Still embedding-dependent, less accurate

**Recommendation**: Go with **full Agent approach** for maximum flexibility and accuracy.

## Open Questions

1. **Tool Selection Strategy**: Should we use query classification hints to guide the LLM?
2. **Conversation Memory**: Should agent maintain context across multiple user messages?
3. **Tool Chaining**: Should tools be able to call other tools directly?
4. **Vercel Deployment**: Function calling works in serverless? (Yes, but need to test)
5. **Streaming**: Can we stream agent reasoning steps to user for transparency?

## Next Steps

1. **Review this plan** with team/stakeholders
2. **Prototype Phase 1** (tools only) to validate approach
3. **Benchmark** current system performance to measure improvements
4. **Decide on agent framework** (LangGraph vs Function Calling)
5. **Create detailed implementation tickets** for each tool

---

## Appendix: Example Agent Traces

### Example 1: "What's my most recent project?"

```
User: What's my most recent project?

Agent Thought: This is a temporal query. I should use the date query tool.

Tool Call: get_records_by_date(record_type="project", sort_order="DESC", limit=1)

Tool Result: [{
  "id": "project-x",
  "title": "AI Resume Agent",
  "start_date": "2024-10-01",
  "summary": "Built an intelligent resume Q&A system..."
}]

Agent Response: Your most recent project is the "AI Resume Agent", which you started 
in October 2024. This project involves building an intelligent resume Q&A system that 
uses RAG and vector search to answer questions about your background.
```

### Example 2: "Show me Python projects from 2024"

```
User: Show me Python projects from 2024

Agent Thought: This combines temporal filtering (2024) and tag filtering (Python). 
I'll use the filter tool with date constraints.

Tool Call: filter_records(
  record_type="project",
  tags=["Python"],
  start_date_after="2024-01-01",
  start_date_before="2024-12-31"
)

Tool Result: [{
  "id": "ai-resume-agent",
  "title": "AI Resume Agent",
  "tags": ["Python", "FastAPI", "RAG"],
  "start_date": "2024-10-01"
}, {
  "id": "data-pipeline",
  "title": "ETL Data Pipeline",
  "tags": ["Python", "PostgreSQL"],
  "start_date": "2024-03-15"
}]

Agent Response: You have 2 Python projects from 2024:

1. **AI Resume Agent** (October 2024)
   - Technologies: Python, FastAPI, RAG
   
2. **ETL Data Pipeline** (March 2024)
   - Technologies: Python, PostgreSQL

Would you like more details about any of these projects?
```

### Example 3: "Tell me about machine learning experience"

```
User: Tell me about machine learning experience

Agent Thought: This is a semantic query. I should use RAG search across projects 
and experience domains.

Tool Call: rag_search_by_domain(
  query="machine learning experience",
  domain="all",
  top_k=5
)

Tool Result: [
  {"id": "ml-internship", "score": 0.92, "type": "experience", ...},
  {"id": "dl-project", "score": 0.89, "type": "project", ...},
  {"id": "ml-course", "score": 0.85, "type": "education", ...}
]

Agent Thought: I found relevant results. Let me get full details for the top matches.

Tool Call: get_record_details(record_id="ml-internship")
Tool Call: get_record_details(record_id="dl-project")

[... results ...]

Agent Response: You have significant machine learning experience across several areas:

**Professional Experience:**
- ML Engineer Intern at XYZ Corp (Summer 2023)
  - Developed recommendation systems using collaborative filtering
  - Improved model accuracy by 15%

**Projects:**
- Deep Learning Image Classifier (2024)
  - Built CNN for medical image analysis
  - Technologies: PyTorch, Python, Docker

**Education:**
- Machine Learning Specialization (Coursera, 2023)

Your ML experience spans both practical implementation and theoretical foundations.
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-20  
**Status**: Proposal - Pending Review
