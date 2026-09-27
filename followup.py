"""
Follow-up question routing and single-agent execution for VentureLens.

Routes user follow-up questions to ONLY the relevant research agent without
triggering the Coordinator, Comparator/Debate, Investor-Verdict, or other
unrelated research agents.
"""

import re
import logging
import urllib.parse
from crewai import Task, Crew, Process
from agents import (
    market_agent,
    competitor_agent,
    financial_agent,
    risk_agent,
)

logger = logging.getLogger(__name__)

# Explicit revalidation triggers
REVALIDATE_PATTERNS = [
    r"\brevalidate\b",
    r"\bvalidation again\b",
    r"\brun.*(complete|full).*validation\b",
    r"\bvalidate again\b",
    r"\bupdate.*(final)?.*score\b",
    r"\bfresh analysis\b",
    r"\bstart over\b",
    r"\bre-evaluate\b",
]

KEYWORD_MAP = {
    "competitor": [
        "competitor", "competitors", "competition", "compete", "competing",
        "rival", "rivals", "alternative", "alternatives", "substitute", "substitutes",
        "differentiation", "differentiate", "positioning", "moat",
        "competitor strengths", "competitor weaknesses", "vs", "versus", "other players"
    ],
    "financial": [
        "revenue", "pricing", "price", "cost", "costs", "expense", "expenses",
        "profit", "profitability", "margin", "margins", "break-even", "breakeven",
        "business model", "monetization", "monetize", "cash flow", "financial",
        "finances", "funding", "cac", "ltv", "unit economics", "setup cost", "capital",
        "roi", "projections"
    ],
    "risk": [
        "risk", "risks", "legal", "law", "laws", "regulation", "regulations",
        "regulatory", "compliance", "liability", "patent", "patents", "infringement",
        "technical risk", "security", "operational", "hazard", "vulnerability",
        "fail", "failure", "threat", "threats", "pitfall", "pitfalls", "downside"
    ],
    "market": [
        "market", "market size", "demand", "trend", "trends", "customer",
        "customers", "target customer", "target audience", "audience",
        "tam", "sam", "som", "growth", "segment", "segmentation", "user base",
        "demographic", "adoption", "industry"
    ]
}

AGENT_REGISTRY = {
    "market": {
        "agent": market_agent,
        "name": "Market Research Agent",
        "icon": "📊",
        "role_desc": "Target audience, market size (TAM/SAM/SOM), demand trends, and customer segments",
        "followups": [
            "What are the target customer demographics?",
            "What is the projected TAM, SAM, and SOM?",
            "What current market trends support this business?",
        ],
    },
    "competitor": {
        "agent": competitor_agent,
        "name": "Competitor Analysis Agent",
        "icon": "🔎",
        "role_desc": "Existing competitors, competitive differentiation, positioning, and alternatives",
        "followups": [
            "How can I differentiate from direct competitors?",
            "What are the main strengths and weaknesses of rivals?",
            "What competitive moat should we build?",
        ],
    },
    "financial": {
        "agent": financial_agent,
        "name": "Financial Feasibility Agent",
        "icon": "💰",
        "role_desc": "Setup costs, revenue models, unit economics, and break-even timelines",
        "followups": [
            "What is the recommended pricing strategy?",
            "What are the estimated initial setup costs?",
            "What is the projected break-even period?",
        ],
    },
    "risk": {
        "agent": risk_agent,
        "name": "Risk Assessment Agent",
        "icon": "⚠️",
        "role_desc": "Technical, legal, regulatory, and operational risks",
        "followups": [
            "What are the biggest legal and compliance risks?",
            "What technical risks should be prioritized?",
            "What operational risks could cause failure?",
        ],
    },
}


