"""
Defines the tasks for all 7 agents in the VentureLens pipeline:
1. Coordinator: Problem formulation and research briefing
2. Market Research: Target audience, TAM/SAM/SOM, demand trends, real URLs
3. Competitor Analysis: Direct and indirect rivals, moats, strengths, weaknesses, competitor URLs
4. Financial Feasibility: Setup cost, revenue model, break-even timeline, unit economics via MCP
5. Risk Assessment: Technical, legal, regulatory, and market risks, citations
6. Comparator / Debate: Cross-verification of research reports and resolving contradictions
7. Investor Verdict: Final viability score (1-10) and Go / No-Go recommendation (Structured Pydantic output)
"""

from crewai import Task
from agents import (
    coordinator, market_agent, competitor_agent, financial_agent,
    risk_agent, comparator_agent, verdict_agent,
)


def build_coordinator_task(idea: str) -> Task:
    return Task(
        description=(
            f"You are the Startup Validation Coordinator. Analyze this business idea: '{idea}'.\n"
            "Define the core problem statement, identify the target customer persona, "
            "highlight any specific founder constraints or claims (such as budget, timeline, geography, and pricing/monetization promises), "
            "and formulate structured research directives for the 4 specialist analysts:\n"
            "1. Market Research (target audience, market size, demand trends, willingness to pay)\n"
            "2. Competitor Analysis (direct & indirect competitors, strengths, weaknesses, moats)\n"
            "3. Financial Feasibility (setup & operating costs vs founder budget, unit economics, revenue model sustainability, break-even reality)\n"
            "4. Risk Assessment (technical, legal, regulatory, operational, and market risks)\n"
            "Keep the brief sharp, objective, and actionable."
        ),
        expected_output=(
            "A structured coordinator brief defining the problem statement, target customer persona, "
            "key founder constraints/claims to test, and specific research questions for Market, Competitor, Financial, and Risk analysts."
        ),
        agent=coordinator,
    )


def build_research_tasks(idea: str, coordinator_brief: str = "") -> dict[str, tuple]:
    coord_ctx = f"\n\nCoordinator Directives:\n{coordinator_brief}\n" if coordinator_brief else ""

    market_task = Task(
        description=(
            f"Research the market for this business idea: '{idea}'.{coord_ctx}\n"
            "Cover target audience, market size (rough numbers if possible), "
            "and current demand trends. You MUST use your web_search tool to find real statistics and market reports. "
            "In your report, cite the verified URLs in [Source Title](URL) format."
        ),
        expected_output="4-6 bullet points covering audience, market size, and demand trend, "
                         "each with a one-line justification and real clickable source URLs in [Source Title](URL) format.",
        agent=market_agent,
    )

    competitor_task = Task(
        description=(
            f"Research existing products, startups, or companies already solving "
            f"a similar problem to: '{idea}'.{coord_ctx}\n"
            "You MUST use your web_search tool to find direct and indirect competitors. "
            "List 2-4 competitors with their strengths, weaknesses, and verified website URLs in [Company Name](URL) format."
        ),
        expected_output="A list of 2-4 competitors with strengths, weaknesses, and direct clickable source URLs in [Name](URL) format.",
        agent=competitor_agent,
    )

    financial_task = Task(
        description=(
            f"Critically analyze the financial feasibility of this business idea: '{idea}'.{coord_ctx}\n"
            "Use your tools (web_search and financial_calculator) to model the startup economics:\n"
            "1. Setup & Operating Costs: Estimate realistic initial setup and monthly operating expenses (tech infrastructure, operations, staffing, marketing). Use web_search where helpful.\n"
            "2. Unit Economics & Calculator: Use the financial_calculator tool to compute contribution margins, break-even unit volume, and runway requirements based on estimated price and variable costs. If the idea proposes zero charges, no commissions, no fees, and discounts on orders, explicitly run or note that the model has zero revenue and burns cash on every transaction.\n"
            "3. Break-Even & Profitability: Assess whether break-even and profitability are plausible under realistic unit economics."
        ),
        expected_output="A structured financial analysis including: 1) Estimated setup & monthly opex, "
                         "2) Unit economics & break-even metrics from the financial_calculator, "
                         "3) Feasibility of the break-even and runway timeline with clear assumptions.",
        agent=financial_agent,
    )

    risk_task = Task(
        description=(
            f"Identify the top technical, legal, and market risks for: '{idea}'.{coord_ctx}\n"
            "Use your web_search tool to check real-world regulatory news, compliance requirements, or failure precedents. "
            "Cite relevant URLs where applicable."
        ),
        expected_output="3-5 risks, each labelled [Technical] / [Legal] / [Market] with a "
                         "one-line explanation and source URLs.",
        agent=risk_agent,
    )

    return {
        "market": (market_agent, market_task, "Market Research Agent"),
        "competitor": (competitor_agent, competitor_task, "Competitor Analysis Agent"),
        "financial": (financial_agent, financial_task, "Financial Feasibility Agent"),
        "risk": (risk_agent, risk_task, "Risk Assessment Agent"),
    }


