"""Statistics Tool - Aggregate queries and statistics"""

from typing import Optional, Dict, Any, List
from .base import Tool, ToolResult


class StatsTool(Tool):
    """
    Computes aggregate statistics across records.
    
    Use this for:
    - "How many projects do I have?"
    - "What are my most used technologies?"
    - "Projects by year"
    - "Count of records by type"
    - Duration calculations
    - Tag distribution analysis
    """
    
    name = "get_statistics"
    description = """
Computes aggregate statistics across records. Supports counting records, analyzing tag 
distributions, grouping by year, and computing duration statistics. Use this for 
numerical queries and data analysis questions.
"""
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "stat_type": {
                "type": "string",
                "enum": ["count", "tags_distribution", "timeline", "types_distribution"],
                "description": """
Type of statistic to compute:
- count: Total count of records (with optional filters)
- tags_distribution: Count of records for each tag (most used technologies)
- timeline: Group records by start year
- types_distribution: Count of records by type (project, education, etc.)
"""
            },
            "record_type": {
                "type": "string",
                "enum": ["project", "education", "experience", "fact"],
                "description": "Filter by record type before computing statistics"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by tags before computing statistics"
            },
            "start_year": {
                "type": "integer",
                "description": "Filter records starting from this year"
            },
            "end_year": {
                "type": "integer",
                "description": "Filter records up to this year"
            },
            "top_n": {
                "type": "integer",
                "description": "For distribution stats, return only top N results",
                "minimum": 1,
                "maximum": 50,
                "default": 10
            }
        },
        "required": ["stat_type"]
    }
    
    async def execute(
        self,
        stat_type: str,
        record_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        top_n: int = 10
    ) -> ToolResult:
        """
        Execute statistics query
        
        Args:
            stat_type: Type of statistic (count, tags_distribution, timeline, types_distribution)
            record_type: Filter by type
            tags: Filter by tags
            start_year: Filter by start year (>=)
            end_year: Filter by end year (<=)
            top_n: For distributions, return top N results
            
        Returns:
            ToolResult with computed statistics
        """
        try:
            # Build base WHERE clause for filters
            where_clauses = []
            params = []
            param_idx = 1
            
            if record_type:
                where_clauses.append(f"type = ${param_idx}")
                params.append(record_type)
                param_idx += 1
            
            if tags:
                where_clauses.append(f"tags && ${param_idx}::text[]")
                params.append(tags)
                param_idx += 1
            
            if start_year:
                where_clauses.append(f"EXTRACT(YEAR FROM start_date) >= ${param_idx}")
                params.append(start_year)
                param_idx += 1
            
            if end_year:
                where_clauses.append(f"EXTRACT(YEAR FROM start_date) <= ${param_idx}")
                params.append(end_year)
                param_idx += 1
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Execute appropriate query based on stat_type
            async with self.db_pool.acquire() as conn:
                if stat_type == "count":
                    query = f"SELECT COUNT(*) as count FROM records WHERE {where_clause}"
                    row = await conn.fetchrow(query, *params)
                    result_data = {"count": row["count"]}
                
                elif stat_type == "tags_distribution":
                    query = f"""
                        SELECT unnest(tags) as tag, COUNT(*) as count
                        FROM records 
                        WHERE {where_clause}
                        GROUP BY tag
                        ORDER BY count DESC
                        LIMIT ${param_idx}
                    """
                    params.append(top_n)
                    rows = await conn.fetch(query, *params)
                    result_data = {
                        "tags": [{"tag": row["tag"], "count": row["count"]} for row in rows],
                        "total_unique_tags": len(rows)
                    }
                
                elif stat_type == "timeline":
                    query = f"""
                        SELECT 
                            EXTRACT(YEAR FROM start_date)::integer as year,
                            COUNT(*) as count,
                            array_agg(title ORDER BY start_date DESC) as titles
                        FROM records 
                        WHERE {where_clause} AND start_date IS NOT NULL
                        GROUP BY year
                        ORDER BY year DESC
                        LIMIT ${param_idx}
                    """
                    params.append(top_n)
                    rows = await conn.fetch(query, *params)
                    result_data = {
                        "timeline": [
                            {
                                "year": row["year"],
                                "count": row["count"],
                                "titles": list(row["titles"])
                            } 
                            for row in rows
                        ]
                    }
                
                elif stat_type == "types_distribution":
                    query = f"""
                        SELECT type, COUNT(*) as count
                        FROM records 
                        WHERE {where_clause}
                        GROUP BY type
                        ORDER BY count DESC
                    """
                    rows = await conn.fetch(query, *params)
                    result_data = {
                        "types": [{"type": row["type"], "count": row["count"]} for row in rows]
                    }
                
                else:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"Unknown stat_type: {stat_type}"
                    )
            
            return ToolResult(
                success=True,
                data=result_data,
                metadata={
                    "stat_type": stat_type,
                    "filters": {
                        "record_type": record_type,
                        "tags": tags,
                        "start_year": start_year,
                        "end_year": end_year
                    }
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Statistics query failed: {str(e)}"
            )
