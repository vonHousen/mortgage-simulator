"""Per-user Streamlit state for the multipage application."""

from typing import cast

import polars as pl
import streamlit as st

from mortgage_simulator.app.simulation_inputs import CONSTANT_CASH_OUTFLOW_STRATEGY, FIXED_OVERPAYMENT_STRATEGY
from mortgage_simulator.settings import AppSettings
from mortgage_simulator.simulation.models import MortgageTerms, OverpaymentScenario, SimulationResult

TERMS_KEY = "mortgage_terms"
SCENARIOS_KEY = "scenario_data"
LUMP_SUMS_KEY = "lump_sum_data"
RESULTS_KEY = "simulation_results"
FOCUS_ON_TYPICAL_PAYMENTS_KEY = "focus_on_typical_payments"
SCENARIO_SCHEMA = {
    "name": pl.String,
    "strategy": pl.String,
    "recurring_value": pl.Float64,
    "start_month": pl.Int64,
}
LUMP_SUM_SCHEMA = {"scenario": pl.String, "month": pl.Int64, "amount": pl.Float64}


def initialize_state(
    settings: AppSettings,
    terms: MortgageTerms,
    scenario_defaults: tuple[OverpaymentScenario, ...] = (),
) -> None:
    """Initialize per-user values once without overwriting edits.

    Args:
        settings: Application defaults used for a new session.
        terms: Complete domain terms used for a new session.
        scenario_defaults: Overpayment scenarios used to seed new-session editors.
    """
    if TERMS_KEY not in st.session_state:
        st.session_state[TERMS_KEY] = terms
    if SCENARIOS_KEY not in st.session_state:
        st.session_state[SCENARIOS_KEY] = _scenario_frame(scenario_defaults)
    if LUMP_SUMS_KEY not in st.session_state:
        st.session_state[LUMP_SUMS_KEY] = _lump_sum_frame(scenario_defaults)
    if RESULTS_KEY not in st.session_state:
        st.session_state[RESULTS_KEY] = None
    if FOCUS_ON_TYPICAL_PAYMENTS_KEY not in st.session_state:
        st.session_state[FOCUS_ON_TYPICAL_PAYMENTS_KEY] = settings.charts.focus_on_typical_payments


def get_terms() -> MortgageTerms:
    """Return the current validated mortgage terms."""
    return cast(MortgageTerms, st.session_state[TERMS_KEY])


def get_scenario_data() -> pl.DataFrame:
    """Return the current recurring-payment editor rows."""
    return cast(pl.DataFrame, st.session_state[SCENARIOS_KEY])


def get_lump_sum_data() -> pl.DataFrame:
    """Return the current lump-sum editor rows."""
    return cast(pl.DataFrame, st.session_state[LUMP_SUMS_KEY])


def get_results() -> tuple[SimulationResult, ...] | None:
    """Return the most recent successful results, if any."""
    return cast(tuple[SimulationResult, ...] | None, st.session_state[RESULTS_KEY])


def store_results(results: tuple[SimulationResult, ...]) -> None:
    """Atomically replace the most recent successful results.

    Args:
        results: Complete validated scenario results.
    """
    st.session_state[RESULTS_KEY] = results


def clear_results() -> None:
    """Discard simulation results calculated from previous mortgage terms."""
    st.session_state[RESULTS_KEY] = None


def _scenario_frame(scenarios: tuple[OverpaymentScenario, ...]) -> pl.DataFrame:
    rows: list[dict[str, str | float | int | None]] = []
    for scenario in scenarios:
        uses_cash_outflow_target = scenario.cash_outflow_target > 0
        rows.append(
            {
                "name": scenario.name,
                "strategy": (
                    CONSTANT_CASH_OUTFLOW_STRATEGY if uses_cash_outflow_target else FIXED_OVERPAYMENT_STRATEGY
                ),
                "recurring_value": float(
                    scenario.cash_outflow_target if uses_cash_outflow_target else scenario.recurring_amount
                ),
                "start_month": scenario.recurring_start_month,
            }
        )
    return pl.DataFrame(rows, schema=SCENARIO_SCHEMA)


def _lump_sum_frame(scenarios: tuple[OverpaymentScenario, ...]) -> pl.DataFrame:
    rows = [
        {"scenario": scenario.name, "month": lump_sum.month, "amount": float(lump_sum.amount)}
        for scenario in scenarios
        for lump_sum in scenario.lump_sums
    ]
    return pl.DataFrame(rows, schema=LUMP_SUM_SCHEMA)
