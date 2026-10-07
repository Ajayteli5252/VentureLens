"""
Defines the tasks for all 7 agents in the VentureLens pipeline:
1. Coordinator: Problem formulation and research briefing
2. Market Research: Target audience, TAM/SAM/SOM, demand trends
3. Competitor Analysis: Direct and indirect rivals, moats, strengths, weaknesses
4. Financial Feasibility: Setup cost, revenue model, break-even timeline
5. Risk Assessment: Technical, legal, regulatory, and market risks
6. Comparator / Debate: Cross-verification of research reports and resolving contradictions
7. Investor Verdict: Final viability score (1-10) and Go / No-Go recommendation
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
            "and formulate structured research directives for the 4 specialist analysts:\n"
            "1. Market Research (target audience, market size, demand trends)\n"
            "2. Competitor Analysis (direct & indirect competitors, strengths, weaknesses, moats)\n"
            "3. Financial Feasibility (setup costs, revenue model, break-even timeline)\n"
            "4. Risk Assessment (technical, legal, regulatory, and market risks)\n"
            "Keep the brief sharp, objective, and actionable."
        ),
        expected_output=(
            "A structured coordinator brief defining the problem statement, target customer persona, "
            "and specific research questions for Market, Competitor, Financial, and Risk analysts."
        ),
        agent=coordinator,
    )


def build_research_tasks(idea: str, coordinator_brief: str = "") -> dict[str, tuple]:
    coord_ctx = f"\n\nCoordinator Directives:\n{coordinator_brief}\n" if coordinator_brief else ""

    market_task = Task(
        description=(
            f"Research the market for this business idea: '{idea}'.{coord_ctx}\n"
            "Cover target audience, market size (rough numbers if possible), "
            "and current demand trends. Use web search for evidence."
        ),
        expected_output="4-6 bullet points covering audience, market size, and demand trend, "
                         "each with a one-line justification.",
        agent=market_agent,
    )

    competitor_task = Task(
        description=(
            f"Research existing products, startups, or companies already solving "
            f"a similar problem to: '{idea}'.{coord_ctx}\n"
            "List their strengths and weaknesses."
        ),
        expected_output="A list of 2-4 competitors (or 'no direct competitor found' if genuinely "
                         "none, only after searching) with one strength and one weakness each.",
        agent=competitor_agent,
    )

    financial_task = Task(
        description=(
            f"Estimate rough setup cost, a plausible revenue model, and an approximate "
            f"break-even timeline for: '{idea}'.{coord_ctx}\n"
            "State your assumptions clearly."
        ),
        expected_output="Rough cost estimate, one revenue model suggestion, and an estimated "
                         "break-even period, each with the assumption behind it.",
        agent=financial_agent,
    )

    risk_task = Task(
        description=(
            f"Identify the top technical, legal, and market risks for: '{idea}'.{coord_ctx}\n"
            "Use web search where relevant (e.g. regulatory news)."
        ),
        expected_output="3-5 risks, each labelled [Technical] / [Legal] / [Market] with a "
                         "one-line explanation.",
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
            "Read the Market, Competitor, Financial, and Risk reports above. "
            "Identify any contradictions (for example, high demand claimed alongside "
            "high competition or high risk). Resolve each contradiction with reasoning. "
            "If there are no contradictions, state that explicitly."
        ),
        expected_output="A short list of identified contradictions (or 'none found') "
                         "each followed by a 1-2 line resolution.",
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
            "Using all reports and the resolved contradictions above, give a final "
            "verdict for the idea: a score out of 10 and a clear Go / No-Go recommendation "
            "with 3-4 lines of justification."
        ),
        expected_output="Score: X/10\nRecommendation: Go or No-Go\nJustification: 3-4 lines.",
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
