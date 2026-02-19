"""Filter Tool - Type, tags, and priority filtering"""

from typing import Optional, List, Dict, Any
from .base import Tool, ToolResult


class FilterTool(Tool):
    """
    Filters records by type, tags, priority.
    
    Use this for:
    - Type-specific queries ("show me all projects")
    - Technology stack queries ("Python projects", "React applications")
    - Priority-based filtering (high-priority items)
    - Tag combination queries
    
    Can combine multiple filters together.
    """
    
    name = "filter_records"
    description = """
Filters records by type, tags, and/or priority. Use this for queries about specific 
technologies, types of work, or priority levels. Can match any or all provided tags.
Returns matching records sorted by priority and date.
"""
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "record_type": {
                "type": "string",
                "enum": ["project", "education", "experience", "fact"],
                "description": "Type of record to filter by. Omit to search all types."
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of tags to filter by (e.g., ['Python', 'AI', 'React']). Records matching ANY tag will be returned."
            },
            "tags_match_all": {
                "type": "boolean",
                "description": "If true, record must have ALL tags. If false, record must have ANY tag.",
                "default": False
            },
            "priority_min": {
                "type": "integer",
                "description": "Minimum priority level (1-3, where 3 is highest)",
                "minimum": 1,
                "maximum": 3
            },
            "priority_max": {
                "type": "integer",
                "description": "Maximum priority level (1-3, where 3 is highest)",
                "minimum": 1,
                "maximum": 3
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (1-50)",
                "minimum": 1,
                "maximum": 50,
                "default": 20
            }
        },
        "required": []
    }
    
    async def execute(
        self,
        record_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        tags_match_all: bool = False,
        priority_min: Optional[int] = None,
        priority_max: Optional[int] = None,
        limit: int = 20
    ) -> ToolResult:
        """
        Execute filter query
        
        Args:
            record_type: Type filter (project, education, experience, fact)
            tags: List of tags to match
            tags_match_all: If true, match ALL tags; if false, match ANY tag
            priority_min: Minimum priority (1-3)
            priority_max: Maximum priority (1-3)
            limit: Max results to return
            
        Returns:
            ToolResult with matching records
        """
        try:
            # Build SQL query - exclude summary, include detail_site and additional_url
            query = "SELECT id, type, title, tags, start_date, end_date, priority, facts, detail_site, additional_url FROM records WHERE 1=1"
            params = []
            param_idx = 1
            
            # Add type filter
            if record_type:
                query += f" AND type = ${param_idx}"
                params.append(record_type)
                param_idx += 1
            
            # Add tag filters
            if tags:
                if tags_match_all:
                    # Record must contain ALL tags
                    query += f" AND tags @> ${param_idx}::text[]"
                    params.append(tags)
                else:
                    # Record must contain ANY tag
                    query += f" AND tags && ${param_idx}::text[]"
                    params.append(tags)
                param_idx += 1
            
            # Add priority filters
            if priority_min is not None:
                query += f" AND priority >= ${param_idx}"
                params.append(priority_min)
                param_idx += 1
            
            if priority_max is not None:
                query += f" AND priority <= ${param_idx}"
                params.append(priority_max)
                param_idx += 1
            
            # Sort by priority (high to low), then by date (recent first)
            query += " ORDER BY priority DESC, start_date DESC NULLS LAST"
            
            # Add limit
            query += f" LIMIT ${param_idx}"
            params.append(limit)
            
            # Execute query
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
            
            # Format results - exclude summary
            results = []
            for row in rows:
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
                results.append(result_data)
            
            return ToolResult(
                success=True,
                data=results,
                metadata={
                    "record_type": record_type,
                    "tags": tags,
                    "tags_match_all": tags_match_all,
                    "priority_range": f"{priority_min or 1}-{priority_max or 3}",
                    "results_count": len(results)
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                data=[],
                error=f"Filter query failed: {str(e)}"
            )
