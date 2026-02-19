"""Base classes for AI Agent tools"""

from typing import Dict, Any, Optional
from pydantic import BaseModel


class ToolResult(BaseModel):
    """Result from tool execution"""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class Tool:
    """Base class for all AI Agent tools"""
    
    name: str = "base_tool"
    description: str = "Base tool"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    def __init__(self, db_pool=None):
        """
        Initialize tool with database connection pool
        
        Args:
            db_pool: asyncpg connection pool for database queries
        """
        self.db_pool = db_pool
    
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given arguments
        
        Args:
            **kwargs: Tool-specific arguments
            
        Returns:
            ToolResult with success status, data, and optional error
        """
        raise NotImplementedError(f"Tool {self.name} must implement execute method")
