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
import re
import time
import logging
import random
import threading
from urllib.parse import urlparse
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
from tools.search_tool import (
    set_search_event_emitter,
    clear_search_event_emitter,
    init_thread_sources,
    get_thread_sources,
    clear_thread_sources,
)

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
) -> tuple[str, list[dict]]:
    """Execute a single agent's task with automatic retry on transient errors,
    real-time activity event streaming, and agent-specific source collection.
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

        # Initialize thread-local source accumulator for this agent run
        init_thread_sources()

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
                u = ev.get("url", "")
                d = ev.get("domain", "")
                s = ev.get("snippet", "")
                supp = ev.get("supports", s)
                _emit({
                    "type": "agent_activity",
                    "stage": stage,
                    "agent": agent_name,
                    "agent_key": agent_key,
                    "message": f"Reading: {t[:60]}" if t else "Reading source...",
                    "source_title": t,
                    "source_url": u,
                    "source_domain": d,
                })
                _emit({
                    "type": "source_found",
                    "stage": stage,
                    "agent": agent_name,
                    "agent_key": agent_key,
                    "title": t,
                    "url": u,
                    "domain": d,
                    "snippet": s,
                    "supports": supp,
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

            output_text = str(res).strip()
            collected_sources = get_thread_sources()
            for s in collected_sources:
                s["agent"] = agent_name
                s["agent_key"] = agent_key

            # Also check if the agent directly cited any real external URLs in the response text
            raw_urls = re.findall(r'https?://[^\s()<>"\']+', output_text)
            seen_urls = {s.get("url") for s in collected_sources if s.get("url")}
            for u in raw_urls:
                clean_u = u.rstrip(".,;:)>]")
                if clean_u not in seen_urls and not clean_u.endswith(("api", "v1", "json")):
                    seen_urls.add(clean_u)
                    parsed_d = urlparse(clean_u).netloc.replace("www.", "") if clean_u else ""
                    collected_sources.append({
                        "title": parsed_d or clean_u,
                        "url": clean_u,
                        "domain": parsed_d,
                        "snippet": f"External source cited by {agent_name}",
                        "supports": f"Directly cited by {agent_name} in findings.",
                        "agent": agent_name,
                        "agent_key": agent_key,
                    })

            return output_text, collected_sources
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
            clear_thread_sources()
            agent.step_callback = orig_callback

    if last_exception:
        raise last_exception
    raise RuntimeError(f"Agent {agent_name} failed to execute.")


def run_validation_pipeline(
    idea: str,
    event_emitter=None,
    cancel_check=None,
) -> tuple[str, dict[str, str], dict[str, list[dict]]]:
    """Run the multi-agent validation pipeline:

    1. Coordinator Agent
    2. [Market + Competitor + Financial + Risk] (PARALLEL CONCURRENT EXECUTION)
    3. Comparator / Debate Agent
    4. Investor Verdict Agent

    Returns:
        verdict_output: str
        agent_outputs: dict[str, str]
        agent_sources: dict[str, list[dict]]
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
    coord_output, coord_sources = _execute_agent_with_retry(
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
    research_sources: dict[str, list[dict]] = {}
    # Track which agents failed so Debate can be informed
    failed_agents: dict[str, str] = {}

    def _worker(rkey):
        if cancel_check and cancel_check():
            raise InterruptedError("Validation cancelled by user.")
        agent, task, _ = research_tasks[rkey]
        out, sources = _execute_agent_with_retry(
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
        return rkey, out, sources

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
                _, out, sources = f.result()
                research_outputs[rkey] = out
                research_sources[rkey] = sources
            except InterruptedError:
                # Propagate cancellation immediately
                raise
            except Exception as exc:
                err_msg = _safe_error_str(exc)
                logger.error(
                    "[PARALLEL RESEARCH] Agent '%s' failed: %s", rkey, err_msg
                )
                failed_agents[rkey] = err_msg
                research_sources[rkey] = []
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
    debate_output, debate_raw_sources = _execute_agent_with_retry(
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

    # Associate sources referenced during debate cross-verification
    debate_sources = list(debate_raw_sources)
    debate_seen = {s.get("url") for s in debate_sources if s.get("url")}
    for rk, r_list in research_sources.items():
        for s in r_list:
            u = s.get("url", "")
            d = s.get("domain", "")
            if u and u not in debate_seen:
                if (u and u in debate_output) or (d and d in debate_output):
                    debate_seen.add(u)
                    debate_sources.append({
                        "title": s.get("title", ""),
                        "url": u,
                        "domain": d,
                        "snippet": s.get("snippet", ""),
                        "supports": f"Referenced during debate cross-verification of {AGENT_META_MAP[rk]['name']} evidence.",
                        "agent": AGENT_META_MAP["debate"]["name"],
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
    verdict_output, verdict_raw_sources = _execute_agent_with_retry(
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

    # Associate sources referenced in the final verdict investment thesis
    verdict_sources = list(verdict_raw_sources)
    verdict_seen = {s.get("url") for s in verdict_sources if s.get("url")}
    for rk, r_list in research_sources.items():
        for s in r_list:
            u = s.get("url", "")
            d = s.get("domain", "")
            if u and u not in verdict_seen:
                if (u and u in verdict_output) or (d and d in verdict_output):
                    verdict_seen.add(u)
                    verdict_sources.append({
                        "title": s.get("title", ""),
                        "url": u,
                        "domain": d,
                        "snippet": s.get("snippet", ""),
                        "supports": f"Synthesized in final investment thesis from {AGENT_META_MAP[rk]['name']} evidence.",
                        "agent": AGENT_META_MAP["verdict"]["name"],
                        "agent_key": "verdict",
                    })

    agent_sources = {
        "coordinator": coord_sources,
        "market": research_sources.get("market", []),
        "competitor": research_sources.get("competitor", []),
        "financial": research_sources.get("financial", []),
        "risk": research_sources.get("risk", []),
        "debate": debate_sources,
        "comparator": debate_sources,
        "verdict": verdict_sources,
    }

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
        "_agent_sources": agent_sources,
    }

    return verdict_output, agent_outputs, agent_sources


def run_validation(idea: str) -> str:
    """Run the full multi-agent validation and return the raw verdict string."""
    res = run_validation_pipeline(idea)
    return res[0]


if __name__ == "__main__":
    test_idea = "Portable EV battery health and degradation prediction device"
    print(run_validation(test_idea))
