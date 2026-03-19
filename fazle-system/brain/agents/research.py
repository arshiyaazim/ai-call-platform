# ============================================================
# Research Agent — Internet search and knowledge retrieval
# Searches web, scrapes content, and summarizes findings
# ============================================================
import logging

import httpx

from .base import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger("fazle-agents.research")

# Keywords indicating research/search needs
_RESEARCH_KEYWORDS = frozenset([
    "search", "find", "look up", "google", "what is",
    "how to", "tell me about", "latest", "news",
    "current", "today", "price of", "weather",
    "explain", "research", "information about",
])


class ResearchAgent(BaseAgent):
    name = "research"
    description = "Searches the internet and retrieves knowledge"

    def __init__(self, tools_url: str):
        self.tools_url = tools_url

    async def can_handle(self, ctx: AgentContext) -> bool:
        msg = ctx.message.lower()
        return any(kw in msg for kw in _RESEARCH_KEYWORDS)

    async def execute(self, ctx: AgentContext) -> AgentResult:
        """Search the web for information relevant to the query."""
        results = await self._web_search(ctx.message)
        ctx.search_results = results

        # If results found, try to scrape the top result for more detail
        enriched = []
        if results and len(results) > 0:
            top_url = results[0].get("url", "")
            if top_url:
                scraped = await self._scrape_url(top_url)
                if scraped:
                    enriched.append(scraped)

        return AgentResult(
            content={
                "search_results": results,
                "enriched_content": enriched,
            },
        )

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Public search method for use by other agents."""
        return await self._web_search(query, max_results)

    async def scrape(self, url: str) -> dict | None:
        """Public scrape method for use by other agents."""
        return await self._scrape_url(url)

    async def _web_search(self, query: str, max_results: int = 5) -> list[dict]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(
                    f"{self.tools_url}/search",
                    json={"query": query, "max_results": max_results},
                )
                if resp.status_code == 200:
                    return resp.json().get("results", [])
            except Exception as e:
                logger.warning(f"Web search failed: {e}")
        return []

    async def _scrape_url(self, url: str) -> dict | None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.tools_url}/scrape",
                    json={"url": url, "extract_text": True},
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                logger.warning(f"Scrape failed: {e}")
        return None
