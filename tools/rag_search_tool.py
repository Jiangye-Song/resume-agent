"""RAG Search Tool - Semantic vector search with domain filtering"""

import os
import asyncio
from typing import Optional, List, Dict, Any
from upstash_vector import Index
from .base import Tool, ToolResult


class RAGSearchTool(Tool):
    """
    Performs semantic vector search within a specific domain.
    
    Use this for:
    - General knowledge queries about projects/education/experience
    - Finding conceptually similar items
    - Keyword-based searches
    - Semantic/concept queries like "machine learning projects"
    
    Domains:
    - "project": Work projects and personal projects
    - "education": Academic degrees, certifications, courses
    - "experience": Work experience, internships
    - "fact": General facts about the person
    - "all": Search across all domains
    """
    
    name = "rag_search_by_domain"
    description = """
Performs semantic vector search within a specific domain (project, education, experience, fact, or all).
Use this for general knowledge queries, conceptual searches, or when looking for semantically similar content.
Returns top_k most relevant results sorted by similarity score.
"""
    
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query"
            },
            "domain": {
                "type": "string",
                "enum": ["project", "education", "experience", "fact", "all"],
                "description": "Domain to search within. Use 'all' to search across all domains.",
                "default": "all"
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (1-20)",
                "minimum": 1,
                "maximum": 20,
                "default": 5
            }
        },
        "required": ["query"]
    }
    
    def __init__(self, db_pool=None):
        super().__init__(db_pool)
        self.index = Index(
            url=os.getenv("UPSTASH_VECTOR_REST_URL"),
            token=os.getenv("UPSTASH_VECTOR_REST_TOKEN")
        )
    
    async def execute(
        self, 
        query: str, 
        domain: str = "all", 
        top_k: int = 5
    ) -> ToolResult:
        """
        Execute semantic search with optional domain filtering
        
        Args:
            query: Natural language search query
            domain: Domain to filter by (project, education, experience, fact, all)
            top_k: Number of results to return
            
        Returns:
            ToolResult with matching records sorted by relevance
        """
        try:
            # Build metadata filter if domain specified
            filter_str = None
            if domain != "all":
                filter_str = f"type = '{domain}'"
            
            # Execute vector search
            results = await asyncio.to_thread(
                self.index.query,
                data=query,
                top_k=top_k,
                include_metadata=True,
                filter=filter_str
            )
            
            # Format results - exclude summary, include all necessary fields
            formatted_results = []
            for r in results:
                result_data = {
                    "id": r.id,
                    "score": r.score,
                    "type": r.metadata.get("type", "unknown"),
                    "title": r.metadata.get("title", "Untitled"),
                    "tags": r.metadata.get("tags", []),
                    "priority": r.metadata.get("priority", 3),
                    "facts": r.metadata.get("facts", []),
                    "detail_site": r.metadata.get("detail_site", ""),
                    "additional_url": r.metadata.get("additional_url", []),
                    "start_date": r.metadata.get("start_date"),
                    "end_date": r.metadata.get("end_date")
                }
                formatted_results.append(result_data)
            
            return ToolResult(
                success=True,
                data=formatted_results,
                metadata={
                    "query": query,
                    "domain": domain,
                    "results_count": len(formatted_results)
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                data=[],
                error=f"RAG search failed: {str(e)}"
            )
