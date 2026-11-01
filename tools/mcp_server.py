"""
Model Context Protocol (MCP) Server for VentureLens.

Implements Requirement 2:
Tool Integration using MCP: At least two external tools (library or custom) must be used
(e.g., web search API, database lookup, file parser, calculator).

Exposes:
1. mcp_web_search: Real-time search engine via Serper API with structured citations.
2. mcp_financial_calculator: Startup unit economics, break-even, and runway calculator.
"""

import os
import sys
import json
import requests
from urllib.parse import urlparse
try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.mcpserver import MCPServer as FastMCP
    except Exception:
        class FastMCP:
            def __init__(self, name: str = "VentureLens-Tools-Server"):
                self.name = name
            def tool(self, name: str = None, description: str = None):
                def decorator(func):
                    return func
                return decorator

# Initialize FastMCP Server
mcp_server = FastMCP(name="VentureLens-Tools-Server")


def mcp_web_search_structured(query: str) -> tuple[str, list[dict]]:
    """Performs live Google search via Serper and returns both LLM-friendly text and structured sources list."""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return "[Search unavailable: SERPER_API_KEY not configured]", []

    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query.strip(), "num": 5}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=14)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return f"[Search error: Failed to fetch search results ({e})]", []

    organic = data.get("organic", [])
    if not organic:
        return f"No results found for query: '{query}'", []

    sources = []
    text_blocks = []

    for item in organic[:5]:
        title = str(item.get("title", "")).strip()
        link = str(item.get("link", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        domain = ""
        if link:
            try:
                domain = urlparse(link).netloc.replace("www.", "")
            except Exception:
                domain = ""

        if not title:
            title = domain or link

        supports_text = snippet if snippet else f"Live evidence concerning '{query[:80]}'"

        sources.append({
            "title": title,
            "url": link,
            "domain": domain,
            "snippet": snippet,
            "supports": supports_text,
            "query": query,
        })

        text_blocks.append(f"- **{title}** ({domain})\n  Link: {link}\n  Summary: {snippet}")

    return "\n\n".join(text_blocks), sources


@mcp_server.tool()
def mcp_web_search(query: str) -> str:
    """Searches the live web for market demand, competitors, industry benchmarks, or risks using Google-indexed search.
    
    Args:
        query: Specific search terms (e.g. 'independent veterinary clinic software market size TAM').
    Returns:
        Structured search evidence with titles, URLs, and summaries.
    """
    text_result, _ = mcp_web_search_structured(query)
    return text_result


@mcp_server.tool()
def mcp_financial_calculator(
    setup_costs: float,
    monthly_operating_expenses: float,
    price_per_unit: float,
    cost_per_unit: float,
    monthly_target_units: int = 100,
) -> str:
    """Calculates startup unit economics, break-even volume, gross margins, and annual capital requirements.

    Args:
        setup_costs: Initial capital expenditure (tech build, licenses, equipment).
        monthly_operating_expenses: Monthly fixed burn (salaries, servers, rent, baseline marketing).
        price_per_unit: Revenue generated per unit/order/subscription.
        cost_per_unit: Direct variable cost incurred per unit/order (COGS, payment fees, shipping).
        monthly_target_units: Projected or target monthly transaction/user volume.
    Returns:
        Structured analysis of unit economics, break-even threshold, and financial sustainability.
    """
    contribution_margin = price_per_unit - cost_per_unit

    if price_per_unit <= 0:
        return (
            "[CRITICAL FINANCIAL WARNING: ZERO REVENUE MODEL]\n"
            f"- Price per unit: Rs {price_per_unit:,.2f}\n"
            f"- Cost per unit: Rs {cost_per_unit:,.2f}\n"
            "- Unit Margin: Structural cash loss on every single transaction.\n"
            f"- Monthly Operating Burn: Rs {monthly_operating_expenses:,.2f}\n"
            "- Assessment: Fatal business model blocker. High transaction volume accelerates insolvency."
        )

    gross_margin_pct = (contribution_margin / price_per_unit) * 100.0

    if contribution_margin <= 0:
        return (
            "[NEGATIVE UNIT ECONOMICS DETECTED]\n"
            f"- Price: Rs {price_per_unit:,.2f} vs Variable Cost: Rs {cost_per_unit:,.2f}\n"
            f"- Unit Margin: Rs {contribution_margin:,.2f} ({gross_margin_pct:.1f}%)\n"
            "- Break-even: Mathematically impossible. The business loses money on each unit sold.\n"
            "- Assessment: Negative unit economics cannot be scaled. Pricing or cost structure must be redesigned."
        )

    # Break-even calculation
    break_even_units_per_month = monthly_operating_expenses / contribution_margin if contribution_margin > 0 else float("inf")
    monthly_revenue_at_target = monthly_target_units * price_per_unit
    monthly_gross_profit = monthly_target_units * contribution_margin
    monthly_net_profit = monthly_gross_profit - monthly_operating_expenses

    annual_fixed_burn = monthly_operating_expenses * 12.0
    recommended_year1_capital = setup_costs + (monthly_operating_expenses * 12.0)

    status_tag = "HEALTHY" if gross_margin_pct >= 40 else "TIGHT MARGINS"
    profit_tag = "PROFITABLE AT TARGET" if monthly_net_profit >= 0 else "LOSS-MAKING AT TARGET VOLUME"

    return f"""### Financial Due-Diligence Model
- Setup / Initial Capital Required: Rs {setup_costs:,.2f}
- Monthly Fixed Operating Burn: Rs {monthly_operating_expenses:,.2f}
- Unit Economics:
  * Unit Price / Revenue: Rs {price_per_unit:,.2f}
  * Variable Cost (COGS): Rs {cost_per_unit:,.2f}
  * Contribution Margin: Rs {contribution_margin:,.2f} ({gross_margin_pct:.1f}% Gross Margin) [{status_tag}]
- Break-Even Analysis:
  * Required Monthly Volume: {int(break_even_units_per_month + 0.999):,} units/orders per month
  * Break-even Monthly Revenue: Rs {(break_even_units_per_month * price_per_unit):,.2f}
- Target Volume Performance ({monthly_target_units:,} units/mo):
  * Monthly Revenue: Rs {monthly_revenue_at_target:,.2f}
  * Monthly Net Operating Profit/Loss: Rs {monthly_net_profit:,.2f} [{profit_tag}]
- 12-Month Runway Recommendation: Minimum Rs {recommended_year1_capital:,.2f} working capital recommended.
"""


if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    txt, srcs = mcp_web_search_structured("startup valuation")
    print("Search result length:", len(txt), "| Sources count:", len(srcs))
