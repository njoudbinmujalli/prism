"""
PRISM — output schemas for the five-agent evaluation pipeline.

The prompts request the contract; this module ENFORCES it. Anything that fails here
should be routed into the repair loop (see PRISM_agent_prompts.md §8) rather than
returned to the user.

Pydantic v2.
"""

from __future__ import annotations

import json
import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

# --------------------------------------------------------------------------------------
# Shared vocabulary
# --------------------------------------------------------------------------------------

Band = Literal["very_weak", "weak", "moderate", "strong", "exceptional"]
AgentId = Literal["novelty", "feasibility", "impact", "risk_ethics"]

BAND_RANGES: dict[str, range] = {
    "very_weak": range(1, 3),     # 1-2
    "weak": range(3, 5),          # 3-4
    "moderate": range(5, 7),      # 5-6
    "strong": range(7, 9),        # 7-8
    "exceptional": range(9, 11),  # 9-10
}

Score = Annotated[int, Field(ge=1, le=10)]

# Hedging is rejected, not merely discouraged. This is the part that actually holds up
# on a free-tier model.
BANNED_PHRASES: tuple[str, ...] = (
    "it depends", "may or may not", "could potentially", "somewhat", "relatively",
    "arguably", "in some cases", "hard to say", "further research is needed",
    "generally speaking", "to some extent", "possibly", "i think", "as an ai",
    "there are pros and cons", "this is subjective", "more information is needed",
    "n/a", "tbd", "unknown", "unclear",
)

# Generic beneficiaries the Impact agent is forbidden from naming.
GENERIC_BENEFICIARIES: tuple[str, ...] = (
    "users", "people", "businesses", "society", "everyone", "customers",
    "individuals", "organizations", "organisations", "the public",
)

# Mitigations that say nothing.
EMPTY_MITIGATIONS: tuple[str, ...] = (
    "be careful", "plan carefully", "start early", "monitor closely",
    "follow best practices", "use good judgement", "be mindful", "take care",
)


def _reject_hedging(v: str) -> str:
    low = v.strip().lower()
    for phrase in BANNED_PHRASES:
        if phrase in low:
            raise ValueError(
                f"banned hedging phrase {phrase!r} present; rewrite as one direct "
                f"declarative sentence with no qualifiers"
            )
    if not low:
        raise ValueError("field is empty; empty strings are not permitted")
    return v.strip()


class StrictBase(BaseModel):
    """Forbids extra keys and applies the anti-hedging rule to every string field."""

    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    @field_validator("*", mode="after")
    @classmethod
    def _no_hedging(cls, v):
        if isinstance(v, str):
            return _reject_hedging(v)
        return v


class ScoredAgent(StrictBase):
    score: Score
    band: Band

    @model_validator(mode="after")
    def _band_matches_score(self):
        if self.score not in BAND_RANGES[self.band]:
            expected = next(b for b, r in BAND_RANGES.items() if self.score in r)
            raise ValueError(
                f"score {self.score} does not sit in band {self.band!r}; keep the "
                f"score and change the band to {expected!r}"
            )
        return self


# --------------------------------------------------------------------------------------
# Novelty
# --------------------------------------------------------------------------------------

class ExistingSolution(StrictBase):
    name: str = Field(max_length=60)
    what_it_does: str = Field(max_length=160)
    overlap: Literal["high", "moderate", "low"]
    source: str  # a real URL, or the literal "model_knowledge"


class NoveltyVerdict(ScoredAgent):
    agent: Literal["novelty"]
    verdict_line: str = Field(max_length=140)
    novelty_claim_status: Literal[
        "novel_approach", "novel_combination", "novel_application", "derivative"
    ]
    closest_existing: list[ExistingSolution] = Field(min_length=3, max_length=3)
    genuine_differentiators: list[Annotated[str, Field(max_length=120)]] = Field(
        max_length=3
    )
    weakest_novelty_claim: str = Field(max_length=200)
    evidence_basis: Literal["search_verified", "model_knowledge_only"]

    @model_validator(mode="after")
    def _search_claims_need_urls(self):
        # Blocks the worst failure in the pipeline: a fabricated "this already exists".
        if self.evidence_basis == "search_verified":
            if not any(s.source.startswith("http") for s in self.closest_existing):
                raise ValueError(
                    "evidence_basis is 'search_verified' but no source contains a URL; "
                    "set evidence_basis to 'model_knowledge_only' or supply real URLs"
                )
        for s in self.closest_existing:
            if not (s.source.startswith("http") or s.source == "model_knowledge"):
                raise ValueError(
                    f"source must be a URL or the literal 'model_knowledge', got "
                    f"{s.source!r}"
                )
        return self


