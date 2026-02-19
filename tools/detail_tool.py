"""Detail Tool - Fetch full record details by ID"""

from typing import Optional
from .base import Tool, ToolResult


class DetailTool(Tool):
    """
    Fetches complete details for a specific record by ID.
    
    Use this when:
    - You have a record ID from previous tool calls
    - User asks for detailed information about a specific item
    - Need to expand summary with full context (detail_site, additional_url)
    """
    
    name = "get_record_details"
    description = """
Fetches complete details for a specific record by ID. Returns all fields including 
detail_site URL and additional_url links. Use this when you need full information 
about a specific record identified in a previous tool call.
"""
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "record_id": {
                "type": "string",
                "description": "The unique ID of the record to fetch (e.g., 'project:ai-resume-agent')"
            }
        },
        "required": ["record_id"]
    }
    
    async def execute(self, record_id: str) -> ToolResult:
        """
        Fetch complete record details
        
        Args:
            record_id: Unique record identifier
            
        Returns:
            ToolResult with full record data
        """
        try:
            # Query for full record - exclude summary
            query = """
                SELECT id, type, title, tags, detail_site, additional_url,
                       start_date, end_date, priority, facts
                FROM records 
                WHERE id = $1
            """
            
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(query, record_id)
            
            if not row:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Record not found: {record_id}"
                )
            
            # Format result with all fields - exclude summary
            result_data = {
                "id": row["id"],
                "type": row["type"],
                "title": row["title"],
                "tags": list(row["tags"]) if row["tags"] else [],
                "priority": row["priority"],
                "facts": list(row["facts"]) if row["facts"] else [],
                "detail_site": row["detail_site"],
                "additional_url": row["additional_url"],
                "start_date": row["start_date"].isoformat() if row["start_date"] else None,
                "end_date": row["end_date"].isoformat() if row["end_date"] else None
            }
            
            return ToolResult(
                success=True,
                data=result_data,
                metadata={
                    "record_id": record_id,
                    "has_detail_site": bool(row["detail_site"]),
                    "has_additional_urls": bool(row["additional_url"])
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to fetch record details: {str(e)}"
            )
