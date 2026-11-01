"""
Observability and Tracing for VentureLens Agentic System.

Implements Requirement 9:
Implement a suitable Observability mechanism for tracing (auditability and provenance).
For example, you may use an open-source observability platform like LangFuse.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TRACES_DIR = Path(__file__).resolve().parent / "traces"
TRACES_DIR.mkdir(exist_ok=True)

# Attempt Langfuse connection if credentials exist
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

_langfuse_client = None

if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY:
    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
        logger.info("Langfuse cloud client initialized successfully.")
    except Exception as e:
        logger.warning("Could not initialize Langfuse client: %s. Using local tracing.", e)


class ObservabilityTracer:
    """Manages auditability, provenance, span hierarchies, and token/latency tracing."""

    def __init__(self, session_id: str, idea: str):
        self.session_id = session_id
        self.idea = idea
        self.start_time = time.time()
        self.trace_data = {
            "session_id": session_id,
            "idea": idea,
            "start_time": self.start_time,
            "spans": [],
            "metadata": {},
        }
        self.langfuse_trace = None

        if _langfuse_client:
            try:
                self.langfuse_trace = _langfuse_client.trace(
                    name="venturelens_validation",
                    session_id=session_id,
                    input={"idea": idea},
                    metadata={"frameworks": ["CrewAI", "Google ADK"], "protocol": "A2A"},
                )
            except Exception as e:
                logger.warning("Failed to start Langfuse trace: %s", e)

    def start_span(self, name: str, stage: str, agent: str, input_payload: Any = None) -> dict[str, Any]:
        """Start a new execution span for an agent or process."""
        span_id = f"span_{len(self.trace_data['spans']) + 1}"
        span = {
            "span_id": span_id,
            "name": name,
            "stage": stage,
            "agent": agent,
            "start_time": time.time(),
            "input": input_payload,
            "output": None,
            "status": "RUNNING",
        }
        self.trace_data["spans"].append(span)

        if self.langfuse_trace:
            try:
                lf_span = self.langfuse_trace.span(
                    name=name,
                    input=input_payload,
                    metadata={"agent": agent, "stage": stage},
                )
                span["_lf_span"] = lf_span
            except Exception:
                pass

        return span

    def end_span(self, span: dict[str, Any], output_payload: Any, status: str = "COMPLETED", metadata: dict | None = None) -> None:
        """Mark a span as complete and record duration and output."""
        end_time = time.time()
        span["end_time"] = end_time
        span["duration_seconds"] = round(end_time - span["start_time"], 3)
        span["output"] = str(output_payload)[:500] if output_payload else None
        span["status"] = status
        if metadata:
            span.setdefault("metadata", {}).update(metadata)

        lf_span = span.pop("_lf_span", None)
        if lf_span:
            try:
                lf_span.end(
                    output=output_payload,
                    metadata=metadata or {},
                )
            except Exception:
                pass

    def record_generation(self, agent: str, model: str, prompt: str, completion: str, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        """Record an LLM prompt and completion for auditability and provenance."""
        gen_record = {
            "type": "generation",
            "agent": agent,
            "model": model,
            "timestamp": time.time(),
            "prompt_preview": prompt[:300],
            "completion_preview": completion[:300],
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
        self.trace_data.setdefault("generations", []).append(gen_record)

        if self.langfuse_trace:
            try:
                self.langfuse_trace.generation(
                    name=f"{agent}_inference",
                    model=model,
                    input=prompt,
                    output=completion,
                    usage={"input": prompt_tokens, "output": completion_tokens},
                )
            except Exception:
                pass

    def finalize_trace(self, verdict_summary: Any = None) -> dict[str, Any]:
        """Save the completed trace locally and sync to Langfuse."""
        self.trace_data["end_time"] = time.time()
        self.trace_data["total_duration"] = round(self.trace_data["end_time"] - self.start_time, 3)
        self.trace_data["verdict_summary"] = verdict_summary

        if self.langfuse_trace:
            try:
                self.langfuse_trace.update(
                    output=verdict_summary,
                )
                if _langfuse_client:
                    _langfuse_client.flush()
            except Exception:
                pass

        # Save local audit trace file for provenance
        trace_file = TRACES_DIR / f"trace_{self.session_id}.json"
        try:
            with open(trace_file, "w", encoding="utf-8") as f:
                json.dump(self.trace_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Could not write trace file: %s", e)

        return self.trace_data

