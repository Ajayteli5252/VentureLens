"""
End-to-End Performance Evaluation, Cost Modeling, and Runtime Estimates for VentureLens.

Implements Requirement 10:
Perform end-to-end performance evaluation, cost and running time estimates.
"""

import time
from typing import Any
from pydantic import BaseModel, Field

# Pricing per 1M tokens (USD)
MODEL_PRICING = {
    "openai/@cf/meta/llama-3.3-70b-instruct-fp8-fast": {
        "input_per_m": 0.35,
        "output_per_m": 0.40,
        "name": "Llama 3.3 70B (Cloudflare/OmniKey)",
    },
    "gemini-2.5-flash": {
        "input_per_m": 0.075,
        "output_per_m": 0.30,
        "name": "Google Gemini 2.5 Flash",
    },
    "gpt-4o-mini": {
        "input_per_m": 0.15,
        "output_per_m": 0.60,
        "name": "OpenAI GPT-4o Mini",
    },
    "default": {
        "input_per_m": 0.30,
        "output_per_m": 0.45,
        "name": "Default Inference Tier",
    }
}

USD_TO_INR_RATE = 86.50


class CostEstimate(BaseModel):
    estimated_input_tokens: int
    estimated_output_tokens: int
    total_tokens: int
    cost_usd: float
    cost_inr: float
    model_name: str


class StageTiming(BaseModel):
    stage_name: str
    duration_seconds: float
    percentage_of_total: float


class PipelinePerformanceMetrics(BaseModel):
    session_id: str
    total_duration_seconds: float
    stage_timings: list[StageTiming]
    cost: CostEstimate
    agents_executed: int
    tools_executed: int

    def to_markdown(self) -> str:
        timings_table = "\n".join(
            f"| {s.stage_name} | `{s.duration_seconds:.2f}s` | `{s.percentage_of_total:.1f}%` |"
            for s in self.stage_timings
        )

        md = f"""# ⏱️ VentureLens Performance & Cost Evaluation

### 📊 Runtime Breakdown
| Pipeline Stage | Duration | % of Total Time |
| :--- | :---: | :---: |
{timings_table}
| **Total Pipeline Duration** | **`{self.total_duration_seconds:.2f}s`** | **100.0%** |

---

### 💰 Cost & Token Consumption Model
| Metric | Value |
| :--- | :--- |
| **Model Inferred** | `{self.cost.model_name}` |
| **Estimated Input Tokens** | `{self.cost.estimated_input_tokens:,}` tokens |
| **Estimated Output Tokens** | `{self.cost.estimated_output_tokens:,}` tokens |
| **Total Token Consumption** | **`{self.cost.total_tokens:,}` tokens** |
| **Total Cost (USD)** | **`${self.cost.cost_usd:.4f}`** |
| **Total Cost (INR)** | **`₹{self.cost.cost_inr:.2f}`** |
| **Agents Executed** | `{self.agents_executed}` agents |
| **MCP Tools Invocations** | `{self.tools_executed}` calls |
"""
        return md


def estimate_pipeline_cost(
    prompt_chars: int,
    output_chars: int,
    model_key: str = "openai/@cf/meta/llama-3.3-70b-instruct-fp8-fast",
) -> CostEstimate:
    """Estimates token counts and costs based on character lengths (~4 chars per token)."""
    est_input_tokens = max(1, prompt_chars // 4)
    est_output_tokens = max(1, output_chars // 4)
    total_tokens = est_input_tokens + est_output_tokens

    pricing = MODEL_PRICING.get(model_key, MODEL_PRICING["default"])
    cost_input = (est_input_tokens / 1_000_000) * pricing["input_per_m"]
    cost_output = (est_output_tokens / 1_000_000) * pricing["output_per_m"]
    total_usd = cost_input + cost_output
    total_inr = total_usd * USD_TO_INR_RATE

    return CostEstimate(
        estimated_input_tokens=est_input_tokens,
        estimated_output_tokens=est_output_tokens,
        total_tokens=total_tokens,
        cost_usd=round(total_usd, 5),
        cost_inr=round(total_inr, 3),
        model_name=pricing["name"],
    )


def compute_performance_metrics(
    session_id: str,
    stage_durations: dict[str, float],
    total_prompt_chars: int,
    total_output_chars: int,
    model_key: str = "openai/@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    agents_count: int = 7,
    tools_count: int = 4,
) -> PipelinePerformanceMetrics:
    """Computes runtime percentages, token costs, and structured performance metrics."""
    total_duration = max(sum(stage_durations.values()), 0.001)

    timings = [
        StageTiming(
            stage_name=k,
            duration_seconds=round(v, 2),
            percentage_of_total=round((v / total_duration) * 100.0, 1),
        )
        for k, v in stage_durations.items()
    ]

    cost = estimate_pipeline_cost(
        prompt_chars=total_prompt_chars,
        output_chars=total_output_chars,
        model_key=model_key,
    )

    return PipelinePerformanceMetrics(
        session_id=session_id,
        total_duration_seconds=round(total_duration, 2),
        stage_timings=timings,
        cost=cost,
        agents_executed=agents_count,
        tools_executed=tools_count,
    )


# Benchmark Test Idea Definitions
BENCHMARK_IDEAS = [
    {
        "id": "sound_b2b_saas",
        "name": "B2B Healthcare Compliance SaaS",
        "description": "Automated HIPAA & state compliance audit SaaS for independent dental and medical clinics charging $199/month per clinic.",
        "expected_verdict": "Go",
        "expected_min_score": 6.5,
    },
    {
        "id": "fatal_flaw_hyperlocal",
        "name": "Zero-Fee 10-Minute Delivery",
        "description": "10-minute grocery delivery in all Indian cities with zero delivery fees, zero merchant commission, ₹2 lakh initial budget, and 30% discounts funded by company.",
        "expected_verdict": "No-Go",
        "expected_max_score": 4.0,
    },
    {
        "id": "capital_intensive_frontier",
        "name": "Urban Drone Battery Swapping",
        "description": "Automated drone battery swap kiosks on commercial rooftops for delivery drones.",
        "expected_verdict": "Go",
        "expected_min_score": 5.5,
    }
]

