from src.tools.base import Tool
from src.tools.data import ToolType, ToolInvocation, ToolResult
from src.config.config import Config
from pydantic import BaseModel, Field
from urllib.parse import urlparse
import httpx
class WebFetchParams(BaseModel):
    url: str = Field(..., description="The URL to fetch (must be http:// or https://)")
    timeout: int = Field(30, ge=5, le=120, description="The timeout in seconds for the fetch (default 30 seconds, max 120 seconds, min 5 seconds)")

# TODO: this is really bad, use a better tool for extracing text from the response body
class WebFetchTool(Tool):
    name: str = "webfetch"
    description: str = "Fetch content from a url and return the response body as text"
    type: ToolType = ToolType.NETWORK
    schema: WebFetchParams = WebFetchParams

    def __init__(self, config: Config) -> None:
        self._config = config

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = WebFetchParams(**invocation.params)
        try:
            parsed  = urlparse(params.url)
            if not parsed.scheme or parsed.scheme not in ["http", "https"]:
                return ToolResult.error_result(f"Invalid URL: {params.url}")
        except ValueError:
            return ToolResult.error_result(f"Invalid URL: {params.url}")
        
        response = None
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(params.timeout), follow_redirects=True) as client:
                response = await client.get(params.url)
                response.raise_for_status()
        except httpx.RequestError as e:
            return ToolResult.error_result(f"Error fetching the URL: {params.url} with error: {e}")
        except httpx.HTTPStatusError as e:
            return ToolResult.error_result(f"Error fetching the URL: {params.url} with error: {e.response.status_code}: {e.response.reason_phrase}")
        except httpx.HTTPError as e:
            return ToolResult.error_result(f"Error fetching the URL: {params.url} with error: {e}")
        except Exception as e:
            return ToolResult.error_result(f"Error fetching the URL: {params.url} with error: {e}")
        
        text = response.text
        truncated = False
        if len(text) > 100 * 1024:
            text = text[:100 * 1024] + "\n...truncated..."
            truncated = True
        return ToolResult.success_result(output=text, truncated=truncated, metadata=dict(url=params.url, status_code=response.status_code, headers=dict(response.headers), content_length=response.headers.get("content-length", 0)))
    
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error fetching the web page with error: {e}")