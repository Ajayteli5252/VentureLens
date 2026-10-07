"""
FastAPI wrapper around the VentureLens CrewAI pipeline.
Exposes:
1. POST /api/validate - Full 7-agent initial validation pipeline.
2. POST /api/follow-up - Fast follow-up question routing to ONLY the relevant research agent.
3. GET  /api/session/{session_id} - Retrieve validation session state.
4. POST /api/cancel/{session_id} - Cancel a running validation pipeline.
5. POST /api/cancel-followup/{request_id} - Cancel a running follow-up request.

Run with:  uvicorn api:app --reload --port 8000
"""

import json
import re
import uuid
import time
import logging
import queue
import threading
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from crew import run_validation_pipeline
from followup import (
    route_question,
    execute_single_agent_followup,
    AGENT_REGISTRY,
)

logger = logging.getLogger(__name__)

# In-memory session store: session_id -> session dict
SESSIONS: dict[str, dict] = {}
PIPELINE_STREAMS: dict[str, queue.Queue] = {}

# Session persistence file for recovery across restarts
SESSION_STORE_PATH = Path(__file__).resolve().parent / "sessions_store.json"

def _load_persisted_sessions():
    if SESSION_STORE_PATH.exists():
        try:
            with open(SESSION_STORE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    SESSIONS.update(data)
                    logger.info("Loaded %d persisted sessions from disk.", len(data))
        except Exception as e:
            logger.warning("Could not load sessions_store.json: %s", e)

def _persist_sessions():
    try:
        serializable = {}
        for sid, sdata in list(SESSIONS.items()):
            try:
                clean_dict = {
                    k: v for k, v in sdata.items()
                    if k not in ("_thread",) and not callable(v)
                }
                json.dumps(clean_dict)
                serializable[sid] = clean_dict
            except Exception:
                pass
        with open(SESSION_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("Could not persist sessions to disk: %s", e)

# Auto-load existing sessions at module start
_load_persisted_sessions()

# Set of session_ids that the user has requested to cancel
CANCELLED_SESSIONS: set[str] = set()

# Set of follow-up request_ids that the user has requested to cancel
CANCELLED_FOLLOWUPS: set[str] = set()

# Per-request SSE event queues for follow-up streaming.
# Keyed by requestId so events are completely isolated between users/sessions.
# One dedicated background thread writes; the SSE generator reads.
FOLLOWUP_STREAMS: dict[str, queue.Queue] = {}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ValidateRequest(BaseModel):
    idea: str = Field(..., min_length=1, description="The startup/business idea to validate")


class ValidateResponse(BaseModel):
    session_id: str = Field(..., description="Unique validation session ID")
    raw: str = Field(..., description="Full raw output from the pipeline")
    score: float | None = Field(None, description="Extracted score out of 10")
    recommendation: str | None = Field(None, description="Go or No-Go")
    justification: str | None = Field(None, description="Verdict justification text")
    agent_results: dict[str, str] = Field(default_factory=dict, description="Outputs from individual research agents")


class ValidationStartResponse(BaseModel):
    session_id: str = Field(..., description="Unique validation session ID")
    status: str = Field(default="running", description="Pipeline status")


class SourceItem(BaseModel):
    title: str = Field(..., description="Domain or title of source")
    url: str = Field(..., description="Clickable source URL")


class FollowUpRequest(BaseModel):
    session_id: str | None = Field(None, description="Existing validation session ID")
    question: str = Field(..., min_length=1, description="Follow-up question or revalidation command")
    idea: str | None = Field(None, description="Fallback startup idea if session_id is omitted")
    request_id: str | None = Field(None, description="Unique ID for this follow-up request to support cancellation")


class FollowUpResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    agent: str = Field(..., description="Target category: market, competitor, financial, risk, assistant, or revalidate")
    agent_name: str = Field(..., description="Human-readable agent title")
    agent_icon: str = Field(..., description="Visual agent icon emoji")
    answer: str = Field(..., description="Direct answer from the selected agent")
    sources: list[SourceItem] = Field(default_factory=list, description="Citations and URLs")
    is_revalidation: bool = Field(False, description="True if full revalidation was triggered")
    score: float | None = Field(None, description="Updated score if revalidation was run")
    recommendation: str | None = Field(None, description="Updated recommendation if revalidation was run")
    justification: str | None = Field(None, description="Updated justification if revalidation was run")
    raw: str | None = Field(None, description="Raw pipeline output if revalidation was run")
    suggested_followups: list[str] = Field(default_factory=list, description="Next suggested questions")


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------
def _parse_pipeline_output(raw: str) -> dict:
    """Extract structured fields from the free-form pipeline string."""
    score_match = re.search(r"Score[:\s*]+([\d.]+)\s*/\s*10", raw, re.IGNORECASE)
    rec_match = re.search(r"Recommendation[:\s*]+(Go|No-?Go)\b", raw, re.IGNORECASE)
    just_match = re.search(r"Justification[:\s*]+([\s\S]+)", raw, re.IGNORECASE)

    score = None
    recommendation = None
    justification = None

    if score_match:
        try:
            score = float(score_match.group(1))
        except (ValueError, TypeError):
            pass

    if rec_match:
        rec_raw = rec_match.group(1).strip()
        recommendation = "No-Go" if "no" in rec_raw.lower() else "Go"

    if just_match:
        justification = just_match.group(1).strip()

    return {
        "score": score,
        "recommendation": recommendation,
        "justification": justification,
    }


def emit_pipeline_event(session_id: str, event: dict):
    """Queue a pipeline status event for an SSE stream."""
    if not session_id:
        return

    feed = PIPELINE_STREAMS.setdefault(session_id, queue.Queue())
    feed.put(event)

    session = SESSIONS.get(session_id)
    if session is not None:
        session.setdefault("event_log", []).append(event)
        session["last_event"] = event
        if event.get("type") == "pipeline_completed":
            session["status"] = "completed"
        elif event.get("type") == "agent_error":
            session["status"] = "error"


def _is_cancelled(session_id: str) -> bool:
    """Check if a session has been cancelled by the user."""
    return session_id in CANCELLED_SESSIONS


# ---------------------------------------------------------------------------
# Follow-up background runner (streaming version)
# ---------------------------------------------------------------------------
def _run_followup_background(request_id: str, session_id: str,
                              question: str, session: dict, category: str):
    """Execute a follow-up in a dedicated background thread, streaming events
    into the request-scoped queue.

    Safety guarantee: FOLLOWUP_STREAMS[request_id] is written ONLY by this
    single thread and read ONLY by the SSE generator for the same request_id.
    No other session or request can access this queue.
    """
    q = FOLLOWUP_STREAMS.get(request_id)
    if q is None:
        return

    def _emit(event: dict):
        """Emit to the queue only if this request has not been cancelled."""
        if request_id in CANCELLED_FOLLOWUPS:
            return
        try:
            q.put(event)
        except Exception:
            pass

    t_start = time.perf_counter()
    _emit({
        "type": "timing",
        "stage": "request_received",
        "elapsed_ms": 0.0,
        "message": f"Follow-up request initialized for {category}",
    })

    try:
        # ── Revalidation ────────────────────────────────────────────────────
        if category == "revalidate":
            idea = session.get("startup_idea", "")
            _emit({
                "type": "followup_started",
                "agent": "revalidate",
                "agent_name": "Full Validation Pipeline",
                "agent_icon": "🔄",
                "message": "Running full 7-agent revalidation pipeline…",
            })
            try:
                raw_result, agent_outputs = run_validation_pipeline(idea)
            except Exception as exc:
                _emit({"type": "followup_error",
                        "message": f"Revalidation failed: {str(exc)[:200]}"})
                return

            parsed = _parse_pipeline_output(raw_result)
            session.update({
                "validation_result": {
                    "raw": raw_result,
                    "score": parsed["score"],
                    "recommendation": parsed["recommendation"],
                    "justification": parsed["justification"],
                },
                "agent_results": agent_outputs,
                "debate_result": agent_outputs.get("comparator", ""),
                "verdict_result": agent_outputs.get("verdict", raw_result),
            })
            answer_text = (
                f"🔄 Complete revalidation finished!\n\n"
                f"**Score:** {parsed['score']}/10\n"
                f"**Recommendation:** {parsed['recommendation']}\n\n"
                f"**Verdict:** {parsed['justification'] or 'See full report for details.'}"
            )
            session.setdefault("conversation", []).extend([
                {"role": "user", "content": question},
                {"role": "ai", "content": answer_text, "agent": "revalidate",
                 "agent_name": "Full Validation Pipeline", "agent_icon": "🔄",
                 "is_revalidation": True},
            ])

            # Stream delta chunks
            words = answer_text.split(" ")
            chunk_size = 4
            for i in range(0, len(words), chunk_size):
                if request_id in CANCELLED_FOLLOWUPS:
                    raise InterruptedError("Follow-up cancelled by user.")
                chunk = " ".join(words[i : i + chunk_size])
                if i > 0:
                    chunk = " " + chunk
                _emit({"type": "followup_delta", "delta": chunk})
                time.sleep(0.01)

            total_ms = round((time.perf_counter() - t_start) * 1000, 1)
            _emit({
                "type": "followup_completed",
                "agent": "revalidate",
                "agent_name": "Full Validation Pipeline",
                "agent_icon": "🔄",
                "answer": answer_text,
                "sources": [],
                "is_revalidation": True,
                "score": parsed["score"],
                "recommendation": parsed["recommendation"],
                "justification": parsed["justification"],
                "raw": raw_result,
                "suggested_followups": [
                    "Who are my biggest competitors?",
                    "What is the market size?",
                    "What are the main risks?",
                ],
                "timing": {
                    "total_ms": total_ms,
                    "total_seconds": round(total_ms / 1000, 2),
                },
            })
            return

        # ── Ambiguous question ───────────────────────────────────────────────
        if category == "ambiguous":
            clarification = "Sure! Would you like to explore the market, competitors, financials, or risks?"
            session.setdefault("conversation", []).extend([
                {"role": "user", "content": question},
                {"role": "ai", "content": clarification, "agent": "assistant",
                 "agent_name": "VentureLens Assistant", "agent_icon": "💬"},
            ])
            _emit({"type": "followup_delta", "delta": clarification})
            total_ms = round((time.perf_counter() - t_start) * 1000, 1)
            _emit({
                "type": "followup_completed",
                "agent": "assistant",
                "agent_name": "VentureLens Assistant",
                "agent_icon": "💬",
                "answer": clarification,
                "sources": [],
                "is_revalidation": False,
                "suggested_followups": [
                    "Who are my biggest competitors?",
                    "What is the market size?",
                    "What is the revenue model?",
                    "What are the main risks?",
                ],
                "timing": {
                    "total_ms": total_ms,
                    "total_seconds": round(total_ms / 1000, 2),
                },
            })
            return

        # ── Targeted specialist agent ────────────────────────────────────────
        result = execute_single_agent_followup(
            category=category,
            question=question,
            session=session,
            event_queue=q,
            request_id=request_id,
        )
        # Update session conversation (followup_completed already emitted inside execute_single_agent_followup)
        session.setdefault("conversation", []).extend([
            {"role": "user", "content": question},
            {
                "role": "ai",
                "content": result["answer"],
                "agent": result["agent"],
                "agent_name": result["agent_name"],
                "agent_icon": result["agent_icon"],
                "sources": result["sources"],
            },
        ])

    except InterruptedError:
        _emit({"type": "followup_cancelled", "message": "Generation stopped."})
    except Exception as exc:
        logger.exception("[FOLLOW-UP BG] Failed for request %s", request_id)
        _emit({"type": "followup_error",
                "message": f"Follow-up failed: {str(exc)[:200]}"})
    finally:
        # Always put the None sentinel so the SSE generator can close cleanly
        try:
            q.put(None)
        except Exception:
            pass


def _run_validation_background(session_id: str, idea: str):
    """Execute the full pipeline in the background while exposing an SSE stream."""
    session = SESSIONS.get(session_id)
    if session is None:
        return

    session["status"] = "running"
    session["event_log"] = []

    # Wrap the emitter to short-circuit when cancelled
    def checked_emitter(event):
        # Emit the event normally
        emit_pipeline_event(session_id, event)

    # Create a cancellation-aware event emitter
    def cancellation_aware_emitter(event):
        if _is_cancelled(session_id):
            return
        emit_pipeline_event(session_id, event)

    try:
        raw_result, agent_outputs = run_validation_pipeline(
            idea,
            event_emitter=cancellation_aware_emitter,
            cancel_check=lambda: _is_cancelled(session_id),
        )

        # Check if cancelled after pipeline finished
        if _is_cancelled(session_id):
            session["status"] = "cancelled"
            emit_pipeline_event(session_id, {
                "type": "validation_cancelled",
                "stage": "report",
                "reason": "user_requested",
                "message": "Validation stopped by user.",
            })
            return

        parsed = _parse_pipeline_output(raw_result)
        session["validation_result"] = {
            "raw": raw_result,
            "score": parsed["score"],
            "recommendation": parsed["recommendation"],
            "justification": parsed["justification"],
        }
        session["agent_results"] = agent_outputs
        session["debate_result"] = agent_outputs.get("comparator", "")
        session["verdict_result"] = agent_outputs.get("verdict", raw_result)
        if "conversation" not in session or session["conversation"] is None:
            session["conversation"] = []
        if not session["conversation"]:
            session["conversation"].extend([
                {"role": "user", "content": idea},
                {
                    "role": "ai",
                    "content": parsed["justification"] or raw_result,
                    "agent": "verdict",
                    "agent_name": "Investor Verdict Agent",
                    "agent_icon": "🏆",
                    "type": "verdict",
                },
            ])
        session["result_ready"] = True
        _persist_sessions()
        emit_pipeline_event(session_id, {
            "type": "pipeline_completed",
            "stage": "report",
            "agent": "Validation Complete",
            "message": "Final validation report is ready.",
        })
    except Exception as exc:
        if _is_cancelled(session_id):
            session["status"] = "cancelled"
            _persist_sessions()
            emit_pipeline_event(session_id, {
                "type": "validation_cancelled",
                "stage": "report",
                "reason": "user_requested",
                "message": "Validation stopped by user.",
            })
            return
        logger.exception("Background validation failed for session %s", session_id)
        session["status"] = "error"
        session["error"] = str(exc)
        _persist_sessions()
        emit_pipeline_event(session_id, {
            "type": "pipeline_error",
            "stage": "report",
            "agent": "Validation Pipeline",
            "message": str(exc),
        })


# ---------------------------------------------------------------------------
# App Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("VentureLens API starting")
    _load_persisted_sessions()
    yield
    _persist_sessions()
    logger.info("VentureLens API shutting down")


app = FastAPI(
    title="VentureLens API",
    description="Multi-agent startup idea validation and fast follow-up routing powered by CrewAI",
    version="2.0.0",
    lifespan=lifespan,
)

# Allow React dev server on port 5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "VentureLens API",
        "active_sessions": len(SESSIONS),
    }


@app.post("/api/validate/start", response_model=ValidationStartResponse)
def start_validation(req: ValidateRequest):
    """Start the pipeline in the background and return a session ID immediately."""
    idea_clean = req.idea.strip()
    session_id = str(uuid.uuid4())

    SESSIONS[session_id] = {
        "session_id": session_id,
        "startup_idea": idea_clean,
        "status": "starting",
        "result_ready": False,
        "event_log": [],
        "agent_results": {},
        "validation_result": {},
        "conversation": [],
    }
    _persist_sessions()
    PIPELINE_STREAMS.setdefault(session_id, queue.Queue())

    thread = threading.Thread(
        target=_run_validation_background,
        args=(session_id, idea_clean),
        daemon=True,
    )
    thread.start()

    return ValidationStartResponse(session_id=session_id, status="running")


@app.get("/api/validate/events/{session_id}")
async def stream_validation_events(session_id: str):
    """Stream live validation lifecycle events using SSE."""
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")

    q = PIPELINE_STREAMS.setdefault(session_id, queue.Queue())

    def event_generator():
        while True:
            try:
                event = q.get(timeout=1)
            except queue.Empty:
                continue
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") in {"pipeline_completed", "pipeline_error"}:
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    session = dict(SESSIONS[session_id])
    # Include cancelled status in response
    if session_id in CANCELLED_SESSIONS and session.get("status") not in ("completed", "error"):
        session["status"] = "cancelled"
    return session


@app.post("/api/cancel/{session_id}")
async def cancel_validation(session_id: str):
    """Signal the background validation pipeline to stop."""
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    session = SESSIONS[session_id]
    if session.get("status") in ("completed", "error", "cancelled"):
        return {"status": "already_finished", "message": "Pipeline already finished."}
    CANCELLED_SESSIONS.add(session_id)
    session["status"] = "cancelled"
    # Emit cancellation event to SSE stream
    emit_pipeline_event(session_id, {
        "type": "validation_cancelled",
        "stage": "report",
        "reason": "user_requested",
        "message": "Validation stopped by user.",
    })
    logger.info("[CANCEL] Validation cancelled for session %s", session_id)
    return {"status": "cancelled", "session_id": session_id}


@app.post("/api/cancel-followup/{request_id}")
async def cancel_followup(request_id: str):
    """Signal a running follow-up request to stop."""
    CANCELLED_FOLLOWUPS.add(request_id)
    logger.info("[CANCEL-FOLLOWUP] Follow-up cancelled: %s", request_id)
    return {"status": "cancelled", "request_id": request_id}


# ---------------------------------------------------------------------------
# Follow-up streaming endpoints (non-blocking start + SSE stream)
# ---------------------------------------------------------------------------

@app.post("/api/follow-up/start")
def start_follow_up_streaming(req: FollowUpRequest):
    """Start a follow-up in the background and return immediately with a requestId.

    The client must then open GET /api/follow-up/stream/{request_id} to receive
    real-time events (followup_started, followup_activity, search_started,
    source_found, followup_completed, followup_cancelled, followup_error).

    Each requestId gets its own isolated queue — no cross-session event leakage.
    """
    t_start = time.perf_counter()
    question = req.question.strip()

    # ── Resolve session ──────────────────────────────────────────────────────
    session = None
    if req.session_id:
        if req.session_id in SESSIONS:
            session = SESSIONS[req.session_id]
        else:
            logger.warning("[FOLLOW-UP/START] Session ID '%s' not found", req.session_id)
            raise HTTPException(
                status_code=404,
                detail="Validation session not found. Please start a new validation.",
            )
    elif req.idea:
        session_id = str(uuid.uuid4())
        session = {
            "session_id": session_id,
            "startup_idea": req.idea.strip(),
            "validation_result": {},
            "agent_results": {},
            "conversation": [],
        }
        SESSIONS[session_id] = session
    else:
        raise HTTPException(
            status_code=404,
            detail="Validation session not found. Please start a new validation.",
        )

    session_id = session["session_id"]
    if "conversation" not in session or not isinstance(session["conversation"], list):
        session["conversation"] = []

    # Use client-provided requestId or generate one (client generates it so
    # the cancel endpoint can be called even before the SSE stream is opened)
    request_id = req.request_id or f"fu-{uuid.uuid4().hex[:16]}"
    session["current_followup_request_id"] = request_id

    # Route immediately (pure keyword matching — no LLM, ~0 ms)
    category = route_question(question)
    t_routed = time.perf_counter()
    logger.info(
        "[FOLLOW-UP/START] session=%s request=%s category=%s routing=%.3fs",
        session_id, request_id, category, t_routed - t_start,
    )

    # Determine agent display info for immediate UI feedback
    if category == "ambiguous":
        agent_name, agent_icon = "VentureLens Assistant", "💬"
    elif category == "revalidate":
        agent_name, agent_icon = "Full Validation Pipeline", "🔄"
    else:
        info = AGENT_REGISTRY.get(category, {})
        agent_name = info.get("name", "Specialist Agent")
        agent_icon = info.get("icon", "⚡")

    # Set up the per-request isolated SSE queue
    q: queue.Queue = queue.Queue()
    FOLLOWUP_STREAMS[request_id] = q

    # Start one dedicated background thread per request
    thread = threading.Thread(
        target=_run_followup_background,
        args=(request_id, session_id, question, session, category),
        daemon=True,
    )
    thread.start()

    t_end = time.perf_counter()
    logger.info("[FOLLOW-UP/START] thread started in %.3fs", t_end - t_start)

    return {
        "request_id": request_id,
        "session_id": session_id,
        "status": "started",
        "agent": category,
        "agent_name": agent_name,
        "agent_icon": agent_icon,
    }


@app.get("/api/follow-up/stream/{request_id}")
async def stream_followup_events(request_id: str):
    """SSE stream for a specific follow-up request.

    Each requestId has its own isolated queue written by exactly one background
    thread. No other request_id's events can appear here.
    The stream closes when the background thread sends followup_completed,
    followup_cancelled, or followup_error, or when the sentinel None is received.
    """
    q = FOLLOWUP_STREAMS.get(request_id)
    if q is None:
        raise HTTPException(
            status_code=404,
            detail="Follow-up request not found or already expired.",
        )

    def event_generator():
        while True:
            try:
                event = q.get(timeout=30)   # 30 s keepalive guard
            except Exception:
                yield ": keepalive\n\n"     # SSE comment, keeps connection alive
                continue

            if event is None:
                # Background thread finished — close the stream
                break

            yield f"data: {json.dumps(event)}\n\n"

            # Close after terminal events (belt-and-suspenders alongside None sentinel)
            if event.get("type") in {
                "followup_completed", "followup_cancelled", "followup_error"
            }:
                break

        # Clean up the queue to avoid memory accumulation
        FOLLOWUP_STREAMS.pop(request_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


@app.post("/api/validate", response_model=ValidateResponse)
def validate_idea(req: ValidateRequest):
    """Run the FULL 7-agent initial validation pipeline and establish a session."""
    idea_clean = req.idea.strip()

    try:
        raw_result, agent_outputs = run_validation_pipeline(idea_clean)
    except Exception as e:
        logger.exception("Validation pipeline failed")
        raise HTTPException(status_code=500, detail=f"Pipeline error: {type(e).__name__}: {str(e)}")

    parsed = _parse_pipeline_output(raw_result)
    session_id = str(uuid.uuid4())

    session_data = {
        "session_id": session_id,
        "startup_idea": idea_clean,
        "validation_result": {
            "raw": raw_result,
            "score": parsed["score"],
            "recommendation": parsed["recommendation"],
            "justification": parsed["justification"],
        },
        "agent_results": agent_outputs,
        "debate_result": agent_outputs.get("comparator", ""),
        "verdict_result": agent_outputs.get("verdict", raw_result),
        "conversation": [
            {"role": "user", "content": idea_clean},
            {
                "role": "ai",
                "content": parsed["justification"] or raw_result,
                "agent": "verdict",
                "agent_name": "Investor Verdict Agent",
                "agent_icon": "🏆",
                "type": "verdict",
            },
        ],
    }

    SESSIONS[session_id] = session_data

    return ValidateResponse(
        session_id=session_id,
        raw=raw_result,
        score=parsed["score"],
        recommendation=parsed["recommendation"],
        justification=parsed["justification"],
        agent_results=agent_outputs,
    )


@app.post("/api/follow-up", response_model=FollowUpResponse)
def follow_up(req: FollowUpRequest):
    """Fast follow-up endpoint.

    Routes question to ONLY the relevant research agent without running
    Coordinator, other research agents, Comparator/Debate, or Investor-Verdict.
    If explicit revalidation is requested, triggers the full 7-agent pipeline.
    Includes timing diagnostics for performance measurement.
    """
    t_start = time.perf_counter()
    question = req.question.strip()

    # 1. Resolve or restore session
    session = None
    if req.session_id:
        if req.session_id in SESSIONS:
            session = SESSIONS[req.session_id]
        else:
            logger.warning("[FOLLOW-UP] Session ID '%s' not found in SESSIONS store", req.session_id)
            raise HTTPException(
                status_code=404,
                detail="Validation session not found. Please start a new validation.",
            )
    elif req.idea:
        # Fallback: create temporary session
        session_id = str(uuid.uuid4())
        session = {
            "session_id": session_id,
            "startup_idea": req.idea.strip(),
            "validation_result": {},
            "agent_results": {},
            "conversation": [],
        }
        SESSIONS[session_id] = session
    else:
        logger.warning("[FOLLOW-UP] No session_id or startup idea provided")
        raise HTTPException(
            status_code=404,
            detail="Validation session not found. Please start a new validation.",
        )

    session_id = session["session_id"]

    # Ensure conversation array is present and is a list
    if "conversation" not in session or not isinstance(session["conversation"], list):
        session["conversation"] = []
        
    session["current_followup_request_id"] = req.request_id

    # Safe production logs
    logger.info("[FOLLOW-UP] session_id = %s", session_id)
    logger.info("[SESSION] found = true")
    logger.info("[SESSION] keys = %s", list(session.keys()))
    logger.info("[SESSION] conversation_exists = true (count=%d)", len(session["conversation"]))

    t_session = time.perf_counter()
    logger.info("[TIMING] followup_received → session_loaded: %.3fs", t_session - t_start)

    category = route_question(question)
    t_routed = time.perf_counter()
    logger.info("[ROUTER] selected_agent = %s", category)
    logger.info("[TIMING] router_completed: %.3fs", t_routed - t_start)

    # 2. Case: Explicit Revalidation Requested
    if category == "revalidate":
        idea = session.get("startup_idea") or req.idea or question
        try:
            raw_result, agent_outputs = run_validation_pipeline(idea)
        except Exception as e:
            logger.exception("Revalidation failed")
            raise HTTPException(status_code=500, detail=f"Revalidation error: {str(e)}")

        parsed = _parse_pipeline_output(raw_result)

        # Update session state with revalidation verdict
        session["validation_result"] = {
            "raw": raw_result,
            "score": parsed["score"],
            "recommendation": parsed["recommendation"],
            "justification": parsed["justification"],
        }
        session["agent_results"] = agent_outputs
        session["debate_result"] = agent_outputs.get("comparator", "")
        session["verdict_result"] = agent_outputs.get("verdict", raw_result)

        answer_text = (
            f"🔄 Complete revalidation finished!\n\n"
            f"**Score:** {parsed['score']}/10\n"
            f"**Recommendation:** {parsed['recommendation']}\n\n"
            f"**Verdict:** {parsed['justification'] or 'See full report for details.'}"
        )

        session["conversation"].append({"role": "user", "content": question})
        session["conversation"].append({
            "role": "ai",
            "content": answer_text,
            "agent": "revalidate",
            "agent_name": "Full Validation Pipeline",
            "agent_icon": "🔄",
            "is_revalidation": True,
        })

        return FollowUpResponse(
            session_id=session_id,
            agent="revalidate",
            agent_name="Full Validation Pipeline",
            agent_icon="🔄",
            answer=answer_text,
            sources=[],
            is_revalidation=True,
            score=parsed["score"],
            recommendation=parsed["recommendation"],
            justification=parsed["justification"],
            raw=raw_result,
            suggested_followups=[
                "Who are my biggest competitors?",
                "What is the market size?",
                "What are the main risks?",
            ],
        )

    # 3. Case: Ambiguous Question
    if category == "ambiguous":
        print(
            f"[FOLLOW-UP]\nQuestion: {question}\nRouter: ambiguous\nAgent: None\nPipeline: CLARIFICATION ONLY\n"
        )
        logger.info(
            "[FOLLOW-UP] Question: %s | Router: ambiguous | Agent: None | Pipeline: CLARIFICATION ONLY",
            question
        )

        clarification_text = "Sure! Would you like to explore the market, competitors, financials, or risks?"
        session["conversation"].append({"role": "user", "content": question})
        session["conversation"].append({
            "role": "ai",
            "content": clarification_text,
            "agent": "assistant",
            "agent_name": "VentureLens Assistant",
            "agent_icon": "💬",
        })

        return FollowUpResponse(
            session_id=session_id,
            agent="assistant",
            agent_name="VentureLens Assistant",
            agent_icon="💬",
            answer=clarification_text,
            sources=[],
            is_revalidation=False,
            suggested_followups=[
                "Who are my biggest competitors?",
                "What is the market size?",
                "What is the revenue model?",
                "What are the main risks?",
            ],
        )

    # 4. Case: Targeted Research Agent (Competitor, Market, Financial, or Risk)
    t_agent_start = time.perf_counter()
    logger.info("[TIMING] agent_started (%s): %.3fs", category, t_agent_start - t_start)
    try:
        result = execute_single_agent_followup(category, question, session)
    except Exception as e:
        logger.exception("Single-agent follow-up failed")
        raise HTTPException(
            status_code=500,
            detail=f"Follow-up agent error ({category}): {type(e).__name__}: {str(e)}",
        )
    t_agent_done = time.perf_counter()
    logger.info("[TIMING] agent_completed (%s): %.3fs total from followup_received", category, t_agent_done - t_start)

    session["conversation"].append({"role": "user", "content": question})
    session["conversation"].append({
        "role": "ai",
        "content": result["answer"],
        "agent": result["agent"],
        "agent_name": result["agent_name"],
        "agent_icon": result["agent_icon"],
        "sources": result["sources"],
    })

    return FollowUpResponse(
        session_id=session_id,
        agent=result["agent"],
        agent_name=result["agent_name"],
        agent_icon=result["agent_icon"],
        answer=result["answer"],
        sources=[SourceItem(**s) for s in result["sources"]],
        is_revalidation=False,
        suggested_followups=result.get("suggested_followups", []),
    )
