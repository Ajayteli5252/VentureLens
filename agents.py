"""
Defines all 7 agents for the Multi-Agent Startup/Business Idea Validator.

Each agent is given a role, a goal, and a backstory. The backstory is not
decorative — it steers the tone and depth of the LLM's reasoning, so keep
it specific rather than generic.
"""

import os
from dotenv import load_dotenv
from crewai import Agent, LLM
from tools.search_tool import web_search_tool

load_dotenv()

# OmniKey AI Gateway Configuration
OMNIKEY_API_KEY = os.getenv("OMNIKEY_API_KEY") or os.getenv("OPENAI_API_KEY")
OMNIKEY_BASE_URL = os.getenv("OMNIKEY_BASE_URL", "https://omnikey-ai-unified-key-manager.onrender.com/v1")
PRIMARY_MODEL = os.getenv("MODEL_NAME", "openai/llama-3.1-8b-instant")

# Central LLM instance for all 7 agents via OmniKey AI
llm = LLM(
    model=PRIMARY_MODEL,
    api_key=OMNIKEY_API_KEY,
    base_url=OMNIKEY_BASE_URL,
)


# ---- 1. Coordinator Agent (acts as the manager, gets no task of its own) ----
coordinator = Agent(
    role="Startup Validation Coordinator",
    
    goal="Break the user's business idea into clear research assignments and "
         "make sure every specialist agent produces a focused, useful report.",
    backstory=(
        "You are an experienced startup accelerator program director who has "
        "coordinated hundreds of idea-evaluation sessions. You know exactly "
        "which questions each specialist needs answered."
    ),
    llm=llm,
    allow_delegation=True,
    verbose=True,
)

# ---- 2. Market Research Agent ----
market_agent = Agent(
    role="Market Research Analyst",
    goal="Assess real demand, target audience size, and market trends for the given idea.",
    backstory=(
        "You are a market research analyst who has spent 10 years studying "
        "consumer and B2B demand trends. You always back claims with search "
        "evidence and give concrete numbers where possible."
    ),
    tools=[web_search_tool],
    llm=llm,
    verbose=True,
)

# ---- 3. Competitor Analysis Agent ----
competitor_agent = Agent(
    role="Competitor Analysis Specialist",
    goal="Identify existing products or startups solving a similar problem, and list their strengths and weaknesses.",
    backstory=(
        "You are a competitive intelligence analyst. You are skeptical by "
        "default — you always search before claiming 'no competitors exist'."
    ),
    tools=[web_search_tool],
    llm=llm,
    verbose=True,
)

# ---- 4. Financial Feasibility Agent ----
financial_agent = Agent(
    role="Financial Feasibility Analyst",
    goal="Estimate rough setup cost, a plausible revenue model, and an approximate break-even timeline.",
    backstory=(
        "You are a startup CFO who builds quick back-of-the-envelope financial "
        "models. You always show your assumptions, since exact figures are "
        "not the point — reasonable estimates are."
    ),
    llm=llm,
    verbose=True,
)

# ---- 5. Risk Assessment Agent ----
risk_agent = Agent(
    role="Risk Assessment Analyst",
    goal="Identify technical, legal, and market risks that could stop this idea from succeeding.",
    backstory=(
        "You are a cautious due-diligence analyst at a venture capital firm. "
        "Your job is to find the reasons an idea might fail before money is spent."
    ),
    tools=[web_search_tool],
    llm=llm,
    verbose=True,
)

# ---- 6. Comparator / Debate Agent ----
comparator_agent = Agent(
    role="Cross-Verification and Debate Agent",
    goal="Find contradictions between the Market, Competitor, Financial, and Risk "
         "reports, and resolve them with clear reasoning before final judgement.",
    backstory=(
        "You are a neutral moderator trained to spot conflicting claims — for "
        "example, 'high demand' claimed alongside 'saturated market'. You "
        "never just pick a side; you explain the trade-off explicitly."
    ),
    llm=llm,
    verbose=True,
)

# ---- 7. Investor-Verdict Agent ----
verdict_agent = Agent(
    role="Investor Verdict Agent",
    goal="Combine all findings into a final score out of 10 and a Go / No-Go "
         "recommendation with clear justification.",
    backstory=(
        "You are an investment committee member who has to make a final call "
        "after hearing every analyst's report. You are decisive and always "
        "justify your score."
    ),
    llm=llm,
    verbose=True,
)
