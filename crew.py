"""
Assembles the 7-agent validation pipeline and exposes run_validation_pipeline()
and run_validation().

Upgraded with full support for:
1. Context Sharing & State Updates: Uses ValidationState container.
2. Tool Integration using MCP: Invokes tools via Model Context Protocol bridge.
3. Structured Output using Pydantic: Generates typed VerdictReport with Markdown, Table, and JSON.
4. Agentic Design Patterns: Orchestrator-Worker, Parallel Fan-Out, Debate/Cross-Verification.
5. Task Monitoring & Logging: Integrated with VentureLensMonitoringCallback and audit log.
6. A2A Protocol & ADK Interoperability: Native state and dispatch hooks.
7. Security Guardrails: Input injection detection, tool return validation, output range checks.
8. Observability & Tracing: Langfuse and OpenTelemetry span auditability.
9. End-to-End Performance Evaluation: Token counting, latency breakdown, cost model.

Windows UTF-8 fix: all print() calls use _safe_print().
"""

import sys
import os
import re
import time
import logging
import random
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# Windows credential path fix
if sys.platform == "win32":
    local_storage = Path(__file__).resolve().parent / ".localappdata"
    local_storage.mkdir(parents=True, exist_ok=True)
    if "LOCALAPPDATA" not in os.environ:
        os.environ["LOCALAPPDATA"] = str(local_storage)

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
from tools.mcp_tools import (
    set_search_event_emitter,
    clear_search_event_emitter,
    init_thread_sources,
    get_thread_sources,
    clear_thread_sources,
)
from state import ValidationState
from schemas import VerdictReport, ScoreBreakdown, SourceCitation
from guardrails import InputGuardrail, ToolReturnGuardrail, OutputGuardrail
from callbacks import VentureLensMonitoringCallback
from observability import ObservabilityTracer
from evaluation import compute_performance_metrics, PipelinePerformanceMetrics

logger = logging.getLogger(__name__)


def _safe_print(*args, **kwargs):
    """Unicode-safe replacement for print() on Windows cp1252 consoles."""
    try:
        text = " ".join(str(a) for a in args)
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout.buffer.write((text + "\n").encode('utf-8', errors='replace'))
            sys.stdout.buffer.flush()
        else:
            safe = text.encode('utf-8', errors='replace').decode('utf-8')
            print(safe, **kwargs)
    except Exception:
        try:
            print(text.encode('ascii', errors='replace').decode('ascii'), **kwargs)
        except Exception:
            pass


def _safe_error_str(exc: Exception) -> str:
    """Convert an exception to a UTF-8 safe string."""
    try:
        msg = str(exc)
        return msg.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return repr(exc).encode('ascii', errors='replace').decode('ascii')


# ---- Retry configuration ----
MAX_RETRIES = 4
BASE_DELAY = 4
MAX_DELAY = 45

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
        "start_msg": "Analyzing target market size and demand trends via MCP...",
        "activity_fallback": "Analyzing market size, trends, and target audience...",
    },
    "competitor": {
        "agent": competitor_agent,
        "name": "Competitor Analysis Agent",
        "stage": "research",
        "start_msg": "Searching competitor landscape and existing players via MCP...",
        "activity_fallback": "Comparing competitor strengths, weaknesses, and moats...",
    },
    "financial": {
        "agent": financial_agent,
        "name": "Financial Feasibility Agent",
        "stage": "research",
        "start_msg": "Calculating setup costs, unit economics, and break-even via MCP tools...",
        "activity_fallback": "Calculating setup costs, unit economics, and break-even...",
    },
    "risk": {
        "agent": risk_agent,
        "name": "Risk Assessment Agent",
        "stage": "research",
        "start_msg": "Assessing critical technical, regulatory, and market risks via MCP...",
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
        "start_msg": "Synthesizing full evaluation into structured Pydantic verdict...",
        "activity_fallback": "Synthesizing all research and debate into final investment score...",
    },
}


