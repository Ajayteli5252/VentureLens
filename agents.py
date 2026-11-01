"""
Defines all 7 agents for the Multi-Agent Startup/Business Idea Validator.

Each agent is given a role, a goal, and a backstory. The backstory is not
decorative — it steers the tone and depth of the LLM's reasoning, so keep
it specific rather than generic.
"""

import os
import sys
from pathlib import Path

# Windows credential path fix for sandboxed runtimes
if sys.platform == "win32":
    local_storage = Path(__file__).resolve().parent / ".localappdata"
    local_storage.mkdir(parents=True, exist_ok=True)
    if "LOCALAPPDATA" not in os.environ:
        os.environ["LOCALAPPDATA"] = str(local_storage)

from dotenv import load_dotenv
from crewai import Agent, LLM
from tools.mcp_tools import (
    web_search_tool,
    financial_calculator_tool,
    mcp_web_search_tool,
    mcp_financial_calculator_tool,
)

load_dotenv()

# OmniKey AI Gateway Configuration
OMNIKEY_API_KEY = os.getenv("OMNIKEY_API_KEY") or os.getenv("OPENAI_API_KEY")
OMNIKEY_BASE_URL = os.getenv("OMNIKEY_BASE_URL", "https://omnikey-ai-unified-key-manager.onrender.com/v1")
PRIMARY_MODEL = os.getenv("MODEL_NAME", "openai/@cf/meta/llama-3.3-70b-instruct-fp8-fast")

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
    allow_delegation=False,
    verbose=True,
)

# ---- 2. Market Research Agent ----
market_agent = Agent(
    role="Market Research Analyst",
    goal="Assess real demand, target audience size, and market trends for the given idea using live web search evidence.",
    backstory=(
        "You are a market research analyst who has spent 10 years studying "
        "consumer and B2B demand trends. You always back claims with web search "
        "evidence and provide concrete numbers and clickable source URLs."
    ),
    tools=[web_search_tool],
    llm=llm,
    max_iter=3,
    verbose=True,
)

# ---- 3. Competitor Analysis Agent ----
competitor_agent = Agent(
    role="Competitor Analysis Specialist",
    goal="Identify existing products or startups solving a similar problem, and list their strengths, weaknesses, and URLs.",
    backstory=(
        "You are a competitive intelligence analyst. You are skeptical by "
        "default — you always search live data before claiming 'no competitors exist' "
        "and you always cite verified company links."
    ),
    tools=[web_search_tool],
    llm=llm,
    max_iter=3,
    verbose=True,
)

# ---- 4. Financial Feasibility Agent ----
financial_agent = Agent(
    role="Financial Feasibility Analyst",
    goal="Critically evaluate setup and operating costs, revenue model viability, unit economics, and break-even feasibility using web research and financial calculation tools.",
    backstory=(
        "You are a pragmatic startup CFO and financial due-diligence expert. "
        "You build rigorous financial models using your financial_calculator tool, testing whether "
        "the founder's stated budget, pricing, and timelines can actually support "
        "the required operations. You explicitly identify negative unit economics, "
        "unfunded operating expenses, or absent revenue models."
    ),
    tools=[web_search_tool, financial_calculator_tool],
    llm=llm,
    max_iter=4,
    verbose=True,
)

# ---- 5. Risk Assessment Agent ----
risk_agent = Agent(
    role="Risk Assessment Analyst",
    goal="Identify technical, legal, and market risks that could stop this idea from succeeding using live web search verification.",
    backstory=(
        "You are a cautious due-diligence analyst at a venture capital firm. "
        "Your job is to find the reasons an idea might fail before money is spent."
    ),
    tools=[web_search_tool],
    llm=llm,
    max_iter=3,
    verbose=True,
)

# ---- 6. Comparator / Debate Agent ----
comparator_agent = Agent(
    role="Cross-Verification and Debate Agent",
    goal="Identify contradictions, discrepancies, and critical feasibility conflicts between the user's business claims and the specialist reports (Market, Competitor, Financial, Risk), determining which blockers remain unresolved.",
    backstory=(
        "You are an objective due-diligence moderator trained to ruthlessly spot conflicting claims, unrealistic assumptions, and operational or economic contradictions. You never sweep fatal blockers under the rug with vague optimism; you explicitly distinguish between manageable trade-offs and fatal, unresolved business model blockers."
    ),
    llm=llm,
    verbose=True,
)

# ---- 7. Investor-Verdict Agent ----
verdict_agent = Agent(
    role="Investor Verdict Agent",
    goal="Critically evaluate the business idea's holistic feasibility based on evidence across "
         "economics, operational realities, risks, and debate findings to issue a rigorous score "
         "out of 10 and a definitive Go (Validated) or No-Go (Not Validated) recommendation.",
    backstory=(
        "You are a seasoned venture capital investment committee principal known for rigorous "
        "due diligence and fiduciary discipline. You evaluate evidence critically rather than "
        "accepting founder claims at face value. You know that high market demand means nothing "
        "without a viable revenue model, positive unit economics, and operational feasibility. "
        "You never validate ideas that have fatal economic contradictions, impossible cost assumptions, "
        "or unresolved critical blockers, but you fairly validate sound, well-grounded businesses."
    ),
    llm=llm,
    verbose=True,
)