# --------------------------------------------------------------------------------------
# Feasibility
# --------------------------------------------------------------------------------------

class CriticalPathStep(StrictBase):
    step: str = Field(max_length=140)
    estimated_hours: int = Field(ge=1, le=200)
    risk: Literal["low", "medium", "high"]


class Blocker(StrictBase):
    blocker: str = Field(max_length=160)
    severity: Literal["low", "medium", "high"]
    mitigation: str = Field(max_length=160)


    @field_validator("mitigation", mode="after")
    @classmethod
    def _mitigation_is_concrete(cls, v: str) -> str:
        low = v.lower()
        for empty in EMPTY_MITIGATIONS:
            if empty in low:
                raise ValueError(
                    f"mitigation {v!r} is generic advice; name a specific tool, "
                    f"library, or scope cut"
                )
        return v


class FeasibilityVerdict(ScoredAgent):
    agent: Literal["feasibility"]
    verdict_line: str = Field(max_length=140)
    buildable_in_window: Literal["yes_full_scope", "yes_reduced_scope", "no"]
    critical_path: list[CriticalPathStep] = Field(min_length=3, max_length=3)
    blockers: list[Blocker] = Field(min_length=1, max_length=3)
    descope_recommendation: str = Field(max_length=200)


# --------------------------------------------------------------------------------------
# Impact
# --------------------------------------------------------------------------------------

class Beneficiary(StrictBase):
    who: str = Field(max_length=100)
    why_they_care: str = Field(max_length=180)

    @field_validator("who", mode="after")
    @classmethod
    def _must_be_specific(cls, v: str) -> str:
        if v.strip().lower() in GENERIC_BENEFICIARIES:
            raise ValueError(
                f"beneficiary {v!r} is too generic; name a specific group, e.g. "
                f"'night-shift nurses in public hospitals'"
            )
        return v


class ImpactVerdict(ScoredAgent):
    agent: Literal["impact"]
    verdict_line: str = Field(max_length=140)
    problem_definition: Literal["well_defined", "partially_defined", "vague"]
    primary_beneficiary: Beneficiary
    status_quo_alternative: str = Field(max_length=180)
    value_type: Literal[
        "saves_time", "saves_money", "improves_quality",
        "enables_new_capability", "reduces_risk", "entertainment_only",
    ]
    impact_ceiling: Literal["niche", "institutional", "national", "global"]
    weakest_impact_claim: str = Field(max_length=160)


# --------------------------------------------------------------------------------------
# Risk / Ethics
# --------------------------------------------------------------------------------------

RISK_CATEGORY_ORDER: tuple[str, ...] = (
    "data_privacy", "bias_fairness", "safety_misuse", "compliance_legal",
)


class RiskFinding(StrictBase):
    category: Literal[
        "data_privacy", "bias_fairness", "safety_misuse", "compliance_legal"
    ]
    present: bool
    finding: str = Field(max_length=180)
    severity: Literal["none", "low", "medium", "high", "critical"]
    required_mitigation: str = Field(max_length=180)

    @model_validator(mode="after")
    def _serious_findings_need_real_mitigations(self):
        if self.severity in ("medium", "high", "critical"):
            low = self.required_mitigation.lower()
            if low == "none required":
                raise ValueError(
                    f"severity {self.severity!r} requires a specific mitigation"
                )
            for empty in EMPTY_MITIGATIONS:
                if empty in low:
                    raise ValueError(
                        f"mitigation {self.required_mitigation!r} is generic advice; "
                        f"name a specific technique or control"
                    )
        if self.severity == "none" and self.present:
            raise ValueError("severity 'none' is inconsistent with present=true")
        return self


