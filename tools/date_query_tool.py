"""Date Query Tool - SQL queries for temporal filtering"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from .base import Tool, ToolResult


class DateQueryTool(Tool):
    """
    Retrieves records sorted by date within a date range.
    
    Use this for:
    - "Most recent" or "latest" queries
    - "Oldest" or "earliest" queries
    - Specific time period queries (e.g., "projects in 2024")
    - Timeline construction
    - Any query involving time/date filtering
    
    Returns records sorted by start_date (DESC by default for recent items)
    """
    
    name = "get_records_by_date"
    description = """
Retrieves records filtered and sorted by date range. Use this for temporal queries like 
'most recent project', 'latest work', 'projects in 2024', etc. Returns records sorted 
by start_date in the specified order (DESC = newest first, ASC = oldest first).
"""
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "record_type": {
                "type": "string",
                "enum": ["project", "education", "experience", "fact"],
                "description": "Type of record to filter by. Omit to search all types."
            },
            "start_date_after": {
                "type": "string",
                "description": "Filter records that started on or after this date (YYYY-MM-DD format)"
            },
            "start_date_before": {
                "type": "string",
                "description": "Filter records that started on or before this date (YYYY-MM-DD format)"
            },
            "end_date_after": {
                "type": "string",
                "description": "Filter records that ended on or after this date (YYYY-MM-DD format)"
            },
            "end_date_before": {
                "type": "string",
                "description": "Filter records that ended on or before this date (YYYY-MM-DD format)"
            },
            "sort_order": {
                "type": "string",
                "enum": ["DESC", "ASC"],
                "description": "Sort order: DESC for newest first (recent), ASC for oldest first",
                "default": "DESC"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (1-50)",
                "minimum": 1,
                "maximum": 50,
                "default": 10
            }
        },
        "required": []
    }
    
    async def execute(
        self,
        record_type: Optional[str] = None,
        start_date_after: Optional[str] = None,
        start_date_before: Optional[str] = None,
        end_date_after: Optional[str] = None,
        end_date_before: Optional[str] = None,
        sort_order: str = "DESC",
        limit: int = 10
    ) -> ToolResult:
        """
        Execute date-based query
        
        Args:
            record_type: Type filter (project, education, experience, fact)
            start_date_after: Records starting on/after this date
            start_date_before: Records starting on/before this date
            end_date_after: Records ending on/after this date
            end_date_before: Records ending on/before this date
            sort_order: DESC (newest first) or ASC (oldest first)
            limit: Max results to return
            
        Returns:
            ToolResult with matching records sorted by date
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
            
            # Add date filters
            if start_date_after:
                query += f" AND start_date >= ${param_idx}"
                params.append(start_date_after)
                param_idx += 1
            
            if start_date_before:
                query += f" AND start_date <= ${param_idx}"
                params.append(start_date_before)
                param_idx += 1
            
            if end_date_after:
                query += f" AND end_date >= ${param_idx}"
                params.append(end_date_after)
                param_idx += 1
            
            if end_date_before:
                query += f" AND end_date <= ${param_idx}"
                params.append(end_date_before)
                param_idx += 1
            
            # Add sorting and limit
            query += f" ORDER BY start_date {sort_order}, priority DESC"
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
                    "sort_order": sort_order,
                    "results_count": len(results),
                    "filters_applied": {
                        "start_date_after": start_date_after,
                        "start_date_before": start_date_before,
                        "end_date_after": end_date_after,
                        "end_date_before": end_date_before
                    }
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                data=[],
                error=f"Date query failed: {str(e)}"
            )
