"""
Defines the 6 tasks (Coordinator has no task of its own — it only manages,
see crew.py). Each task's `context` list tells CrewAI which earlier tasks'
outputs this agent is allowed to read before doing its own work.
"""

from crewai import Task
from agents import (
    market_agent, competitor_agent, financial_agent,
    risk_agent, comparator_agent, verdict_agent,
)


def build_tasks(idea: str):
    market_task = Task(
        description=(
            f"Research the market for this business idea: '{idea}'. "
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
            f"a similar problem to: '{idea}'. List their strengths and weaknesses."
        ),
        expected_output="A list of 2-4 competitors (or 'no direct competitor found' if genuinely "
                         "none, only after searching) with one strength and one weakness each.",
        agent=competitor_agent,
    )

    financial_task = Task(
        description=(
            f"Estimate rough setup cost, a plausible revenue model, and an approximate "
            f"break-even timeline for: '{idea}'. State your assumptions clearly."
        ),
        expected_output="Rough cost estimate, one revenue model suggestion, and an estimated "
                         "break-even period, each with the assumption behind it.",
        agent=financial_agent,
    )

    risk_task = Task(
        description=(
            f"Identify the top technical, legal, and market risks for: '{idea}'. "
            "Use web search where relevant (e.g. regulatory news)."
        ),
        expected_output="3-5 risks, each labelled [Technical] / [Legal] / [Market] with a "
                         "one-line explanation.",
        agent=risk_agent,
    )

    comparator_task = Task(
        description=(
            "Read the Market, Competitor, Financial, and Risk reports above. "
            "Identify any contradictions (for example, high demand claimed alongside "
            "high competition or high risk). Resolve each contradiction with reasoning. "
            "If there are no contradictions, state that explicitly."
        ),
        expected_output="A short list of identified contradictions (or 'none found') "
                         "each followed by a 1-2 line resolution.",
        agent=comparator_agent,
        context=[market_task, competitor_task, financial_task, risk_task],
    )

    verdict_task = Task(
        description=(
            "Using all reports and the resolved contradictions above, give a final "
            "verdict for the idea: a score out of 10 and a clear Go / No-Go recommendation "
            "with 3-4 lines of justification."
        ),
        expected_output="Score: X/10\nRecommendation: Go or No-Go\nJustification: 3-4 lines.",
        agent=verdict_agent,
        context=[market_task, competitor_task, financial_task, risk_task, comparator_task],
    )

    return [market_task, competitor_task, financial_task, risk_task, comparator_task, verdict_task]