class RiskEthicsVerdict(ScoredAgent):
    agent: Literal["risk_ethics"]
    verdict_line: str = Field(max_length=140)
    findings: list[RiskFinding] = Field(min_length=4, max_length=4)
    blocking_issue: bool
    blocking_reason: str = Field(max_length=140)

    @model_validator(mode="after")
    def _consistency(self):
        got = tuple(f.category for f in self.findings)
        if got != RISK_CATEGORY_ORDER:
            raise ValueError(
                f"findings must cover all four categories in the order "
                f"{RISK_CATEGORY_ORDER}, got {got}"
            )
        has_critical = any(f.severity == "critical" for f in self.findings)
        if has_critical and not self.blocking_issue:
            raise ValueError("a critical finding requires blocking_issue=true")
        if self.blocking_issue and self.blocking_reason.lower() == "none":
            raise ValueError("blocking_issue=true requires a blocking_reason")
        if not self.blocking_issue and self.blocking_reason.lower() != "none":
            raise ValueError("blocking_issue=false requires blocking_reason='none'")
        # Catches a silently inverted score direction, which produces well-formed
        # output and a wrong final verdict.
        if has_critical and self.score >= 7:
            raise ValueError(
                "a critical risk cannot score 7 or above; remember 10 = LOW risk"
            )
        return self


# --------------------------------------------------------------------------------------
# Synthesis
# --------------------------------------------------------------------------------------

class Tension(StrictBase):
    between: list[AgentId] = Field(min_length=2, max_length=2)
    description: str = Field(max_length=180)
    resolution_type: Literal[
        "descope", "reframe_problem", "add_mitigation", "accept_tradeoff", "pivot"
    ]
    recommended_action: str = Field(max_length=200)

    @model_validator(mode="after")
    def _two_distinct_agents(self):
        if self.between[0] == self.between[1]:
            raise ValueError("a tension must name two DIFFERENT judges")
        return self


class Action(StrictBase):
    rank: int = Field(ge=1, le=3)
    action: str = Field(max_length=140)
    owner_dimension: AgentId
    expected_effect: str = Field(max_length=100)


class SynthesisVerdict(StrictBase):
    agent: Literal["synthesis"]
    overall_score: Score
    decision: Literal[
        "advance_as_is", "advance_with_changes", "major_rework", "do_not_pursue"
    ]
    one_line_verdict: str = Field(max_length=160)
    tensions: list[Tension] = Field(min_length=1, max_length=3)
    agreements: list[Annotated[str, Field(max_length=140)]] = Field(
        min_length=1, max_length=2
    )
    top_3_actions: list[Action] = Field(min_length=3, max_length=3)
    dissent_note: str = Field(max_length=180)
    confidence: Literal["high", "medium", "low"]

    @model_validator(mode="after")
    def _ranks_are_1_2_3(self):
        if sorted(a.rank for a in self.top_3_actions) != [1, 2, 3]:
            raise ValueError("top_3_actions must have ranks 1, 2, and 3 exactly once")
        return self


# --------------------------------------------------------------------------------------
# Parsing + repair support
# --------------------------------------------------------------------------------------

SCHEMAS: dict[str, type[BaseModel]] = {
    "novelty": NoveltyVerdict,
    "feasibility": FeasibilityVerdict,
    "impact": ImpactVerdict,
    "risk_ethics": RiskEthicsVerdict,
    "synthesis": SynthesisVerdict,
}

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def extract_json(raw: str) -> dict:
    """Most 'invalid JSON' from a cheap model is valid JSON wrapped in prose.

    Try the free recoveries before spending a repair call.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    stripped = _FENCE.sub("", raw).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # First balanced {...} block, by brace counting.
    start = stripped.find("{")
    if start != -1:
        depth, in_str, esc = 0, False, False
        for i, ch in enumerate(stripped[start:], start):
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
            elif ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(stripped[start:i + 1])
    raise ValueError("no JSON object found in response")


def format_errors(exc: ValidationError) -> str:
    """Render validation errors in the form the repair prompt expects."""
    lines = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        lines.append(f"- {loc}: {err['msg']}")
    return "\n".join(lines)


def skeleton(agent: str) -> str:
    """Empty schema skeleton for repair attempt 2.

    Weak models recover format far better from a skeleton to fill in than from a
    description of what went wrong.
    """
    model = SCHEMAS[agent]
    return json.dumps(
        {name: "" for name in model.model_fields}, indent=2, ensure_ascii=False
    )

