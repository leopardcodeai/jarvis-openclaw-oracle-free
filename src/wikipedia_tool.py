import asyncio
import logging

logger = logging.getLogger(__name__)


def _search_sync(query: str, sentences: int) -> dict:
    import wikipedia
    wikipedia.set_lang("de")
    try:
        summary = wikipedia.summary(query, sentences=sentences, auto_suggest=True)
        page = wikipedia.page(query, auto_suggest=True)
        return {"success": True, "title": page.title, "summary": summary, "url": page.url}
    except wikipedia.exceptions.DisambiguationError as e:
        # Try first option
        try:
            suggestion = e.options[0]
            summary = wikipedia.summary(suggestion, sentences=sentences)
            page = wikipedia.page(suggestion)
            return {"success": True, "title": page.title, "summary": summary, "url": page.url,
                    "note": f"Mehrdeutig – zeige: {suggestion}"}
        except Exception:
            return {"success": False, "error": f"Mehrdeutig: {', '.join(e.options[:5])}"}
    except wikipedia.exceptions.PageError:
        # Fallback to English
        wikipedia.set_lang("en")
        try:
            summary = wikipedia.summary(query, sentences=sentences, auto_suggest=True)
            page = wikipedia.page(query, auto_suggest=True)
            return {"success": True, "title": page.title, "summary": summary, "url": page.url,
                    "note": "Kein deutscher Artikel – zeige Englisch"}
        except Exception as e2:
            return {"success": False, "error": str(e2)}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        wikipedia.set_lang("de")


async def wiki_search(query: str, sentences: int = 5) -> dict:
    """Async Wikipedia search, tries German first, falls back to English."""
    return await asyncio.get_event_loop().run_in_executor(None, _search_sync, query, sentences)


def format_wiki(data: dict) -> str:
    if not data["success"]:
        return f"❌ Wikipedia: {data['error']}"
    note = f"\n_{data['note']}_" if data.get("note") else ""
    return (
        f"📚 *{data['title']}*{note}\n\n"
        f"{data['summary']}\n\n"
        f"🔗 {data['url']}"
    )


def format_wiki_for_llm(data: dict) -> str:
    if not data["success"]:
        return f"[Wikipedia] Kein Artikel gefunden: {data['error']}"
    return f"[Wikipedia: {data['title']}]\n{data['summary']}"
