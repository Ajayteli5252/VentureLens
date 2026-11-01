"""
State Management and Context Sharing for VentureLens.

Implements Requirement 1:
Context Sharing & State Updates: Intermediate outputs from one agent must feed into another.
Use state for sharing context.
"""

import time
from typing import Literal, Any
from pydantic import BaseModel, Field
from schemas import VerdictReport


class StateTransition(BaseModel):
    from_stage: str
    to_stage: str
    timestamp: float = Field(default_factory=time.time)
    note: str = ""


class ValidationState(BaseModel):
    """
    Centralized state object managing intermediate context sharing and state updates
    across the entire multi-agent lifecycle (Coordinator -> Parallel Specialists -> Debate -> Verdict).
    """
    session_id: str
    idea: str
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    current_stage: Literal[
        "INITIALIZED",
        "COORDINATING",
        "RESEARCHING",
        "DEBATING",
        "VERDICT_EVALUATING",
        "COMPLETED",
        "FAILED"
    ] = "INITIALIZED"

    # Context shared across agents
    coordinator_brief: str = ""
    research_reports: dict[str, str] = Field(default_factory=dict)
    research_sources: dict[str, list[dict]] = Field(default_factory=dict)
    debate_report: str = ""
    verdict_report: VerdictReport | None = None
    raw_verdict_text: str = ""

    # Tracing & state audit trail
    state_transitions: list[StateTransition] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def transition_to(self, new_stage: str, note: str = "") -> None:
        """Record stage transition in state history."""
        self.state_transitions.append(
            StateTransition(
                from_stage=self.current_stage,
                to_stage=new_stage,
                timestamp=time.time(),
                note=note
            )
        )
        self.current_stage = new_stage
        self.updated_at = time.time()

    def update_coordinator(self, brief: str) -> None:
        """Update state with coordinator directives."""
        self.coordinator_brief = brief.strip()
        self.transition_to("RESEARCHING", note="Coordinator directives formulated.")

    def update_research_agent(self, agent_key: str, report: str, sources: list[dict] | None = None) -> None:
        """Update state with an individual specialist agent's findings."""
        self.research_reports[agent_key] = report.strip()
        if sources:
            self.research_sources[agent_key] = sources
        self.updated_at = time.time()

    def update_debate(self, debate_output: str) -> None:
        """Update state with comparator / cross-verification synthesis."""
        self.debate_report = debate_output.strip()
        self.transition_to("VERDICT_EVALUATING", note="Cross-verification and debate completed.")

    def update_verdict(self, verdict: VerdictReport, raw_text: str = "") -> None:
        """Update state with final investor verdict."""
        self.verdict_report = verdict
        self.raw_verdict_text = raw_text
        self.transition_to("COMPLETED", note="Final investor verdict rendered.")

    def fail(self, reason: str) -> None:
        """Mark state as failed with error context."""
        self.transition_to("FAILED", note=reason)
        self.metadata["error"] = reason

    def get_context_for_research(self) -> str:
        """Shared context for specialist agents."""
        if not self.coordinator_brief:
            return ""
        return f"\n--- COORDINATOR DIRECTIVES ---\n{self.coordinator_brief}\n"

    def get_context_for_debate(self) -> dict[str, str]:
        """Shared context feeding intermediate research reports into the Comparator/Debate agent."""
        return {
            "market_report": self.research_reports.get("market", "[No Market Data]"),
            "competitor_report": self.research_reports.get("competitor", "[No Competitor Data]"),
            "financial_report": self.research_reports.get("financial", "[No Financial Data]"),
            "risk_report": self.research_reports.get("risk", "[No Risk Data]"),
        }

    def get_context_for_verdict(self) -> dict[str, str]:
        """Shared context feeding all research reports and the debate report into the Verdict agent."""
        ctx = self.get_context_for_debate()
        ctx["debate_report"] = self.debate_report or "[No Debate Report]"
        return ctx

    def to_summary_dict(self) -> dict[str, Any]:
        """Structured dictionary of the full state."""
        return {
            "session_id": self.session_id,
            "idea": self.idea,
            "stage": self.current_stage,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "has_coordinator_brief": bool(self.coordinator_brief),
            "research_reports_count": len(self.research_reports),
            "has_debate_report": bool(self.debate_report),
            "verdict": self.verdict_report.model_dump() if self.verdict_report else None,
            "transitions": [t.model_dump() for t in self.state_transitions],
        }

