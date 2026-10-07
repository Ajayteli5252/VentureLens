"""
Assembles the 7-agent crew and exposes a single run_validation() function
that api.py and frontend call.

Includes robust retry logic with exponential back-off so that transient
Groq errors (output_parse_failed, 429 rate-limit, 503 overloaded) do not
kill the entire pipeline.
"""

import time
import logging
import random
from crewai import Crew, Process
from agents import (
    coordinator, market_agent, competitor_agent,
    financial_agent, risk_agent, comparator_agent, verdict_agent,
)
from tasks import build_tasks

logger = logging.getLogger(__name__)

AGENT_STAGE_MAP = {
    "Startup Validation Coordinator": ("coordinator", "Coordinator Agent"),
    "Market Research Analyst": ("research", "Market Research Agent"),
    "Competitor Analysis Specialist": ("research", "Competitor Analysis Agent"),
    "Financial Feasibility Analyst": ("research", "Financial Feasibility Agent"),
    "Risk Assessment Analyst": ("research", "Risk Assessment Agent"),
    "Cross-Verification and Debate Agent": ("debate", "Comparator / Debate Agent"),
    "Investor Verdict Agent": ("verdict", "Investor-Verdict Agent"),
}

# ---- Retry configuration ----
MAX_RETRIES = 4          # total attempts = 1 original + 4 retries
BASE_DELAY = 5           # seconds before first retry
MAX_DELAY = 60           # cap on back-off delay

# Error substrings that are worth retrying (transient / model-side issues / rate limits)
RETRYABLE_ERRORS = [
    "output_parse_failed",
    "rate limit",
    "resource_exhausted",
    "quota",
    "exceeded your current quota",
    "429",
    "503",
    "overloaded",
    "capacity",
    "All fallback attempts failed",
    "no running event loop",
    "Parsing failed",
    "502",
    "bad gateway",
    "failed to parse tool call arguments",
]


def _is_retryable(error: Exception) -> bool:
    """Return True if the error is transient and worth retrying."""
    msg = str(error).lower()
    return any(keyword.lower() in msg for keyword in RETRYABLE_ERRORS)


def _wrap_agent_execution(agent, event_emitter, cancel_check=None):
    """Add non-invasive execution hooks without changing the actual pipeline."""
    if event_emitter is None:
        return

    agent_cls = type(agent)
    if getattr(agent_cls, "_venturLens_wrapped", False):
        return

    original_execute_task = agent_cls.execute_task

    def wrapped_execute_task(self, task, context=None, tools=None):
        # Check cancellation before starting each agent task
        if cancel_check and cancel_check():
            raise InterruptedError("Validation cancelled by user.")
        stage_key, agent_name = AGENT_STAGE_MAP.get(getattr(self, "role", ""), (None, getattr(self, "role", "Agent")))
        if stage_key:
            event_emitter({
                "type": "agent_started",
                "stage": stage_key,
                "agent": agent_name,
                "message": "Understanding your startup idea and assigning research tasks..." if stage_key == "coordinator" else "Analyzing startup idea and gathering evidence...",
            })
            
        original_step_callback = getattr(self, "step_callback", None)
        
        def cancellation_step_callback(step):
            if cancel_check and cancel_check():
                raise InterruptedError("Validation cancelled by user.")
            
            # Emit real research activity from the agent step
            try:
                # 'step' is typically a tuple of (AgentAction, text) or just AgentAction/AgentStep
                # We do best effort to extract the tool name and input
                action = step[0] if isinstance(step, tuple) else step
                
                if hasattr(action, "tool") and action.tool:
                    tool_name = str(action.tool).lower()
                    tool_input = str(getattr(action, "tool_input", ""))
                    # Truncate input for UI display
                    if len(tool_input) > 60:
                        tool_input = tool_input[:60] + "..."
                        
                    if "search" in tool_name:
                        event_emitter({
                            "type": "agent_activity",
                            "stage": stage_key,
                            "agent": agent_name,
                            "message": f"Searching: {tool_input}"
                        })
                    elif "read" in tool_name or "scrape" in tool_name or "webpage" in tool_name:
                        event_emitter({
                            "type": "agent_activity",
                            "stage": stage_key,
                            "agent": agent_name,
                            "message": f"Reading source: {tool_input}"
                        })
                    else:
                        event_emitter({
                            "type": "agent_activity",
                            "stage": stage_key,
                            "agent": agent_name,
                            "message": f"Using tool: {action.tool}"
                        })
                elif hasattr(action, "text") and action.text:
                    event_emitter({
                        "type": "agent_activity",
                        "stage": stage_key,
                        "agent": agent_name,
                        "message": "Analyzing findings..."
                    })
            except Exception:
                pass
                
            if original_step_callback:
                original_step_callback(step)

        # Apply the callback for this run
        self.step_callback = cancellation_step_callback
        
        try:
            result = original_execute_task(self, task, context=context, tools=tools)
            # Check cancellation after each agent completes too
            if cancel_check and cancel_check():
                raise InterruptedError("Validation cancelled by user.")
            if stage_key:
                event_emitter({
                    "type": "agent_completed",
                    "stage": stage_key,
                    "agent": agent_name,
                })
            return result
        except InterruptedError:
            raise
        except Exception:
            if stage_key:
                event_emitter({
                    "type": "agent_error",
                    "stage": stage_key,
                    "agent": agent_name,
                    "message": "Agent execution failed.",
                })
            raise
        finally:
            self.step_callback = original_step_callback

    agent_cls.execute_task = wrapped_execute_task
    agent_cls._venturLens_wrapped = True


