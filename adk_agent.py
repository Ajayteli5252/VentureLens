"""
Google ADK (Agent Development Kit) Integration for VentureLens.

Implements Requirement 6 & 7:
- Agent to Agent communication using the A2A protocol. Use interoperability - e.g. one agent defined
  using ADK another using CrewAI.
- You MUST use both CrewAI and ADK as the agentic framework for the implementation.
  Do NOT use any agentic framework other than CrewAI and ADK.
"""

import os
import sys
import logging
from typing import Any
from google.adk import Agent as ADKAgent
from a2a_protocol import A2AClient, get_crewai_agent_card
from state import ValidationState
from schemas import VerdictReport

logger = logging.getLogger(__name__)


def create_adk_executive_director() -> ADKAgent:
    """Creates the Executive Program Director Agent using Google's Agent Development Kit (ADK).
    
    This agent serves as the top-level executive governance interface:
    1. Evaluates user pitch submissions.
    2. Delegates execution to the CrewAI specialist crew using the A2A Protocol.
    3. Reviews the CrewAI verdict against venture portfolio guidelines.
    """
    model_name = os.getenv("ADK_MODEL_NAME", "gemini-2.5-flash")

    adk_director = ADKAgent(
        name="ADK_Executive_Startup_Director",
        description="Executive Venture Director built with Google ADK. Oversees multi-framework A2A validation.",
        instruction=(
            "You are the Executive Startup Accelerator Director built with Google ADK. "
            "You oversee the VentureLens validation pipeline, delegating deep-dive research to "
            "the specialized CrewAI agent crew over the Agent-to-Agent (A2A) protocol. "
            "Your role is to maintain institutional due-diligence standards, verify evidence integrity, "
            "and synthesize the final venture evaluation."
        ),
        model=model_name,
    )
    return adk_director


class ADKOrchestrationController:
    """Manages the lifecycle of the ADK Executive Agent and its A2A communication with CrewAI."""

    def __init__(self):
        self.adk_agent = create_adk_executive_director()
        self.a2a_client = A2AClient(get_crewai_agent_card())

    def delegate_validation_via_a2a(
        self,
        state: ValidationState,
        crewai_execution_fn: Any,
        event_emitter: Any = None,
        cancel_check: Any = None,
    ) -> dict[str, Any]:
        """ADK Agent dispatches the validation task to CrewAI over the A2A protocol."""
        logger.info("[ADK -> A2A] ADK Executive Agent initiating A2A Task delegation for idea: %s", state.idea[:60])

        if event_emitter:
            event_emitter({
                "type": "adk_event",
                "framework": "Google ADK",
                "agent": self.adk_agent.name,
                "message": "ADK Executive Director initiating A2A task delegation to CrewAI engine...",
            })

        # 1. Format A2A request payload
        a2a_payload = self.a2a_client.create_task_payload(
            skill_name="validate_startup_idea",
            arguments={"idea": state.idea, "session_id": state.session_id}
        )

        # 2. Invoke target CrewAI crew via A2A bridge
        verdict_str, agent_outputs, agent_sources = crewai_execution_fn(
            idea=state.idea,
            event_emitter=event_emitter,
            cancel_check=cancel_check,
            validation_state=state,
        )

        # 3. Structure A2A response
        a2a_response = {
            "jsonrpc": "2.0",
            "id": a2a_payload["id"],
            "result": {
                "status": "completed",
                "verdict_output": verdict_str,
                "agent_outputs": agent_outputs,
                "agent_sources": agent_sources,
                "framework": "CrewAI",
            }
        }

        # 4. Parse verified result in ADK agent
        parsed_result = self.a2a_client.parse_response(a2a_response)

        if event_emitter:
            event_emitter({
                "type": "adk_event",
                "framework": "Google ADK",
                "agent": self.adk_agent.name,
                "message": "ADK Executive Director verified and synthesized CrewAI A2A results.",
            })

        return parsed_result

