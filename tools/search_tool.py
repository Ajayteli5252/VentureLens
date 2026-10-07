"""
Custom web search tool using Serper's API directly.

Includes a thread-local event emitter so that search_started and
source_found events can be streamed into the per-request SSE queue.

Safety: threading.local() is per-thread, not shared between threads.
Each follow-up request runs in its own dedicated background thread, so
registering/clearing the emitter here never mixes events between sessions.
"""

import os
import threading
import requests
from crewai.tools import tool


# ---------------------------------------------------------------------------
# Per-thread search event emitter
# ---------------------------------------------------------------------------
_search_emitter = threading.local()


def set_search_event_emitter(fn):
    """Register an event emitter for the current thread.

    Safe to call per-request because each follow-up runs in its own thread.
    Always call clear_search_event_emitter() in a finally block after use.
    """
    _search_emitter.fn = fn


def clear_search_event_emitter():
    """Remove the search event emitter for the current thread."""
    _search_emitter.fn = None


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
    print(f"\n[TOOL CALL]\nTool: web_search\nArguments: query='{query}'\n")

    # Notify SSE stream that a search is starting (scoped to this thread's request)
    _emit_search_event({
        "type": "search_started",
        "message": f"Searching: {query[:80]}",
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

    results = []
    for item in data.get("organic", [])[:5]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")
        results.append(f"- {title}: {snippet} ({link})")

        # Notify SSE stream that a source was found
        _emit_search_event({
            "type": "source_found",
            "message": f"Source found: {title}",
            "title": title,
            "url": link,
        })

    return "\n".join(results) if results else "No results found for this query."
