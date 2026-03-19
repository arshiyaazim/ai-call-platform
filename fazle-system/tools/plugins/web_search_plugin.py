# ============================================================
# Web Search Plugin — Internet search via Serper/Tavily
# ============================================================
import httpx
from . import Plugin


class WebSearchPlugin(Plugin):
    name = "web_search"
    description = "Search the internet for real-time information"
    version = "1.0.0"

    def __init__(self, serper_api_key: str = "", tavily_api_key: str = ""):
        self.serper_api_key = serper_api_key
        self.tavily_api_key = tavily_api_key

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs) -> dict:
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)
        if not query:
            return {"error": "Query is required"}

        if self.serper_api_key:
            return await self._search_serper(query, max_results)
        if self.tavily_api_key:
            return await self._search_tavily(query, max_results)
        return {"error": "No search API configured"}

    async def _search_serper(self, query: str, max_results: int) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": self.serper_api_key,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": max_results},
            )
            resp.raise_for_status()
            data = resp.json()
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in data.get("organic", [])[:max_results]
        ]
        return {"status": "ok", "results": results}

    async def _search_tavily(self, query: str, max_results: int) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
            }
            for item in data.get("results", [])[:max_results]
        ]
        return {"status": "ok", "results": results}
