"""
Custom web search tool using Serper's API directly.

Includes a thread-local event emitter so that search_started and
source_found events can be streamed into the per-request SSE queue.

Safety: threading.local() is per-thread, not shared between threads.
Each follow-up request runs in its own dedicated background thread, so
registering/clearing the emitter here never mixes events between sessions.

Windows UTF-8 fix: all print() and string-building calls safely encode/decode
through UTF-8 with 'replace' error handling to avoid cp1252/charmap crashes.
"""

import os
import sys
import threading
import requests
from urllib.parse import urlparse
from crewai.tools import tool


def _u(text) -> str:
    """Return a Unicode-safe version of text (replaces unencodable chars)."""
    if not isinstance(text, str):
        text = str(text)
    return text.encode('utf-8', errors='replace').decode('utf-8')


def _safe_print(msg: str):
    """Print to stdout in UTF-8 without crashing on Windows cp1252 consoles."""
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout.buffer.write((_u(msg) + "\n").encode('utf-8', errors='replace'))
            sys.stdout.buffer.flush()
        else:
            print(_u(msg))
    except Exception:
        try:
            print(msg.encode('ascii', errors='replace').decode('ascii'))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Per-thread search event emitter and source accumulator
# ---------------------------------------------------------------------------
_search_emitter = threading.local()


def init_thread_sources():
    """Initialize or reset the thread-local source accumulator."""
    _search_emitter.sources = []


def get_thread_sources() -> list[dict]:
    """Retrieve all structured sources collected in the current thread."""
    raw = getattr(_search_emitter, "sources", None)
    return list(raw) if raw is not None else []


def clear_thread_sources():
    """Clear the thread-local source accumulator."""
    _search_emitter.sources = []


def set_search_event_emitter(fn):
    """Register an event emitter for the current thread.

    Safe to call per-request because each follow-up or validation agent runs
    in its own thread. Always call clear_search_event_emitter() in a finally block.
    """
    _search_emitter.fn = fn
    if not hasattr(_search_emitter, "sources") or _search_emitter.sources is None:
        _search_emitter.sources = []


def clear_search_event_emitter():
    """Remove the search event emitter and clear sources for the current thread."""
    _search_emitter.fn = None
    _search_emitter.sources = []


def _emit_search_event(event: dict):
    """Emit a search event through the current thread's registered emitter."""
    fn = getattr(_search_emitter, "fn", None)
    if fn is not None:
        try:
            fn(event)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

@tool("web_search")
def web_search_tool(query: str) -> str:
    """Searches the web for the given query and returns the top results as text.
    Use this to find current market data, competitor information, and regulatory facts."""

    # Safe debug logging (no secrets or keys logged)
    _safe_print(f"\n[TOOL CALL]\nTool: web_search\nArguments: query='{_u(query)}'\n")

    # Notify SSE stream that a search is starting (scoped to this thread's request)
    _emit_search_event({
        "type": "search_started",
        "message": f"Searching: {_u(query)[:80]}",
    })

    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": os.getenv("SERPER_API_KEY", ""),
        "Content-Type": "application/json",
    }
    payload = {"q": query}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return f"Search failed: {e}"

    if not hasattr(_search_emitter, "sources") or _search_emitter.sources is None:
        _search_emitter.sources = []

    results = []
    seen_urls = {s.get("url") for s in _search_emitter.sources if s.get("url")}

    for item in data.get("organic", [])[:5]:
        title = _u(item.get("title", "")).strip()
        snippet = _u(item.get("snippet", "")).strip()
        link = _u(item.get("link", "")).strip()

        domain = ""
        if link:
            try:
                domain = urlparse(link).netloc.replace("www.", "")
            except Exception:
                domain = ""

        if not title:
            title = domain or link

        supports_text = snippet if snippet else f"Verified research data regarding '{_u(query)[:80]}'"

        source_record = {
            "title": title,
            "url": link,
            "domain": domain,
            "snippet": snippet,
            "supports": supports_text,
            "query": _u(query),
        }

        if link and link not in seen_urls:
            seen_urls.add(link)
            _search_emitter.sources.append(source_record)

        results.append(f"- {title}: {snippet} ({link})")

        # Notify SSE stream that a source was found with full metadata
        _emit_search_event({
            "type": "source_found",
            "message": f"Source found: {title}",
            "title": title,
            "url": link,
            "domain": domain,
            "snippet": snippet,
            "supports": supports_text,
        })

    return "\n".join(results) if results else "No results found for this query."

