"""
Security Guardrails and Validation for VentureLens Agentic System.

Implements Requirement 8:
Secure the Agentic System - use Guardrails for safeguard, callbacks for data validation
(e.g. type checking from a tool's return, user prompt parsing for toxic or abusive language
or prompt injection attacks, etc.).
"""

import re
import html
from urllib.parse import urlparse
from typing import Any

# ---------------------------------------------------------------------------
# 1. Prompt Injection & Toxicity Patterns
# ---------------------------------------------------------------------------
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|system)\s+(instructions?|prompts?)",
    r"you\s+are\s+now\s+(an?\s+)?unrestricted",
    r"jailbreak",
    r"dan\s+mode",
    r"system\s+override",
    r"developer\s+mode\s+output",
    r"<\|im_start\|>",
    r"<\|system\|>",
    r"\[INST\].*\[/INST\]",
    r"bypass\s+(content\s+)?filters?",
    r"reveal\s+(your\s+)?(system\s+prompt|hidden\s+instructions)",
    r"output\s+the\s+exact\s+prompt\s+above",
    r"forget\s+everything\s+you\s+were\s+told",
]

TOXIC_MALICIOUS_PATTERNS = [
    r"\b(make|create|build|construct)\s+(a\s+)?(bomb|explosive|weapon)\b",
    r"\b(bomb|explosive|weapon)\s+(making|recipe|build|manufacture)\b",
    r"\bhow\s+to\s+(hack|ddos|exploit)\b",
    r"\b(malware|ransomware|keylogger|trojan)\b",
    r"\bcredit\s+card\s+(theft|fraud|skimmer)\b",
    r"\bassassinate|murder\b",
]


class InputGuardrail:
    """Guardrail inspecting and sanitizing user prompts before feeding them to agents."""

    @staticmethod
    def validate_prompt(user_text: str) -> tuple[bool, str, str]:
        """Validates user text against prompt injections, toxic content, and format abuses.

        Returns:
            (is_valid: bool, error_message: str, sanitized_text: str)
        """
        if not user_text or not user_text.strip():
            return False, "Input cannot be empty.", ""

        cleaned = user_text.strip()

        # Length check
        if len(cleaned) < 5:
            return False, "Startup idea description is too short to validate (minimum 5 characters).", ""
        if len(cleaned) > 5000:
            return False, "Input exceeds maximum allowed length of 5000 characters.", ""

        # Prompt Injection Detection
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                return False, "Security Alert: Prompt injection or instruction overriding detected. Request blocked.", ""

        # Toxic / Malicious Intent Detection
        for pattern in TOXIC_MALICIOUS_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                return False, "Security Alert: Input contains prohibited or harmful content. Request blocked.", ""

        # HTML / Script Tag Sanitization
        sanitized = html.escape(cleaned)

        return True, "", sanitized


class ToolReturnGuardrail:
    """Data validation callback layer ensuring tool outputs are safe, validly typed, and uncorrupted."""

    @staticmethod
    def validate_search_output(tool_result: Any) -> tuple[bool, str]:
        """Type checks and sanitizes web search returns before agent ingestion."""
        if not isinstance(tool_result, str):
            return False, f"[Tool Validation Error: Expected str from search tool, got {type(tool_result).__name__}]"

        clean_text = re.sub(r"<script.*?>.*?</script>", "", tool_result, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<iframe.*?>.*?</iframe>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)

        if len(clean_text) > 25000:
            clean_text = clean_text[:25000] + "\n... [Search results truncated for safety]"

        return True, clean_text

    @staticmethod
    def validate_calculator_inputs(setup_costs: Any, monthly_opex: Any, price: Any, cost: Any) -> tuple[bool, str]:
        """Type checks calculator numerical inputs."""
        try:
            s = float(setup_costs)
            m = float(monthly_opex)
            p = float(price)
            c = float(cost)
            if s < 0 or m < 0 or p < 0 or c < 0:
                return False, "Financial values cannot be negative numbers."
            return True, ""
        except (ValueError, TypeError) as exc:
            return False, f"Invalid numerical types provided to financial calculator: {exc}"

    @staticmethod
    def validate_source_url(url: str) -> bool:
        """Validates that a URL citation is safe and well-formed."""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False


class OutputGuardrail:
    """Guardrail inspecting final agent verdicts before presentation to the user."""

    @staticmethod
    def validate_verdict(score: float, recommendation: str, justification: str) -> tuple[bool, str]:
        """Ensures score is within bounds [1.0, 10.0] and recommendation is Go/No-Go."""
        if score < 1.0 or score > 10.0:
            return False, f"Invalid verdict score: {score}. Score must be between 1.0 and 10.0."

        if recommendation not in ("Go", "No-Go"):
            return False, f"Invalid verdict recommendation '{recommendation}'. Must be 'Go' or 'No-Go'."

        if not justification or len(justification.strip()) < 10:
            return False, "Verdict justification is missing or too brief."

        return True, ""
