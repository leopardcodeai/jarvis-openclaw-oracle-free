import asyncio
import logging
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

MAX_RESULTS = 5


def _search_sync(query: str, max_results: int) -> list[dict]:
    """Synchronous DuckDuckGo search (runs in thread)."""
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


async def search(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    """Async DuckDuckGo web search. Returns list of {title, href, body}."""
    try:
        results = await asyncio.get_event_loop().run_in_executor(
            None, _search_sync, query, max_results
        )
        return results
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return []


def format_results_for_llm(query: str, results: list[dict]) -> str:
    """Format search results as context for the LLM."""
    if not results:
        return f"Keine Suchergebnisse für: {query}"

    lines = [f"Web-Suchergebnisse für \"{query}\":\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        body = r.get("body", "")[:300]
        url = r.get("href", "")
        lines.append(f"{i}. **{title}**\n   {body}\n   Quelle: {url}\n")

    return "\n".join(lines)


def format_results_for_telegram(query: str, results: list[dict]) -> str:
    """Format search results as a Telegram message."""
    if not results:
        return f"❌ Keine Ergebnisse für: *{query}*"

    lines = [f"🔍 *Suchergebnisse: {query}*\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        body = r.get("body", "")[:200]
        url = r.get("href", "")
        lines.append(f"*{i}. {title}*\n{body}\n🔗 {url}\n")

    return "\n".join(lines)
