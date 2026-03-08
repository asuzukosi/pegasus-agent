from src.tools.base import Tool
from src.tools.data import ToolType, ToolInvocation, ToolResult
from src.config.config import Config
from pydantic import BaseModel, Field   
from ddgs import DDGS
from src.utils.logger import logger

class WebSearchParams(BaseModel):
    query: str = Field(..., description="The query to search for")
    max_results: int = Field(10, ge=1, le=100, description="The maximum number of results to return (default 10, max 100, min 1)")


class WebSearchTool(Tool):
    name: str = "websearch"
    description: str = "Search the web for information. Returns search results with titles, urls and snippets"
    type: ToolType = ToolType.NETWORK
    schema: WebSearchParams = WebSearchParams

    def __init__(self, config: Config) -> None:
        self._config = config

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = WebSearchParams(**invocation.params)
        results = []
        try:
            results = DDGS().text(params.query, region="us-en", safesearch="off", timelimit="y", page=1, backend="auto")
        except Exception as e:
            return ToolResult.error_result(f"Error searching the web with error: {e}")
        if not results:
            return ToolResult.error_result(f"No results found for query: {params.query}")
        
        output_lines = [f'Search results for "{params.query}":']
        for idx, result in enumerate(results[:params.max_results]):
            output_lines.append(f'{idx+1}. Title: {result.get("title")}')
            output_lines.append(f'         URL: {result.get("href")}')
            if result.get("body"):
                output_lines.append(f'         Snippet: {result.get("body")}')
            else:
                output_lines.append(f'         No snippet available')
            output_lines.append('-' * 100)
            output_lines.append('')
        truncated = False
        if len(results) > params.max_results:
            output_lines.append(f'...truncated to {params.max_results} results...')
            truncated = True
        return ToolResult.success_result(output="\n".join(output_lines), truncated=truncated, metadata=dict(results=results[:params.max_results], total_results=len(results)))
    
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error searching the web with error: {e}")