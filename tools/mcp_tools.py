"""
MCP Tool Bridge for CrewAI and ADK Agents.

Provides access to the external tools integrated via MCP (Model Context Protocol):
1. web_search (mcp_web_search): Real-time search via Serper Google API with direct structured source extraction.
2. financial_calculator (mcp_financial_calculator): Unit economics, break-even, and capital requirement modeling.

Includes thread-local source accumulator and real-time activity emission.
"""

import sys
import threading
from urllib.parse import urlparse
from crewai.tools import tool
from tools.mcp_server import mcp_web_search_structured, mcp_financial_calculator

# Thread-local storage for event emitting and source collection
_tool_context = threading.local()


def init_thread_sources():
    _tool_context.sources = []


def get_thread_sources() -> list[dict]:
    raw = getattr(_tool_context, "sources", None)
    return list(raw) if raw is not None else []


def clear_thread_sources():
    _tool_context.sources = []


def set_search_event_emitter(fn):
    _tool_context.emitter = fn
    if not hasattr(_tool_context, "sources") or _tool_context.sources is None:
        _tool_context.sources = []


def clear_search_event_emitter():
    _tool_context.emitter = None
    _tool_context.sources = []


def _emit_event(event: dict):
    fn = getattr(_tool_context, "emitter", None)
    if fn:
        try:
            fn(event)
        except Exception:
            pass


@tool("web_search")
def web_search_tool(query: str) -> str:
    """Searches the live web using Google search to find market size, competitors, benchmarks, and regulatory risks. Returns real titles and verified URLs.
    
    Args:
        query: Specific search terms (e.g. 'independent veterinary clinic software market size TAM').
    """
    clean_q = str(query).strip()
    _emit_event({
        "type": "search_started",
        "message": f"Searching: {clean_q[:60]}",
    })

    text_result, sources = mcp_web_search_structured(query=clean_q)

    # Accumulate parsed sources directly into thread-local collection
    if not hasattr(_tool_context, "sources") or _tool_context.sources is None:
        _tool_context.sources = []

    seen = {s.get("url") for s in _tool_context.sources if s.get("url")}
    for s in sources:
        u = s.get("url")
        if u and u not in seen:
            seen.add(u)
            _tool_context.sources.append(s)
            _emit_event({
                "type": "source_found",
                "title": s["title"],
                "url": s["url"],
                "domain": s["domain"],
                "snippet": s["snippet"],
                "supports": s["supports"],
            })

    return text_result


# Alias for backwards compatibility and explicit naming
mcp_web_search_tool = web_search_tool


@tool("financial_calculator")
def financial_calculator_tool(
    setup_costs: float,
    monthly_operating_expenses: float,
    price_per_unit: float,
    cost_per_unit: float,
    monthly_target_units: int = 100,
) -> str:
    """Calculates unit economics, contribution margin, break-even unit volume, and 12-month capital requirements.
    
    Args:
        setup_costs: One-time setup / launch capital (Rs).
        monthly_operating_expenses: Fixed monthly burn (Rs) for salaries, servers, operations, rent.
        price_per_unit: Revenue generated per unit/order/subscription (Rs). Use 0 if the business charges no fees.
        cost_per_unit: Variable cost incurred per transaction/order (Rs).
        monthly_target_units: Expected or target units sold per month (default 100).
    """
    _emit_event({
        "type": "agent_activity",
        "message": f"Calculating unit economics: Price Rs {price_per_unit} vs Cost Rs {cost_per_unit}",
    })

    return mcp_financial_calculator(
        setup_costs=float(setup_costs),
        monthly_operating_expenses=float(monthly_operating_expenses),
        price_per_unit=float(price_per_unit),
        cost_per_unit=float(cost_per_unit),
        monthly_target_units=int(monthly_target_units),
    )


# Alias
mcp_financial_calculator_tool = financial_calculator_tool
