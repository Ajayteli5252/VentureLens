"""
Assembles the 7-agent crew and exposes a single run_validation() function
that app.py (Streamlit) calls.

Includes robust retry logic with exponential back-off so that transient
Groq errors (output_parse_failed, 429 rate-limit, 503 overloaded) do not
kill the entire pipeline.
"""

import time
import logging
import random
from crewai import Crew, Process
from agents import (
    coordinator, market_agent, competitor_agent,
    financial_agent, risk_agent, comparator_agent, verdict_agent,
)
from tasks import build_tasks

logger = logging.getLogger(__name__)

# ---- Retry configuration ----
MAX_RETRIES = 4          # total attempts = 1 original + 4 retries
BASE_DELAY = 5           # seconds before first retry
MAX_DELAY = 60           # cap on back-off delay

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
]


def _is_retryable(error: Exception) -> bool:
    """Return True if the error is transient and worth retrying."""
    msg = str(error).lower()
    return any(keyword.lower() in msg for keyword in RETRYABLE_ERRORS)


def run_validation(idea: str) -> str:
    """Run the full multi-agent validation with automatic retries.

    If the crew fails due to a transient error (parsing, rate-limit, etc.),
    the function waits with exponential back-off and retries. Non-retryable
    errors (auth failures, missing API keys) are raised immediately.
    """
    last_exception = None

    for attempt in range(1, MAX_RETRIES + 2):  # +2 because range is exclusive and attempt 1 is the original
        try:
            tasks = build_tasks(idea)

            crew = Crew(
                agents=[market_agent, competitor_agent, financial_agent,
                        risk_agent, comparator_agent, verdict_agent],
                tasks=tasks,
                process=Process.hierarchical,
                manager_agent=coordinator,
                memory=False,                  # Disabled memory (vector embedder not needed)
                verbose=True,
                max_rpm=3,                     # Throttled to 3 RPM to respect Gemini Free Tier rate limits (20 req/min limit)
                max_retry_limit=3,             # CrewAI internal per-agent retries
            )

            result = crew.kickoff(inputs={"idea": idea})
            return str(result)

        except Exception as e:
            last_exception = e
            if attempt > MAX_RETRIES or not _is_retryable(e):
                logger.error("Non-retryable error or retries exhausted: %s", e)
                raise

            # Exponential back-off with jitter
            delay = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
            jitter = random.uniform(0, delay * 0.3)
            wait = delay + jitter

            logger.warning(
                "Attempt %d/%d failed (%s). Retrying in %.1fs…",
                attempt, MAX_RETRIES + 1, type(e).__name__, wait,
            )
            print(
                f"⚠️  Attempt {attempt}/{MAX_RETRIES + 1} failed: {type(e).__name__}. "
                f"Retrying in {wait:.0f}s…"
            )
            time.sleep(wait)

    # Should not reach here, but safety net
    raise last_exception  # type: ignore[misc]


if __name__ == "__main__":
    # Quick command-line test: python crew.py
    test_idea = "Portable EV battery health and degradation prediction device"
    print(run_validation(test_idea))