def parse_to_verdict_report(raw: str, sources: list[dict] | None = None) -> VerdictReport:
    """Converts raw LLM verdict output into a validated Pydantic VerdictReport model."""
    score_match = re.search(r"Score[:\s*]+([\d.]+)\s*/\s*10", raw, re.IGNORECASE)
    rec_match = re.search(r"Recommendation[:\s*]+([^\n\r]+)", raw, re.IGNORECASE)
    just_match = re.search(r"Justification[:\s*]+([\s\S]+?)(?:Market Demand Score|Key Strengths|$)", raw, re.IGNORECASE)

    market_match = re.search(r"Market Demand Score[:\s*]+([\d.]+)", raw, re.IGNORECASE)
    moat_match = re.search(r"Competitive Moat Score[:\s*]+([\d.]+)", raw, re.IGNORECASE)
    fin_match = re.search(r"Unit Economics Score[:\s*]+([\d.]+)", raw, re.IGNORECASE)
    risk_match = re.search(r"Risk Profile Score[:\s*]+([\d.]+)", raw, re.IGNORECASE)

    score = float(score_match.group(1)) if score_match else 6.0
    score = max(1.0, min(10.0, score))

    rec = "Go"
    if rec_match:
        r = rec_match.group(1).strip().lower()
        if "no" in r:
            rec = "No-Go"
        elif "go" in r or "validate" in r:
            rec = "Go"
        else:
            rec = "No-Go" if score < 6.0 else "Go"
    else:
        rec = "No-Go" if score < 6.0 else "Go"

    just = just_match.group(1).strip() if just_match else "Rigorous multi-agent assessment completed across market, competition, financial feasibility, and risk."

    m_score = float(market_match.group(1)) if market_match else score
    c_score = float(moat_match.group(1)) if moat_match else score
    f_score = float(fin_match.group(1)) if fin_match else score
    r_score = float(risk_match.group(1)) if risk_match else score

    strengths_match = re.search(r"Key Strengths[:\s*]+([\s\S]+?)(?:Fatal Blockers|$)", raw, re.IGNORECASE)
    blockers_match = re.search(r"Fatal Blockers[:\s*]+([\s\S]+?)(?:Manageable Risks|$)", raw, re.IGNORECASE)
    risks_match = re.search(r"Manageable Risks[:\s*]+([\s\S]+?)$", raw, re.IGNORECASE)

    def _extract_bullets(txt: str | None) -> list[str]:
        if not txt:
            return []
        items = [line.strip().lstrip("-*•0123456789. ") for line in txt.split("\n") if line.strip()]
        return [i for i in items if i and "none" not in i.lower()]

    strengths = _extract_bullets(strengths_match.group(1) if strengths_match else "")
    blockers = _extract_bullets(blockers_match.group(1) if blockers_match else "")
    risks = _extract_bullets(risks_match.group(1) if risks_match else "")

    citations = []
    if sources:
        for s in sources[:8]:
            u = s.get("url")
            if u and ToolReturnGuardrail.validate_source_url(u):
                citations.append(SourceCitation(
                    title=s.get("title") or s.get("domain") or "Source",
                    url=u,
                    domain=s.get("domain", ""),
                    supports=s.get("supports", s.get("snippet", ""))[:120],
                ))

    return VerdictReport(
        score=score,
        recommendation=rec,
        justification=just,
        score_breakdown=ScoreBreakdown(
            market_demand=max(1.0, min(10.0, m_score)),
            competition_moat=max(1.0, min(10.0, c_score)),
            unit_economics=max(1.0, min(10.0, f_score)),
            risk_profile=max(1.0, min(10.0, r_score)),
        ),
        key_strengths=strengths,
        fatal_blockers=blockers,
        manageable_risks=risks,
        sources=citations,
    )


