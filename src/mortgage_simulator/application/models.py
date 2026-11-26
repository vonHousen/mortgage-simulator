"""Headless request and response contracts."""

from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from mortgage_simulator.simulation.models import (
    ComparisonReport,
    InvestmentCandidate,
    InvestmentSummary,
    OverpaymentScenario,
    SimulationSummary,
)

BASELINE_NAME = "Baseline"


class ComparisonInput(BaseModel):
    """Mortgage term overrides and custom scenarios; profile supplies missing terms."""

    model_config = ConfigDict(extra="forbid")

    terms: dict[str, JsonValue] = Field(default_factory=dict)
    scenarios: tuple[OverpaymentScenario, ...]


class ScenarioOutcome(BaseModel):
    """Scenario totals and investment details without monthly mortgage rows."""

    scenario_name: str
    summary: SimulationSummary
    net_financing_cost: Decimal
    investment: InvestmentSummary | None
    investment_candidates: tuple[InvestmentCandidate, ...]


class RunReport(BaseModel):
    """Machine-readable comparison and locations of its detailed artifacts."""

    results: tuple[ScenarioOutcome, ...]
    comparison: ComparisonReport
    artifacts: dict[str, Path]
