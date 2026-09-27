"""
FastAPI wrapper around the VentureLens CrewAI pipeline.
Exposes:
1. POST /api/validate - Full 7-agent initial validation pipeline.
2. POST /api/follow-up - Fast follow-up question routing to ONLY the relevant research agent.
3. GET /api/session/{session_id} - Retrieve validation session state.

Run with:  uvicorn api:app --reload --port 8000
"""

import json
import re
import uuid
import logging
import queue
import threading
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


def _run_validation_background(session_id: str, idea: str):
    """Execute the full pipeline in the background while exposing an SSE stream."""
    session = SESSIONS.get(session_id)
    if session is None:
        return

    session["status"] = "running"
    session["event_log"] = []
    try:
        raw_result, agent_outputs = run_validation_pipeline(idea, event_emitter=lambda event: emit_pipeline_event(session_id, event))
        parsed = _parse_pipeline_output(raw_result)
        session["validation_result"] = {
            "raw": raw_result,
            "score": parsed["score"],
            "recommendation": parsed["recommendation"],
            "justification": parsed["justification"],
        }
        session["agent_results"] = agent_outputs
        session["result_ready"] = True
        emit_pipeline_event(session_id, {
            "type": "pipeline_completed",
            "stage": "report",
            "agent": "Validation Complete",
            "message": "Final validation report is ready.",
        })
    except Exception as exc:
        logger.exception("Background validation failed for session %s", session_id)
        session["status"] = "error"
        session["error"] = str(exc)
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
    yield
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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
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
    }
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
    return SESSIONS[session_id]


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
    """
    question = req.question.strip()

    # 1. Resolve or restore session
    session = None
    if req.session_id and req.session_id in SESSIONS:
        session = SESSIONS[req.session_id]
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
    elif SESSIONS:
        # Fallback: take most recent session
        latest_id = list(SESSIONS.keys())[-1]
        session = SESSIONS[latest_id]
    else:
        raise HTTPException(
            status_code=400,
            detail="No active validation session found. Please validate a startup idea first.",
        )

    session_id = session["session_id"]
    category = route_question(question)

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
    try:
        result = execute_single_agent_followup(category, question, session)
    except Exception as e:
        logger.exception("Single-agent follow-up failed")
        raise HTTPException(
            status_code=500,
            detail=f"Follow-up agent error ({category}): {type(e).__name__}: {str(e)}",
        )

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
