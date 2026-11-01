"""
Pydantic Schemas for VentureLens: Multi-Agent Startup Idea Validator.

Implements Requirement 3:
Structured Output using Pydantic - final output must be generated in a structured form
(Markdown, Table, or JSON).
"""

from typing import Literal, Any
import json
from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    market_demand: float = Field(..., ge=1.0, le=10.0, description="Score 1-10 on market demand and customer pain")
    competition_moat: float = Field(..., ge=1.0, le=10.0, description="Score 1-10 on competitive moat and differentiation")
    unit_economics: float = Field(..., ge=1.0, le=10.0, description="Score 1-10 on unit economics and margin feasibility")
    risk_profile: float = Field(..., ge=1.0, le=10.0, description="Score 1-10 on risk management (higher means lower risk)")


class SourceCitation(BaseModel):
    title: str = Field(..., description="Title or name of source")
    url: str = Field(..., description="Verified URL citation")
    domain: str = Field(default="", description="Domain name")
    supports: str = Field(default="", description="Specific finding supported by this source")


class VerdictReport(BaseModel):
    """Structured Pydantic model for the final Investor Verdict Agent output."""
    score: float = Field(..., ge=1.0, le=10.0, description="Final overall score out of 10")
    recommendation: Literal["Go", "No-Go"] = Field(..., description="Go (Validated) or No-Go (Not Validated)")
    justification: str = Field(..., min_length=10, description="Concise, evidence-based justification lines")
    score_breakdown: ScoreBreakdown = Field(..., description="Categorical score breakdown out of 10")
    key_strengths: list[str] = Field(default_factory=list, description="Top validated strengths of the idea")
    fatal_blockers: list[str] = Field(default_factory=list, description="Fatal business model blockers identified, if any")
    manageable_risks: list[str] = Field(default_factory=list, description="Manageable startup risks")
    sources: list[SourceCitation] = Field(default_factory=list, description="Citations supporting the verdict")

    def to_markdown(self) -> str:
        """Render verdict in clean GitHub-flavored Markdown."""
        strengths = "\n".join(f"- {s}" for s in self.key_strengths) if self.key_strengths else "- None stated"
        blockers = "\n".join(f"- ❌ {b}" for b in self.fatal_blockers) if self.fatal_blockers else "- None detected"
        risks = "\n".join(f"- ⚠️ {r}" for r in self.manageable_risks) if self.manageable_risks else "- None detected"

        md = f"""# 🚀 VentureLens Investment Verdict

**Overall Score:** `{self.score:.1f} / 10`  
**Recommendation:** **{self.recommendation}**

---

### 📝 Executive Justification
{self.justification}

---

### 📊 Score Breakdown
| Dimension | Score (out of 10) | Assessment |
| :--- | :---: | :--- |
| **Market Demand** | `{self.score_breakdown.market_demand:.1f}` | {'High pain point' if self.score_breakdown.market_demand >= 7 else 'Moderate/Uncertain'} |
| **Competitive Moat** | `{self.score_breakdown.competition_moat:.1f}` | {'Strong moat' if self.score_breakdown.competition_moat >= 7 else 'Crowded / Low barrier'} |
| **Unit Economics** | `{self.score_breakdown.unit_economics:.1f}` | {'Profitable per unit' if self.score_breakdown.unit_economics >= 6 else 'Negative / Fragile'} |
| **Risk Profile** | `{self.score_breakdown.risk_profile:.1f}` | {'Manageable risks' if self.score_breakdown.risk_profile >= 6 else 'High legal/tech exposure'} |

---

### 💡 Key Strengths
{strengths}

### 🛑 Fatal Business Blockers
{blockers}

### ⚠️ Manageable Risks
{risks}
"""
        if self.sources:
            md += "\n---\n### 🔗 Key Citations\n"
            for src in self.sources:
                md += f"- [{src.title}]({src.url}) - {src.supports}\n"
        return md

    def to_table(self) -> str:
        """Render verdict summary in a compact Markdown Table."""
        blocker_count = len(self.fatal_blockers)
        strength_count = len(self.key_strengths)
        table = f"""| Metric | Value |
| :--- | :--- |
| **Overall Viability Score** | `{self.score:.1f} / 10` |
| **Recommendation** | **{self.recommendation}** |
| **Market Demand Score** | `{self.score_breakdown.market_demand:.1f} / 10` |
| **Competitive Moat Score** | `{self.score_breakdown.competition_moat:.1f} / 10` |
| **Unit Economics Score** | `{self.score_breakdown.unit_economics:.1f} / 10` |
| **Risk Profile Score** | `{self.score_breakdown.risk_profile:.1f} / 10` |
| **Fatal Blockers Found** | `{blocker_count}` |
| **Validated Strengths** | `{strength_count}` |
"""
        return table

    def to_json(self, indent: int = 2) -> str:
        """Render structured JSON representation."""
        return self.model_dump_json(indent=indent)