def _execute_agent_with_retry(
    agent,
    task,
    agent_key: str,
    event_emitter=None,
    cancel_check=None,
    monitoring_cb: VentureLensMonitoringCallback | None = None,
    tracer: ObservabilityTracer | None = None,
) -> tuple[str, list[dict]]:
    """Execute a single agent's task with automatic retry, callbacks, and observability tracing."""
    info = AGENT_META_MAP[agent_key]
    agent_name = info["name"]
    stage = info["stage"]

    def _emit(event):
        if event_emitter:
            try:
                event_emitter(event)
            except Exception:
                pass

    if monitoring_cb:
        monitoring_cb.on_task_start(agent_name, stage, getattr(task, "description", ""))

    span = None
    if tracer:
        span = tracer.start_span(
            name=f"{agent_name}_execution",
            stage=stage,
            agent=agent_name,
            input_payload={"agent_key": agent_key},
        )

    last_exception = None

    for attempt in range(1, MAX_RETRIES + 2):
        if cancel_check and cancel_check():
            raise InterruptedError("Validation cancelled by user.")

        init_thread_sources()

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
        orig_callback = getattr(agent, "step_callback", None)

        def _step_callback(step):
            if cancel_check and cancel_check():
                raise InterruptedError("Validation cancelled by user.")
            if monitoring_cb:
                try:
                    action = step[0] if isinstance(step, tuple) else step
                    monitoring_cb.on_agent_step(agent_name, stage, action)
                except Exception:
                    pass
            try:
                action = step[0] if isinstance(step, tuple) else step
                if hasattr(action, "tool") and action.tool:
                    tool_name = str(action.tool).lower()
                    tool_input = str(getattr(action, "tool_input", "")).strip()
                    if len(tool_input) > 60:
                        tool_input = tool_input[:60] + "..."
                    _emit({
                        "type": "agent_activity",
                        "stage": stage,
                        "agent": agent_name,
                        "agent_key": agent_key,
                        "message": f"Using MCP tool {action.tool}: {tool_input}",
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
            crew = Crew(agents=[agent], tasks=[task], verbose=True)
            res = crew.kickoff()
            t1 = time.time()

            output_text = str(res).strip()
            # Tool return guardrail sanitization
            _, safe_output = ToolReturnGuardrail.validate_search_output(output_text)
            output_text = safe_output

            collected_sources = get_thread_sources()
            seen_urls = {s.get('url') for s in collected_sources if s.get('url')}
            for s in collected_sources:
                s['agent'] = agent_name
                s['agent_key'] = agent_key

            # 1. Parse markdown links [Title](https://...)
            md_links = re.findall(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', output_text)
            for title_match, url_match in md_links:
                clean_u = url_match.rstrip('.,;:)>]')
                if clean_u not in seen_urls and ToolReturnGuardrail.validate_source_url(clean_u):
                    seen_urls.add(clean_u)
                    parsed_d = urlparse(clean_u).netloc.replace('www.', '')
                    collected_sources.append({
                        'title': title_match.strip() or parsed_d or clean_u,
                        'url': clean_u,
                        'domain': parsed_d,
                        'snippet': f'Cited in {agent_name} research findings',
                        'supports': f'Directly cited by {agent_name}: {title_match.strip()}',
                        'agent': agent_name,
                        'agent_key': agent_key,
                    })

            # 2. Parse raw URLs
            raw_urls = re.findall(r'https?://[^\s()<>"]+', output_text)
            for u in raw_urls:
                clean_u = u.rstrip('.,;:)>]')
                if clean_u not in seen_urls and ToolReturnGuardrail.validate_source_url(clean_u):
                    seen_urls.add(clean_u)
                    parsed_d = urlparse(clean_u).netloc.replace('www.', '')
                    collected_sources.append({
                        'title': parsed_d or clean_u,
                        'url': clean_u,
                        'domain': parsed_d,
                        'snippet': f'External source cited by {agent_name}',
                        'supports': f'Directly cited by {agent_name} in findings.',
                        'agent': agent_name,
                        'agent_key': agent_key,
                    })

            if monitoring_cb:
                monitoring_cb.on_task_complete(agent_name, stage, output_text)

            if tracer and span:
                tracer.end_span(span, output_payload=output_text[:300], status="COMPLETED")

            return output_text, collected_sources
        except InterruptedError:
            if monitoring_cb:
                monitoring_cb.on_task_error(agent_name, stage, InterruptedError("Cancelled by user"))
            if tracer and span:
                tracer.end_span(span, output_payload="Cancelled", status="CANCELLED")
            raise
        except Exception as e:
            last_exception = e
            if monitoring_cb:
                monitoring_cb.on_task_error(agent_name, stage, e)
            if attempt > MAX_RETRIES or not _is_retryable(e):
                logger.error("[%s] Non-retryable error or retries exhausted: %s", agent_name, e)
                if tracer and span:
                    tracer.end_span(span, output_payload=str(e), status="FAILED")
                raise
            delay = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
            jitter = random.uniform(0, delay * 0.3)
            wait = delay + jitter
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
    validation_state: ValidationState | None = None,
) -> tuple[str, dict[str, str], dict[str, list[dict]]]:
    """Runs the full multi-agent validation pipeline:
    1. Input Guardrail Security Screening
    2. Coordinator Agent (State initialized & context updated)
    3. 4 Research Specialists in Parallel with MCP Tools
    4. Comparator / Debate Agent (Cross-verification)
    5. Investor Verdict Agent (Structured Pydantic VerdictReport)
    6. Performance Evaluation & Langfuse/OTel Tracing Finalization
    """
    session_id = str(uuid.uuid4())
    logger.info("[VALIDATION PIPELINE START] Session=%s, Idea=%s", session_id, idea[:60])

    def _emit(event):
        if event_emitter:
            try:
                event_emitter(event)
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # Step 0: Security Guardrail on Input
    # -----------------------------------------------------------------------
    is_safe, error_msg, sanitized_idea = InputGuardrail.validate_prompt(idea)
    if not is_safe:
        _emit({
            "type": "guardrail_blocked",
            "message": error_msg,
        })
        raise ValueError(f"Security Guardrail Violation: {error_msg}")

    clean_idea = sanitized_idea

    # Initialize State & Observability & Callbacks
    state = validation_state or ValidationState(session_id=session_id, idea=clean_idea)
    state.transition_to("COORDINATING", note="Starting Coordinator Agent.")

    monitoring_cb = VentureLensMonitoringCallback(session_id=session_id, event_emitter=_emit)
    tracer = ObservabilityTracer(session_id=session_id, idea=clean_idea)

    stage_durations: dict[str, float] = {}

    if cancel_check and cancel_check():
        raise InterruptedError("Validation cancelled by user.")

    # -----------------------------------------------------------------------
    # Stage 1: Coordinator Agent
    # -----------------------------------------------------------------------
    t_coord_0 = time.time()
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

    coord_task = build_coordinator_task(clean_idea)
    coord_output, coord_sources = _execute_agent_with_retry(
        agent=coordinator,
        task=coord_task,
        agent_key="coordinator",
        event_emitter=_emit,
        cancel_check=cancel_check,
        monitoring_cb=monitoring_cb,
        tracer=tracer,
    )
    stage_durations["Coordinator"] = time.time() - t_coord_0
    state.update_coordinator(coord_output)

    _emit({
        "type": "agent_completed",
        "stage": "coordinator",
        "agent": "Coordinator Agent",
        "agent_key": "coordinator",
    })

    if cancel_check and cancel_check():
        raise InterruptedError("Validation cancelled by user.")

    # -----------------------------------------------------------------------
    # Stage 2: 4 Research Specialists in PARALLEL via MCP Tools
    # -----------------------------------------------------------------------
    t_parallel_0 = time.time()
    research_tasks = build_research_tasks(clean_idea, coordinator_brief=state.coordinator_brief)
    research_keys = ["market", "competitor", "financial", "risk"]

    for rkey in research_keys:
        info = AGENT_META_MAP[rkey]
        _emit({
            "type": "agent_started",
            "stage": "research",
            "agent": info["name"],
            "agent_key": rkey,
            "message": info["start_msg"],
        })

    research_outputs = {}
    research_sources: dict[str, list[dict]] = {}
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
            monitoring_cb=monitoring_cb,
            tracer=tracer,
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
        while not all(f.done() for f in futures):
            if cancel_check and cancel_check():
                for f in futures:
                    f.cancel()
                raise InterruptedError("Validation cancelled by user.")
            time.sleep(0.1)

        for f, rkey in futures.items():
            try:
                _, out, sources = f.result()
                research_outputs[rkey] = out
                research_sources[rkey] = sources
                state.update_research_agent(rkey, out, sources)
            except InterruptedError:
                raise
            except Exception as exc:
                err_msg = _safe_error_str(exc)
                failed_agents[rkey] = err_msg
                research_sources[rkey] = []
                _emit({
                    "type": "agent_error",
                    "stage": "research",
                    "agent": AGENT_META_MAP[rkey]["name"],
                    "agent_key": rkey,
                    "message": f"{AGENT_META_MAP[rkey]['name']} failed: {err_msg[:200]}",
                    "error": err_msg[:500],
                })

    stage_durations["Parallel Research"] = time.time() - t_parallel_0
    successful = [k for k in research_keys if k not in failed_agents]

    if not successful:
        state.fail("All research agents failed.")
        raise RuntimeError("All research agents failed. Cannot proceed to Debate.")

    if cancel_check and cancel_check():
        raise InterruptedError("Validation cancelled by user.")

    # -----------------------------------------------------------------------
    # Stage 3: Comparator / Debate Agent (Cross-Verification)
    # -----------------------------------------------------------------------
    t_debate_0 = time.time()
    state.transition_to("DEBATING", note="Starting Comparator / Debate cross-verification.")

    _emit({
        "type": "agent_started",
        "stage": "debate",
        "agent": "Comparator / Debate Agent",
        "agent_key": "debate",
        "message": AGENT_META_MAP["debate"]["start_msg"],
    })

    def _agent_report(key):
        if key in failed_agents:
            return f"[DATA UNAVAILABLE — {AGENT_META_MAP[key]['name']} failed: {failed_agents[key][:200]}]"
        return research_outputs.get(key, "[No data returned]")

    debate_task = build_comparator_task(
        clean_idea,
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
        monitoring_cb=monitoring_cb,
        tracer=tracer,
    )
    stage_durations["Debate & Cross-Verification"] = time.time() - t_debate_0
    state.update_debate(debate_output)

    _emit({
        "type": "agent_completed",
        "stage": "debate",
        "agent": "Comparator / Debate Agent",
        "agent_key": "debate",
    })

    debate_sources = list(debate_raw_sources)

    if cancel_check and cancel_check():
        raise InterruptedError("Validation cancelled by user.")

    # -----------------------------------------------------------------------
    # Stage 4: Investor Verdict Agent (Structured Pydantic Output)
    # -----------------------------------------------------------------------
    t_verdict_0 = time.time()
    state.transition_to("VERDICT_EVALUATING", note="Investor Verdict Agent synthesizing final verdict.")

    _emit({
        "type": "agent_started",
        "stage": "verdict",
        "agent": "Investor Verdict Agent",
        "agent_key": "verdict",
        "message": AGENT_META_MAP["verdict"]["start_msg"],
    })

    verdict_task = build_verdict_task(
        clean_idea,
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
        monitoring_cb=monitoring_cb,
        tracer=tracer,
    )
    stage_durations["Investor Verdict"] = time.time() - t_verdict_0

    # Combine all verified sources
    all_sources = []
    seen_urls = set()
    for s_list in [coord_sources, *research_sources.values(), debate_sources, verdict_raw_sources]:
        for s in s_list:
            u = s.get("url")
            if u and u not in seen_urls:
                seen_urls.add(u)
                all_sources.append(s)

    # Parse and validate structured Pydantic report
    verdict_report = parse_to_verdict_report(verdict_output, sources=all_sources)
    OutputGuardrail.validate_verdict(verdict_report.score, verdict_report.recommendation, verdict_report.justification)

    state.update_verdict(verdict_report, raw_text=verdict_output)

    _emit({
        "type": "agent_completed",
        "stage": "verdict",
        "agent": "Investor Verdict Agent",
        "agent_key": "verdict",
    })

    # -----------------------------------------------------------------------
    # Stage 5: End-to-End Performance, Cost & Runtime Evaluation
    # -----------------------------------------------------------------------
    prompt_chars = len(clean_idea) + len(coord_output) + sum(len(v) for v in research_outputs.values()) + len(debate_output)
    output_chars = len(verdict_output)
    performance_metrics = compute_performance_metrics(
        session_id=session_id,
        stage_durations=stage_durations,
        total_prompt_chars=prompt_chars,
        total_output_chars=output_chars,
    )

    # Finalize Langfuse / OTel trace
    tracer.finalize_trace(verdict_summary={
        "score": verdict_report.score,
        "recommendation": verdict_report.recommendation,
        "runtime_seconds": performance_metrics.total_duration_seconds,
        "cost_inr": performance_metrics.cost.cost_inr,
    })

    agent_sources = {
        "coordinator": coord_sources,
        "market": research_sources.get("market", []),
        "competitor": research_sources.get("competitor", []),
        "financial": research_sources.get("financial", []),
        "risk": research_sources.get("risk", []),
        "debate": debate_sources,
        "comparator": debate_sources,
        "verdict": all_sources,
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
        "_failed_agents": failed_agents,
        "_agent_sources": agent_sources,
        # Enhanced State & Requirements integration objects
        "_validation_state": state.to_summary_dict(),
        "_verdict_report": verdict_report.model_dump(),
        "_verdict_markdown": verdict_report.to_markdown(),
        "_verdict_table": verdict_report.to_table(),
        "_performance_metrics": performance_metrics.model_dump(),
        "_performance_markdown": performance_metrics.to_markdown(),
    }

    return verdict_output, agent_outputs, agent_sources


def run_validation(idea: str) -> str:
    """Run the full multi-agent validation and return the raw verdict string."""
    res = run_validation_pipeline(idea)
    return res[0]


if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) > 1:
        test_idea = " ".join(sys.argv[1:])
    else:
        try:
            user_input = input("Enter your startup idea to validate: ").strip()
            test_idea = user_input if user_input else "AI copilot for independent veterinary clinics with $99/mo subscription"
        except (EOFError, KeyboardInterrupt):
            test_idea = "AI copilot for independent veterinary clinics with $99/mo subscription"

    _safe_print(f"\n============================================================")
    _safe_print(f"VENTURELENS TERMINAL VALIDATION RUNNER")
    _safe_print(f"Idea: {test_idea}")
    _safe_print(f"============================================================\n")

    verdict_text, outputs, sources = run_validation_pipeline(test_idea)

    _safe_print("\n" + "=" * 60)
    _safe_print(outputs.get("_verdict_markdown", verdict_text))
    _safe_print("=" * 60)
    _safe_print(outputs.get("_performance_markdown", ""))