def route_question(question: str) -> str:
    """Classifies a user question into:

    - 'revalidate'
    - 'competitor'
    - 'financial'
    - 'risk'
    - 'market'
    - 'ambiguous'
    """
    q_lower = question.lower().strip()

    # 1. Check for explicit revalidation requests
    for pat in REVALIDATE_PATTERNS:
        if re.search(pat, q_lower):
            return "revalidate"

    # 2. Keyword scoring with boundary search and phrase weighting
    scores = {k: 0 for k in KEYWORD_MAP}
    for category, kw_list in KEYWORD_MAP.items():
        for kw in kw_list:
            pattern = r"\b" + re.escape(kw) + r"\b"
            matches = len(re.findall(pattern, q_lower))
            if matches > 0:
                weight = 2 if " " in kw else 1
                scores[category] += matches * weight

    best_category, best_score = max(scores.items(), key=lambda x: x[1])
    if best_score > 0:
        return best_category

    return "ambiguous"


def extract_sources_from_text(text: str) -> list[dict]:
    """Extract and deduplicate source URLs from agent response or tool outputs."""
    raw_urls = re.findall(r'https?://[^\s()<>"\']+', text)
    sources = []
    seen = set()

    for url in raw_urls:
        clean_url = url.rstrip(".,;:)>]")
        if clean_url not in seen and not clean_url.endswith(("api", "v1", "json")):
            seen.add(clean_url)
            parsed = urllib.parse.urlparse(clean_url)
            domain = parsed.netloc.replace("www.", "")
            title = domain or clean_url
            sources.append({"title": title, "url": clean_url})

    return sources


def execute_single_agent_followup(category: str, question: str, session: dict) -> dict:
    """Executes ONLY the selected research agent on the follow-up question,

    incorporating the startup idea and relevant previous validation findings.
    Coordinator, other research agents, Comparator/Debate, and Investor-Verdict
    are NEVER executed.
    """
    agent_info = AGENT_REGISTRY[category]
    selected_agent = agent_info["agent"]
    agent_name = agent_info["name"]
    agent_icon = agent_info["icon"]

    # Log exact verification output as required
    print(
        f"[FOLLOW-UP]\nQuestion: {question}\nRouter: {category}\nAgent: {agent_name}\nPipeline: FOLLOW-UP ONLY\n"
    )
    logger.info(
        "[FOLLOW-UP] Question: %s | Router: %s | Agent: %s | Pipeline: FOLLOW-UP ONLY",
        question, category, agent_name
    )

    startup_idea = session.get("startup_idea", "")
    agent_results = session.get("agent_results", {})
    specific_previous_context = agent_results.get(category, "")
    
    # If specific category context isn't available, fall back to initial validation raw summary
    if not specific_previous_context:
        specific_previous_context = session.get("validation_result", {}).get("raw", "")

    # Build focused follow-up task for this single agent
    task = Task(
        description=(
            f"You are providing follow-up research for the startup idea: '{startup_idea}'.\n\n"
            f"--- RELEVANT PREVIOUS VALIDATION RESEARCH ---\n"
            f"{specific_previous_context}\n"
            f"----------------------------------------------\n\n"
            f"USER FOLLOW-UP QUESTION:\n'{question}'\n\n"
            f"Instructions:\n"
            f"1. Answer the user's question directly and thoroughly from the perspective of your role: {agent_name}.\n"
            f"2. Use your web search tool ONLY if you need fresh, external data not present in the previous research.\n"
            f"   If the existing findings already answer the question, answer without unnecessary searching.\n"
            f"3. If you perform a search, cite the source links directly in your response.\n"
            f"4. Do NOT output a new overall startup score (e.g. X/10) or Go/No-Go investment verdict."
        ),
        expected_output=(
            "A structured, informative answer directly addressing the follow-up question. "
            "Use clear bullet points and cite source links if web search was used."
        ),
        agent=selected_agent,
    )

    # Run single-agent crew (Process.sequential, no manager agent)
    single_crew = Crew(
        agents=[selected_agent],
        tasks=[task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )

    result = single_crew.kickoff()
    answer_text = str(result).strip()

    sources = extract_sources_from_text(answer_text)

    return {
        "agent": category,
        "agent_name": agent_name,
        "agent_icon": agent_icon,
        "answer": answer_text,
        "sources": sources,
        "suggested_followups": agent_info["followups"],
    }
