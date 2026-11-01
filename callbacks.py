"""
Task Monitoring and Execution Logging Callbacks for VentureLens.

Implements Requirement 5:
Task Monitoring & Logging using Callback functions: Agents must include a monitoring mechanism
that tracks intermediate outputs, execution flows, and errors for transparency and debugging.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Execution trace log path
LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
TRACE_LOG_PATH = LOGS_DIR / "execution_trace.jsonl"


class VentureLensMonitoringCallback:
    """Central monitoring and logging callback for tracking agentic task execution flows,
    intermediate agent reasoning, tool usage, latency, and errors.
    """

    def __init__(self, session_id: str = "", event_emitter: Callable[[dict], None] | None = None):
        self.session_id = session_id
        self.event_emitter = event_emitter
        self.execution_spans: list[dict] = []
        self._start_times: dict[str, float] = {}

    def _emit(self, event: dict) -> None:
        """Forward real-time event to streaming listeners (e.g. SSE)."""
        if self.event_emitter:
            try:
                self.event_emitter(event)
            except Exception:
                pass

    def _log_record(self, record_type: str, agent: str, stage: str, data: dict) -> None:
        """Append an audit record to the structured JSONL execution trace log."""
        record = {
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": self.session_id,
            "record_type": record_type,
            "agent": agent,
            "stage": stage,
            **data,
        }
        self.execution_spans.append(record)
        try:
            with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to write to execution_trace.jsonl: %s", e)

    def on_task_start(self, agent_name: str, stage: str, task_description: str) -> None:
        """Called when an agent begins execution on a task."""
        self._start_times[agent_name] = time.time()
        self._log_record("TASK_START", agent_name, stage, {
            "description": task_description[:200]
        })
        self._emit({
            "type": "agent_started",
            "agent": agent_name,
            "stage": stage,
            "timestamp": time.time(),
        })

    def on_agent_step(self, agent_name: str, stage: str, action: Any) -> None:
        """Called on every intermediate agent reasoning step or tool selection."""
        step_message = ""
        tool_name = ""
        tool_input = ""

        if hasattr(action, "tool") and action.tool:
            tool_name = str(action.tool)
            tool_input = str(getattr(action, "tool_input", ""))
            step_message = f"Invoking tool {tool_name} with input: {tool_input[:60]}"
        elif hasattr(action, "text") and action.text:
            step_message = str(action.text)[:120]
        else:
            step_message = str(action)[:120]

        self._log_record("AGENT_STEP", agent_name, stage, {
            "tool": tool_name,
            "tool_input": tool_input[:200],
            "step_message": step_message,
        })

        self._emit({
            "type": "agent_activity",
            "agent": agent_name,
            "stage": stage,
            "message": step_message,
        })

    def on_tool_start(self, agent_name: str, tool_name: str, tool_input: Any) -> None:
        """Called when a tool execution starts."""
        self._log_record("TOOL_START", agent_name, "tool_call", {
            "tool": tool_name,
            "input": str(tool_input)[:200],
        })

    def on_tool_end(self, agent_name: str, tool_name: str, tool_output: Any) -> None:
        """Called when a tool successfully returns output."""
        self._log_record("TOOL_END", agent_name, "tool_call", {
            "tool": tool_name,
            "output_preview": str(tool_output)[:200],
        })

    def on_task_error(self, agent_name: str, stage: str, error: Exception) -> None:
        """Called when an agent encounters an error during execution."""
        err_msg = str(error)
        self._log_record("TASK_ERROR", agent_name, stage, {
            "error_type": type(error).__name__,
            "error_message": err_msg,
        })
        self._emit({
            "type": "agent_error",
            "agent": agent_name,
            "stage": stage,
            "error": err_msg[:300],
        })

    def on_task_complete(self, agent_name: str, stage: str, output: str) -> None:
        """Called when an agent completes its task successfully."""
        start_t = self._start_times.get(agent_name, time.time())
        duration = time.time() - start_t
        self._log_record("TASK_COMPLETE", agent_name, stage, {
            "duration_seconds": round(duration, 3),
            "output_length": len(output),
            "output_preview": output[:250],
        })
        self._emit({
            "type": "agent_completed",
            "agent": agent_name,
            "stage": stage,
            "duration": round(duration, 3),
        })

    def get_session_trace(self) -> list[dict]:
        """Retrieve execution trace records for this callback session."""
        return list(self.execution_spans)

