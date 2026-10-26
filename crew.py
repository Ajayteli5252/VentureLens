"""
Assembles the 7-agent validation pipeline and exposes run_validation_pipeline()
and run_validation().

Architecture:
1. Coordinator Agent (analyzes idea & creates research directives)
2. [Market + Competitor + Financial + Risk] (REAL CONCURRENT PARALLEL EXECUTION)
3. Cross-Verification and Debate Agent (starts ONLY after all 4 research agents complete)
4. Investor Verdict Agent (starts ONLY after Debate completes)
5. Final Report synthesis

Includes robust per-agent retry logic with exponential back-off for transient errors,
granular real-time SSE activity streaming, and cancellation support.

Windows UTF-8 fix: all print() calls use _safe_print() which encodes to UTF-8 and
ignores unencodable characters, preventing charmap/cp1252 crashes.
"""

import sys
import time
import logging
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from crewai import Crew
from agents import (
    coordinator, market_agent, competitor_agent,
    financial_agent, risk_agent, comparator_agent, verdict_agent,
)
from tasks import (
    build_coordinator_task,
    build_research_tasks,
    build_comparator_task,
    build_verdict_task,
    build_tasks,
)
from tools.search_tool import set_search_event_emitter, clear_search_event_emitter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Windows UTF-8 safe console output
# On Windows the default console encoding is cp1252 which cannot encode many
# Unicode characters found in web-search results. We wrap print() so that any
# unencodable character is replaced with '?' instead of raising UnicodeEncodeError.
# ---------------------------------------------------------------------------
def _safe_print(*args, **kwargs):
    """Unicode-safe replacement for print() on Windows cp1252 consoles."""
    try:
        text = " ".join(str(a) for a in args)
        # Encode to UTF-8 bytes then decode back — this forces a clean roundtrip.
        # If the underlying stdout can't handle UTF-8 we fall back gracefully.
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout.buffer.write((text + "\n").encode('utf-8', errors='replace'))
            sys.stdout.buffer.flush()
        else:
            safe = text.encode('utf-8', errors='replace').decode('utf-8')
            print(safe, **kwargs)
    except Exception:
        try:
            # Last-resort fallback: ASCII only
            print(text.encode('ascii', errors='replace').decode('ascii'), **kwargs)
        except Exception:
            pass  # Never crash the pipeline over a print statement


def _safe_error_str(exc: Exception) -> str:
    """Convert an exception to a UTF-8 safe string, replacing unencodable chars."""
    try:
        msg = str(exc)
        return msg.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return repr(exc).encode('ascii', errors='replace').decode('ascii')


# ---- Retry configuration ----
MAX_RETRIES = 4          # total attempts = 1 original + 4 retries
BASE_DELAY = 4           # seconds before first retry
MAX_DELAY = 45           # cap on back-off delay

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


AGENT_META_MAP = {
    "coordinator": {
        "agent": coordinator,
        "name": "Coordinator Agent",
        "stage": "coordinator",
        "start_msg": "Understanding your startup idea and assigning research briefs...",
        "activity_fallback": "Formulating problem statement and research assignments...",
    },
    "market": {
        "agent": market_agent,
        "name": "Market Research Agent",
        "stage": "research",
        "start_msg": "Analyzing target market size and demand trends...",
        "activity_fallback": "Analyzing market size, trends, and target audience...",
    },
    "competitor": {
        "agent": competitor_agent,
        "name": "Competitor Analysis Agent",
        "stage": "research",
        "start_msg": "Searching competitor landscape and existing players...",
        "activity_fallback": "Comparing competitor strengths, weaknesses, and moats...",
    },
    "financial": {
        "agent": financial_agent,
        "name": "Financial Feasibility Agent",
        "stage": "research",
        "start_msg": "Calculating setup costs, unit economics, and break-even timeline...",
        "activity_fallback": "Calculating setup costs, unit economics, and break-even...",
    },
    "risk": {
        "agent": risk_agent,
        "name": "Risk Assessment Agent",
        "stage": "research",
        "start_msg": "Assessing critical technical, regulatory, and market risks...",
        "activity_fallback": "Assessing technical, legal, and market risks...",
    },
    "debate": {
        "agent": comparator_agent,
        "name": "Comparator / Debate Agent",
        "stage": "debate",
        "start_msg": "Cross-checking Market, Competitor, Financial, and Risk reports for contradictions...",
        "activity_fallback": "Comparing cross-domain findings and resolving contradictions...",
    },
    "verdict": {
        "agent": verdict_agent,
        "name": "Investor Verdict Agent",
        "stage": "verdict",
        "start_msg": "Synthesizing full evaluation into final score and recommendation...",
        "activity_fallback": "Synthesizing all research and debate into final investment score...",
    },
}


