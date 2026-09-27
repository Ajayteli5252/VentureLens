"""
Custom web search tool using Serper's API directly.
"""

import os
import requests
from crewai.tools import tool


@tool("web_search")
def web_search_tool(query: str) -> str:
    """Searches the web for the given query and returns the top results as text.
    Use this to find current market data, competitor information, and regulatory facts."""
    # Safe debug logging (no secrets or keys logged)
    print(f"\n[TOOL CALL]\nTool: web_search\nArguments: query='{query}'\n")

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

    return "\n".join(results) if results else "No results found for this query."