def build_comparator_task(idea: str, market_report: str = "", competitor_report: str = "",
                          financial_report: str = "", risk_report: str = "") -> Task:
    return Task(
        description=(
            f"Business Idea: '{idea}'\n\n"
            f"--- Market Research Report ---\n{market_report}\n\n"
            f"--- Competitor Analysis Report ---\n{competitor_report}\n\n"
            f"--- Financial Feasibility Report ---\n{financial_report}\n\n"
            f"--- Risk Assessment Report ---\n{risk_report}\n\n"
            "Read the Market, Competitor, Financial, and Risk reports above.\n"
            "Cross-examine the business idea against the specialist findings:\n"
            "1. Check if the founder made specific claims (e.g. budget, speed, zero fees) that directly contradict operational or financial reality.\n"
            "2. Distinguish between normal startup challenges (competition, marketing, hiring) versus fatal business model blockers (zero revenue, structurally negative unit economics, impossible budgets).\n"
            "3. If an idea has a sound revenue model (e.g. commission or subscription), treat competition and operational scaling as manageable challenges rather than fatal blockers.\n"
            "4. Clearly highlight any true fatal blockers that make the business impossible to sustain."
        ),
        expected_output="A structured debate report detailing: 1) Contradictions between founder claims and evidence, "
                         "2) Manageable trade-offs vs fatal business model blockers, "
                         "3) Summary of whether any fatal blockers exist.",
        agent=comparator_agent,
    )


def build_verdict_task(idea: str, market_report: str = "", competitor_report: str = "",
                       financial_report: str = "", risk_report: str = "",
                       debate_report: str = "") -> Task:
    return Task(
        description=(
            f"Business Idea: '{idea}'\n\n"
            f"--- Market Research Report ---\n{market_report}\n\n"
            f"--- Competitor Analysis Report ---\n{competitor_report}\n\n"
            f"--- Financial Feasibility Report ---\n{financial_report}\n\n"
            f"--- Risk Assessment Report ---\n{risk_report}\n\n"
            f"--- Contradiction Debate Report ---\n{debate_report}\n\n"
            "You are the Investor Verdict Agent. Your job is to make a fair, balanced, and evidence-based "
            "investment validation decision for this startup idea.\n\n"
            "CORE PRINCIPLE: Distinguish fatal business model blockers from normal startup execution risks.\n"
            "- A business idea SHOULD BE VALIDATED (Recommendation: Go, Score 6-9/10) if it has a plausible monetization mechanism "
            "(e.g., commissions, subscriptions, margins), potentially viable unit economics, and standard startup risks (like competition, customer acquisition, or regulatory compliance) that can be managed as the business grows.\n"
            "- A business idea MUST BE NOT VALIDATED (Recommendation: No-Go, Score 1-4/10) ONLY IF it has fatal, unresolved feasibility blockers—such as proposing zero revenue (no charges, no fees, no commissions), structurally negative unit economics (losing money on every order with no revenue stream), or mathematically impossible operational/budget claims.\n\n"
            "OUTPUT FORMAT REQUIREMENTS:\n"
            "Score: X/10\n"
            "Recommendation: Go or No-Go\n"
            "Justification: 3-5 lines explaining the verdict, specifically addressing revenue viability, operational/capital realism, and whether blockers are fatal or manageable.\n"
            "Market Demand Score: X/10\n"
            "Competitive Moat Score: X/10\n"
            "Unit Economics Score: X/10\n"
            "Risk Profile Score: X/10\n"
            "Key Strengths: 2-3 bullet points\n"
            "Fatal Blockers: bullet points if any, or 'None'\n"
            "Manageable Risks: 2-3 bullet points"
        ),
        expected_output="Score: X/10\nRecommendation: Go or No-Go\nJustification: 3-5 lines of clear, evidence-based justification.\nMarket Demand Score: X/10\nCompetitive Moat Score: X/10\nUnit Economics Score: X/10\nRisk Profile Score: X/10\nKey Strengths: ...\nFatal Blockers: ...\nManageable Risks: ...",
        agent=verdict_agent,
    )


def build_tasks(idea: str):
    tasks_dict = build_research_tasks(idea)
    market_task = tasks_dict["market"][1]
    competitor_task = tasks_dict["competitor"][1]
    financial_task = tasks_dict["financial"][1]
    risk_task = tasks_dict["risk"][1]
    comparator_task = build_comparator_task(idea)
    verdict_task = build_verdict_task(idea)
    return [market_task, competitor_task, financial_task, risk_task, comparator_task, verdict_task]