def _execute_agent_with_retry(
    agent,
    task,
    agent_key: str,
    event_emitter=None,
    cancel_check=None,
) -> str:
    """Execute a single agent's task with automatic retry on transient errors

    and real-time activity event streaming.
    """
    info = AGENT_META_MAP[agent_key]
    agent_name = info["name"]
    stage = info["stage"]

    def _emit(event):
        if event_emitter:
            try:
                event_emitter(event)
            except Exception:
                pass

    last_exception = None

    for attempt in range(1, MAX_RETRIES + 2):
        if cancel_check and cancel_check():
            raise InterruptedError("Validation cancelled by user.")

        # Thread-local search tool event emitter
        def _thread_search_emitter(ev):
            if cancel_check and cancel_check():
                return
            ev_type = ev.get("type")
            msg = ev.get("message", "")
            if ev_type == "search_started":
                q = msg.replace("Searching: ", "").strip()
                _emit({
                    "type": "agent_activity",
                    "stage": stage,
                    "agent": agent_name,
                    "agent_key": agent_key,
                    "message": f"Searching: {q[:60]}",
                })
            elif ev_type == "source_found":
                t = ev.get("title", "")
                _emit({
                    "type": "agent_activity",
                    "stage": stage,
                    "agent": agent_name,
                    "agent_key": agent_key,
                    "message": f"Reading: {t[:60]}" if t else "Reading source...",
                    "source_title": t,
                    "source_url": ev.get("url", ""),
                })

        set_search_event_emitter(_thread_search_emitter)

        # Agent step callback
        orig_callback = getattr(agent, "step_callback", None)

        def _step_callback(step):
            if cancel_check and cancel_check():
                raise InterruptedError("Validation cancelled by user.")
            try:
                action = step[0] if isinstance(step, tuple) else step
                if hasattr(action, "tool") and action.tool:
                    tool_name = str(action.tool).lower()
                    tool_input = str(getattr(action, "tool_input", "")).strip()
                    if len(tool_input) > 60:
                        tool_input = tool_input[:60] + "..."
                    if "search" in tool_name:
                        _emit({
                            "type": "agent_activity",
                            "stage": stage,
                            "agent": agent_name,
                            "agent_key": agent_key,
                            "message": f"Searching: {tool_input}",
                        })
                    elif any(w in tool_name for w in ("read", "scrape", "webpage")):
                        _emit({
                            "type": "agent_activity",
                            "stage": stage,
                            "agent": agent_name,
                            "agent_key": agent_key,
                            "message": f"Reading: {tool_input}",
                        })
                    else:
                        _emit({
                            "type": "agent_activity",
                            "stage": stage,
                            "agent": agent_name,
                            "agent_key": agent_key,
                            "message": f"Using {action.tool}: {tool_input}",
                        })
                elif hasattr(action, "text") and action.text:
                    _emit({
                        "type": "agent_activity",
                        "stage": stage,
                        "agent": agent_name,
                        "agent_key": agent_key,
                        "message": info["activity_fallback"],
                    })
            except Exception:
                pass
            if orig_callback:
                try:
                    orig_callback(step)
                except Exception:
                    pass

        agent.step_callback = _step_callback

        try:
            t0 = time.time()
            logger.info("[%s START] key=%s, timestamp=%.3f", agent_name, agent_key, t0)
            crew = Crew(agents=[agent], tasks=[task], verbose=True)
            res = crew.kickoff()
            t1 = time.time()
            logger.info("[%s COMPLETE] key=%s, timestamp=%.3f (duration=%.2fs)", agent_name, agent_key, t1, t1 - t0)
            return str(res).strip()
        except InterruptedError:
            raise
        except Exception as e:
            last_exception = e
            if attempt > MAX_RETRIES or not _is_retryable(e):
                logger.error("[%s] Non-retryable error or retries exhausted: %s", agent_name, e)
                raise
            delay = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
            jitter = random.uniform(0, delay * 0.3)
            wait = delay + jitter
            logger.warning("[%s] Attempt %d failed (%s). Retrying in %.1fs...", agent_name, attempt, type(e).__name__, wait)
            time.sleep(wait)
        finally:
            clear_search_event_emitter()
            agent.step_callback = orig_callback

    if last_exception:
        raise last_exception
    raise RuntimeError(f"Agent {agent_name} failed to execute.")


