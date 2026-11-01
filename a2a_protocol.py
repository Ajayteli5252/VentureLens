"""
Agent-to-Agent (A2A) Protocol Implementation for VentureLens.

Implements Requirement 6 & 7:
- Agent to Agent communication using the A2A protocol. Use interoperability - e.g. one agent defined
  using ADK another using CrewAI.
- You MUST use both CrewAI and ADK as the agentic framework for the implementation.
  Do NOT use any agentic framework other than CrewAI and ADK.
"""

import time
import json
import uuid
from typing import Any
from pydantic import BaseModel, Field


class AgentSkill(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class AgentCard(BaseModel):
    """A2A Standard Agent Card (.well-known/agent-card.json) for service discovery."""
    id: str = "urn:agent:venturelens:crewai-engine"
    name: str = "VentureLens CrewAI Validation Engine"
    description: str = "7-Agent CrewAI system providing parallel research, cross-verification debate, and investor verdicts."
    version: str = "1.0.0"
    framework: str = "CrewAI"
    protocols_supported: list[str] = Field(default_factory=lambda: ["a2a/v1", "json-rpc/2.0"])
    endpoint: str = "/a2a/v1/tasks"
    skills: list[AgentSkill] = Field(default_factory=list)


def get_crewai_agent_card() -> dict[str, Any]:
    """Generate the official A2A Agent Card for the CrewAI validation crew."""
    card = AgentCard(
        skills=[
            AgentSkill(
                name="validate_startup_idea",
                description="Conducts multi-agent due-diligence across market, competitors, financial unit economics, and risk.",
                parameters={
                    "idea": {"type": "string", "description": "The startup business concept to evaluate"},
                }
            ),
            AgentSkill(
                name="single_agent_followup",
                description="Direct follow-up question answering by a specific research specialist.",
                parameters={
                    "question": {"type": "string", "description": "Specific question"},
                    "category": {"type": "string", "description": "market, competitor, financial, or risk"},
                }
            )
        ]
    )
    return card.model_dump()


class A2ATaskRequest(BaseModel):
    """A2A JSON-RPC 2.0 Task Request Schema."""
    jsonrpc: str = "2.0"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    method: str = "a2a.tasks.execute"
    params: dict[str, Any]


class A2ATaskResponse(BaseModel):
    """A2A JSON-RPC 2.0 Task Response Schema."""
    jsonrpc: str = "2.0"
    id: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class A2AClient:
    """A2A Protocol Client used by the ADK Agent to communicate with the CrewAI Multi-Agent System."""

    def __init__(self, target_agent_card: dict[str, Any] | None = None):
        self.target_agent_card = target_agent_card or get_crewai_agent_card()

    def create_task_payload(self, skill_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Format an A2A task message conforming to A2A protocol."""
        req = A2ATaskRequest(
            params={
                "target_agent": self.target_agent_card.get("id"),
                "skill": skill_name,
                "arguments": arguments,
                "timestamp": time.time(),
            }
        )
        return req.model_dump()

    def parse_response(self, response_payload: dict[str, Any]) -> dict[str, Any]:
        """Validate and extract results from an A2A response payload."""
        if "error" in response_payload and response_payload["error"]:
            raise RuntimeError(f"A2A Protocol Error: {response_payload['error']}")
        return response_payload.get("result", {})

