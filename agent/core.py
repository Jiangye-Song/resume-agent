"""AI Agent Core - ResumeAgent with tool calling loop"""

from groq import Groq
from typing import List, Dict, Any
import json
import logging
from tools.base import Tool, ToolResult

# Set up logging
logger = logging.getLogger(__name__)


class ResumeAgent:
    """
    AI Agent that uses LLM function calling to intelligently select and execute tools.
    
    The agent maintains conversation history and can make multiple tool calls in a loop
    until it has enough information to answer the user's question.
    """
    
    def __init__(self, tools: List[Tool], llm_client: Groq):
        """
        Initialize the Resume Agent
        
        Args:
            tools: List of Tool instances available to the agent
            llm_client: Groq client for LLM inference
        """
        self.tools = {tool.name: tool for tool in tools}
        self.llm_client = llm_client
        self.conversation_history = []
        self.tool_calls_history = []  # For debugging/testing
        
        logger.info(f"✅ ResumeAgent initialized with {len(self.tools)} tools: {list(self.tools.keys())}")
    
    def get_tools_schema(self) -> List[Dict]:
        """
        Convert tools to OpenAI function calling format
        
        Returns:
            List of tool schemas compatible with Groq/OpenAI function calling
        """
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
        """
        Execute a tool by name with arguments
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments for the tool
            
        Returns:
            ToolResult from tool execution
        """
        if tool_name not in self.tools:
            logger.error(f"❌ Tool not found: {tool_name}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool {tool_name} not found"
            )
        
        tool = self.tools[tool_name]
        logger.info(f"🔧 Executing tool: {tool_name} with args: {arguments}")
        
        try:
            result = await tool.execute(**arguments)
            logger.info(f"✅ Tool {tool_name} completed: success={result.success}")
            
            # Track tool calls for debugging
            self.tool_calls_history.append(tool_name)
            
            return result
        except Exception as e:
            logger.error(f"❌ Tool {tool_name} failed: {str(e)}")
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool execution error: {str(e)}"
            )
    
    async def run(self, user_query: str, max_iterations: int = 5) -> str:
        """
        Main agent loop with tool calling
        
        Args:
            user_query: User's question/request
            max_iterations: Maximum number of agent loop iterations
            
        Returns:
            Final response string from the agent
        """
        # Reset for new query
        self.conversation_history = []
        self.tool_calls_history = []
        
        # Add user query to conversation
        self.conversation_history.append({
            "role": "user",
            "content": user_query
        })
        
        logger.info(f"🤖 Agent started processing: '{user_query[:100]}...'")
        
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"📍 Agent iteration {iteration}/{max_iterations}")
            
            try:
                # Call LLM with available tools
                response = self.llm_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": self.get_system_prompt()},
                        *self.conversation_history
                    ],
                    tools=self.get_tools_schema(),
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=2000
                )
                
                message = response.choices[0].message
                
                # Check if LLM wants to call tools
                if message.tool_calls:
                    logger.info(f"🔧 LLM requested {len(message.tool_calls)} tool call(s)")
                    
                    # Execute all tool calls
                    tool_results = []
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError as e:
                            logger.error(f"❌ Failed to parse tool arguments: {e}")
                            arguments = {}
                        
                        result = await self.execute_tool(tool_name, arguments)
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "result": result
                        })
                    
                    # Add assistant's tool calls to history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })
                    
                    # Add tool results to history
                    for tr in tool_results:
                        result_dict = tr["result"].dict()
                        self.conversation_history.append({
                            "role": "tool",
                            "tool_call_id": tr["tool_call_id"],
                            "content": json.dumps(result_dict)
                        })
                    
                    # Continue loop to let LLM synthesize response
                    continue
                
                # No more tool calls - return final response
                final_response = message.content or "I apologize, but I couldn't generate a response."
                logger.info(f"✅ Agent completed after {iteration} iteration(s)")
                logger.info(f"📊 Tools used: {self.tool_calls_history}")
                
                return final_response
                
            except Exception as e:
                logger.error(f"❌ Agent error in iteration {iteration}: {str(e)}")
                return f"I apologize, but I encountered an error: {str(e)}"
        
        # Max iterations reached
        logger.warning(f"⚠️ Agent reached max iterations ({max_iterations})")
        return "I apologize, but I couldn't complete your request within the allowed steps. Please try rephrasing your question or breaking it into smaller parts."
    
    def get_system_prompt(self) -> str:
        """
        Get the system prompt that guides the agent's behavior
        
        Returns:
            System prompt string
        """
        return """You are an intelligent resume assistant with access to tools for querying a resume database.

Your goal is to accurately answer user questions about projects, education, experience, and skills.

**Available Tools:**
1. **rag_search_by_domain**: Semantic vector search for conceptual/keyword queries
2. **get_records_by_date**: SQL date queries for temporal filtering (most recent, latest, oldest, by year)
3. **filter_records**: SQL filtering by type, tags, priority
4. **get_record_details**: Fetch full details for a specific record by ID
5. **get_statistics**: Compute counts, distributions, timelines

**Tool Selection Guidelines:**

1. **Temporal Queries** ("most recent", "latest", "newest", "oldest", "in 2024"):
   → ALWAYS use `get_records_by_date` tool
   → Example: "What's my most recent project?" → get_records_by_date(record_type="project", sort_order="DESC", limit=1)

2. **Semantic/Concept/Qualitative Queries** ("machine learning projects", "about X", "challenging", "complex", "impressive", "best"):
   → Use `rag_search_by_domain` tool for broad semantic search
   → For quality/difficulty questions, search broadly then analyze the facts
   → Example: "Projects about AI" → rag_search_by_domain(query="AI projects", domain="project")
   → Example: "Most challenging problem" → rag_search_by_domain(query="challenging complex difficult problem solving", domain="all", top_k=10) then analyze facts

3. **Technology/Tag Queries** ("Python projects", "React apps", "projects with Docker"):
   → Use `filter_records` tool
   → Example: "Python projects" → filter_records(tags=["Python"])

4. **Statistical Queries** ("how many", "count", "distribution", "most used"):
   → Use `get_statistics` tool
   → Example: "How many projects?" → get_statistics(stat_type="count", record_type="project")

5. **Combined Queries** ("recent Python projects", "2024 AI work"):
   → Combine tools: Use date + filter, or date + tags in filter_records
   → Example: "Recent Python projects" → filter_records(tags=["Python"], sort by date) OR get_records_by_date + filter results

6. **Detail Expansion**:
   → After finding relevant records, use `get_record_details` to fetch full information
   → Use this when you need to see detail_site URL or additional_url links

**Response Guidelines:**
- Always cite sources (project names, dates, types)
- Be conversational and natural in tone
- Format lists and dates clearly
- Include relevant facts from the records - these contain key details about complexity, achievements, and technical challenges
- If multiple records match, prioritize by priority level (3=highest) and recency
- When analyzing "challenging", "complex", or "impressive" work, look at the facts field for details about technical difficulty, scale, and impact
- Use detail_site URLs to provide links for more information

**Important:**
- For "most recent" or "latest" queries, NEVER use rag_search - use get_records_by_date
- For qualitative queries ("challenging", "best", "impressive"), use RAG search with broader terms, then analyze the facts
- Facts field contains the detailed information about what makes each project significant
- If no direct match, use semantic search with related keywords and examine facts to infer difficulty/complexity
- Combine tools when needed to answer complex queries accurately
"""
    
    def reset_conversation(self):
        """Reset conversation history for a new query"""
        self.conversation_history = []
        self.tool_calls_history = []