def run_validation_pipeline(
    idea: str,
    event_emitter=None,
    cancel_check=None,
) -> tuple[str, dict[str, str]]:
    """Run the multi-agent validation pipeline:

    1. Coordinator Agent
    2. [Market + Competitor + Financial + Risk] (PARALLEL CONCURRENT EXECUTION)
    3. Comparator / Debate Agent
    4. Investor Verdict Agent
    """
    logger.info("[VALIDATION PIPELINE START] Idea: %s", idea)
    _safe_print(
        "\n[VENTURELENS VALIDATION EXECUTION]\n"
        "1. Coordinator Agent\n"
        "2. [Market + Competitor + Financial + Risk] (PARALLEL CONCURRENT EXECUTION)\n"
        "3. Debate / Comparison Agent\n"
        "4. Investor Verdict Agent\n"
    )

    def _emit(event):
        if event_emitter:
            try:
                event_emitter(event)
            except Exception:
                pass

    if cancel_check and cancel_check():
        raise InterruptedError("Validation cancelled by user.")

    # -----------------------------------------------------------------------
    # Stage 1: Coordinator Agent
    # -----------------------------------------------------------------------
    _emit({
        "type": "pipeline_started",
        "stage": "coordinator",
        "agent": "Coordinator Agent",
        "agent_key": "coordinator",
        "message": AGENT_META_MAP["coordinator"]["start_msg"],
    })
    _emit({
        "type": "agent_started",
        "stage": "coordinator",
        "agent": "Coordinator Agent",
        "agent_key": "coordinator",
        "message": AGENT_META_MAP["coordinator"]["start_msg"],
    })

    coord_task = build_coordinator_task(idea)
    coord_output = _execute_agent_with_retry(
        agent=coordinator,
        task=coord_task,
        agent_key="coordinator",
        event_emitter=_emit,
        cancel_check=cancel_check,
    )
    _emit({
        "type": "agent_completed",
        "stage": "coordinator",
        "agent": "Coordinator Agent",
        "agent_key": "coordinator",
    })

    if cancel_check and cancel_check():
        raise InterruptedError("Validation cancelled by user.")

    # -----------------------------------------------------------------------
    # Stage 2: 4 Research Specialists in PARALLEL
    # -----------------------------------------------------------------------
    research_tasks = build_research_tasks(idea, coordinator_brief=coord_output)
    research_keys = ["market", "competitor", "financial", "risk"]

    # Signal frontend that all 4 research agents are starting in parallel
    for rkey in research_keys:
        info = AGENT_META_MAP[rkey]
        _emit({
            "type": "agent_started",
            "stage": "research",
            "agent": info["name"],
            "agent_key": rkey,
            "message": info["start_msg"],
        })

    t_parallel_start = time.time()
    logger.info(
        "[PARALLEL RESEARCH BATCH] Launching 4 research agents concurrently at timestamp=%.3f",
        t_parallel_start,
    )
    research_outputs = {}
    # Track which agents failed so Debate can be informed
    failed_agents: dict[str, str] = {}

    def _worker(rkey):
        if cancel_check and cancel_check():
            raise InterruptedError("Validation cancelled by user.")
        agent, task, _ = research_tasks[rkey]
        out = _execute_agent_with_retry(
            agent=agent,
            task=task,
            agent_key=rkey,
            event_emitter=_emit,
            cancel_check=cancel_check,
        )
        _emit({
            "type": "agent_completed",
            "stage": "research",
            "agent": AGENT_META_MAP[rkey]["name"],
            "agent_key": rkey,
        })
        return rkey, out

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_worker, k): k for k in research_keys}

        # Poll loop ensuring prompt cancellation responsiveness
        while not all(f.done() for f in futures):
            if cancel_check and cancel_check():
                for f in futures:
                    f.cancel()
                raise InterruptedError("Validation cancelled by user.")
            time.sleep(0.1)

        # Collect results — handle each future independently so one failure
        # does NOT abort the remaining agents.
        for f, rkey in futures.items():
            try:
                _, out = f.result()
                research_outputs[rkey] = out
            except InterruptedError:
                # Propagate cancellation immediately
                raise
            except Exception as exc:
                err_msg = _safe_error_str(exc)
                logger.error(
                    "[PARALLEL RESEARCH] Agent '%s' failed: %s", rkey, err_msg
                )
                failed_agents[rkey] = err_msg
                # Emit agent_error so frontend shows "Failed" instead of hanging
                _emit({
                    "type": "agent_error",
                    "stage": "research",
                    "agent": AGENT_META_MAP[rkey]["name"],
                    "agent_key": rkey,
                    "message": f"{AGENT_META_MAP[rkey]['name']} failed: {err_msg[:200]}",
                    "error": err_msg[:500],
                })

    t_parallel_end = time.time()
    successful = [k for k in research_keys if k not in failed_agents]
    logger.info(
        "[PARALLEL RESEARCH BATCH COMPLETE] %d/%d agents succeeded in %.2fs "
        "(start=%.3f, end=%.3f). Failed: %s",
        len(successful), len(research_keys),
        t_parallel_end - t_parallel_start, t_parallel_start, t_parallel_end,
        list(failed_agents.keys()) or "none",
    )

    # If ALL research agents failed, abort the pipeline — there is nothing to debate.
    if not successful:
        raise RuntimeError(
            "All research agents failed. Cannot proceed to Debate. "
            f"Failures: { {k: v[:120] for k, v in failed_agents.items()} }"
        )

    if cancel_check and cancel_check():
        raise InterruptedError("Validation cancelled by user.")

    # -----------------------------------------------------------------------
    # Stage 3: Debate / Comparison Agent (starts only after all 4 finish)
    # -----------------------------------------------------------------------
    _emit({
        "type": "agent_started",
        "stage": "debate",
        "agent": "Comparator / Debate Agent",
        "agent_key": "debate",
        "message": AGENT_META_MAP["debate"]["start_msg"],
    })

    # Build failure notes so Debate knows which agents didn't produce data
    def _agent_report(key):
        if key in failed_agents:
            return f"[DATA UNAVAILABLE — {AGENT_META_MAP[key]['name']} failed: {failed_agents[key][:200]}]"
        return research_outputs.get(key, "[No data returned]")

    debate_task = build_comparator_task(
        idea,
        market_report=_agent_report("market"),
        competitor_report=_agent_report("competitor"),
        financial_report=_agent_report("financial"),
        risk_report=_agent_report("risk"),
    )
    debate_output = _execute_agent_with_retry(
        agent=comparator_agent,
        task=debate_task,
        agent_key="debate",
        event_emitter=_emit,
        cancel_check=cancel_check,
    )
    _emit({
        "type": "agent_completed",
        "stage": "debate",
        "agent": "Comparator / Debate Agent",
        "agent_key": "debate",
    })

    if cancel_check and cancel_check():
        raise InterruptedError("Validation cancelled by user.")

    # -----------------------------------------------------------------------
    # Stage 4: Investor Verdict Agent (starts only after Debate completes)
    # -----------------------------------------------------------------------
    _emit({
        "type": "agent_started",
        "stage": "verdict",
        "agent": "Investor Verdict Agent",
        "agent_key": "verdict",
        "message": AGENT_META_MAP["verdict"]["start_msg"],
    })

    verdict_task = build_verdict_task(
        idea,
        market_report=_agent_report("market"),
        competitor_report=_agent_report("competitor"),
        financial_report=_agent_report("financial"),
        risk_report=_agent_report("risk"),
        debate_report=debate_output,
    )
    verdict_output = _execute_agent_with_retry(
        agent=verdict_agent,
        task=verdict_task,
        agent_key="verdict",
        event_emitter=_emit,
        cancel_check=cancel_check,
    )
    _emit({
        "type": "agent_completed",
        "stage": "verdict",
        "agent": "Investor Verdict Agent",
        "agent_key": "verdict",
    })

    agent_outputs = {
        "coordinator": coord_output,
        "market": research_outputs.get("market", _agent_report("market")),
        "competitor": research_outputs.get("competitor", _agent_report("competitor")),
        "financial": research_outputs.get("financial", _agent_report("financial")),
        "risk": research_outputs.get("risk", _agent_report("risk")),
        "comparator": debate_output,
        "debate": debate_output,
        "verdict": verdict_output,
        # Expose failure metadata so callers can surface it
        "_failed_agents": failed_agents,
    }

    return verdict_output, agent_outputs


def run_validation(idea: str) -> str:
    """Run the full multi-agent validation and return the raw verdict string."""
    raw_result, _ = run_validation_pipeline(idea)
    return raw_result


if __name__ == "__main__":
    test_idea = "Portable EV battery health and degradation prediction device"
    print(run_validation(test_idea))