def run_validation_pipeline(idea: str, event_emitter=None, cancel_check=None) -> tuple[str, dict[str, str]]:
    """Run the full multi-agent validation with automatic retries and returns

    (raw_result, agent_outputs_dict).
    """
    print(
        "[VALIDATION]\nCoordinator\nMarket Agent\nCompetitor Agent\nFinancial Agent\nRisk Agent\nComparator/Debate\nInvestor-Verdict\n"
    )
    logger.info(
        "[VALIDATION]\nCoordinator\nMarket Agent\nCompetitor Agent\nFinancial Agent\nRisk Agent\nComparator/Debate\nInvestor-Verdict"
    )

    last_exception = None

    if event_emitter:
        from tools.search_tool import set_search_event_emitter, clear_search_event_emitter
        def _pipeline_search_emitter(ev):
            event_emitter({
                "type": "agent_activity",
                "stage": "research",
                "message": ev.get("message", "Searching web...")
            })
        set_search_event_emitter(_pipeline_search_emitter)

        event_emitter({
            "type": "pipeline_started",
            "stage": "coordinator",
            "agent": "Coordinator Agent",
            "message": "Understanding your startup idea and assigning research tasks...",
        })

        for agent in [coordinator, market_agent, competitor_agent, financial_agent, risk_agent, comparator_agent, verdict_agent]:
            _wrap_agent_execution(agent, event_emitter, cancel_check=cancel_check)

    try:
        for attempt in range(1, MAX_RETRIES + 2):  # +2 because range is exclusive and attempt 1 is the original
            # Check cancellation before each retry attempt
            if cancel_check and cancel_check():
                raise InterruptedError("Validation cancelled by user.")
            try:
                tasks = build_tasks(idea)

                crew = Crew(
                    agents=[market_agent, competitor_agent, financial_agent,
                            risk_agent, comparator_agent, verdict_agent],
                    tasks=tasks,
                    process=Process.hierarchical,
                    manager_agent=coordinator,
                    memory=False,                  # Disabled memory (vector embedder not needed)
                    verbose=True,
                    max_rpm=3,                     # Throttled to 3 RPM to respect Gemini Free Tier rate limits (20 req/min limit)
                    max_retry_limit=3,             # CrewAI internal per-agent retries
                )

                result = crew.kickoff(inputs={"idea": idea})

                # Extract individual task outputs for follow-up context
                agent_outputs = {}
                if hasattr(result, "tasks_output") and result.tasks_output:
                    keys = ["market", "competitor", "financial", "risk", "comparator", "verdict"]
                    for i, task_out in enumerate(result.tasks_output):
                        key = keys[i] if i < len(keys) else f"task_{i}"
                        agent_outputs[key] = str(getattr(task_out, "raw", "") or "")

                return str(result), agent_outputs

            except Exception as e:
                last_exception = e
                if attempt > MAX_RETRIES or not _is_retryable(e):
                    logger.error("Non-retryable error or retries exhausted: %s", e)
                    raise

                # Exponential back-off with jitter
                delay = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
                jitter = random.uniform(0, delay * 0.3)
                wait = delay + jitter

                logger.warning(
                    "Attempt %d/%d failed (%s). Retrying in %.1fs…",
                    attempt, MAX_RETRIES + 1, type(e).__name__, wait,
                )
                print(
                    f"⚠️  Attempt {attempt}/{MAX_RETRIES + 1} failed: {type(e).__name__}. "
                    f"Retrying in {wait:.0f}s…"
                )
                time.sleep(wait)

        # Should not reach here, but safety net
        raise last_exception  # type: ignore[misc]

    finally:
        if event_emitter:
            try:
                clear_search_event_emitter()
            except Exception:
                pass


def run_validation(idea: str) -> str:
    """Run the full multi-agent validation and return the raw verdict string."""
    raw_result, _ = run_validation_pipeline(idea)
    return raw_result


if __name__ == "__main__":
    # Quick command-line test: python crew.py
    test_idea = "Portable EV battery health and degradation prediction device"
    print(run_validation(test_idea))
