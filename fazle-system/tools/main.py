# ============================================================
# Fazle Web Intelligence — Internet search and content extraction
# ============================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
import httpx
import ipaddress
import logging
import os
import re
import socket
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-web-intelligence")


class Settings(BaseSettings):
    serper_api_key: str = ""
    tavily_api_key: str = ""
    search_provider: str = "serper"  # "serper" or "tavily"
    memory_url: str = "http://fazle-memory:8300"

    class Config:
        env_prefix = ""


settings = Settings()

app = FastAPI(title="Fazle Web Intelligence — Search & Extraction", version="1.0.0")

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://fazle.iamazim.com,https://iamazim.com,http://localhost:3020").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fazle-web-intelligence", "timestamp": datetime.utcnow().isoformat()}


# ── Search ──────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    max_results: int = 5


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


@app.post("/search")
async def search(request: SearchRequest):
    """Search the internet for information."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if settings.search_provider == "tavily" and settings.tavily_api_key:
        results = await _search_tavily(request.query, request.max_results)
    elif settings.serper_api_key:
        results = await _search_serper(request.query, request.max_results)
    else:
        raise HTTPException(status_code=503, detail="No search API configured")

    return {"query": request.query, "results": results, "count": len(results)}


async def _search_serper(query: str, max_results: int) -> list[dict]:
    """Search using Serper API (Google Search)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": settings.serper_api_key,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": max_results},
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("organic", [])[:max_results]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        })
    return results


async def _search_tavily(query: str, max_results: int) -> list[dict]:
    """Search using Tavily API."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": max_results,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("results", [])[:max_results]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
        })
    return results


# ── Web scraping ────────────────────────────────────────────
class ScrapeRequest(BaseModel):
    url: str
    extract_text: bool = True


def _is_private_ip(url: str) -> bool:
    """Check if URL points to private/internal IP ranges (SSRF protection).

    Resolves both IPv4 and IPv6 addresses via getaddrinfo to block:
    127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16,
    169.254.0.0/16, ::1, fc00::/7, fe80::/10, and other reserved ranges.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True

        # Fast reject known internal hostnames
        if hostname in ('localhost', '0.0.0.0', '[::1]', '[::]'):
            return True
        if hostname.endswith('.internal') or hostname.endswith('.local'):
            return True

        # Resolve all addresses (IPv4 + IPv6) for the hostname
        try:
            addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror:
            return True  # Block unresolvable hostnames

        if not addr_infos:
            return True

        for addr_info in addr_infos:
            raw_ip = addr_info[4][0]
            try:
                ip = ipaddress.ip_address(raw_ip)
            except ValueError:
                return True
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return True

        return False
    except Exception:
        return True  # Fail closed on any parsing error


@app.post("/scrape")
async def scrape(request: ScrapeRequest):
    """Extract content from a web page."""
    # Validate URL format
    if not re.match(r'^https?://', request.url):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    # SSRF protection: block requests to internal/private IPs
    if _is_private_ip(request.url):
        raise HTTPException(status_code=400, detail="URL resolves to internal/private IP range")

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(
                request.url,
                headers={"User-Agent": "Fazle-AI/1.0 (Personal Assistant)"},
            )
            resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {str(e)}")

    if request.extract_text:
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts, styles, navs
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Clean up excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        title = soup.title.string if soup.title else ""

        return {
            "url": request.url,
            "title": title,
            "text": text[:10000],  # Limit to 10K chars
            "length": len(text),
        }

    return {"url": request.url, "html": resp.text[:50000]}


# ── Summarize content ──────────────────────────────────────
class SummarizeRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None


@app.post("/summarize")
async def summarize(request: SummarizeRequest):
    """Scrape a URL and/or summarize text. Uses the brain for summarization."""
    content = request.text or ""

    if request.url:
        scrape_result = await scrape(ScrapeRequest(url=request.url))
        content = scrape_result.get("text", "")

    if not content:
        raise HTTPException(status_code=400, detail="No content to summarize")

    # Store in knowledge base
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            await client.post(
                f"{settings.memory_url}/ingest",
                json={
                    "text": content[:5000],
                    "source": request.url or "direct_input",
                    "title": f"Web content from {request.url}" if request.url else "Direct text",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to store in knowledge base: {e}")

    return {
        "content": content[:5000],
        "source": request.url or "direct_input",
        "stored_in_knowledge": True,
    }
