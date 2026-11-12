"""Conversion and validation helpers for Streamlit simulation inputs."""

from datetime import date
from decimal import Decimal
from typing import Any, TypedDict

import polars as pl
import streamlit as st

from mortgage_simulator.settings import AppSettings
from mortgage_simulator.simulation.models import (
    FeeTerms,
    InsuranceCalculationMethod,
    InterestCalculationMethod,
    LumpSum,
    MortgageTerms,
    OverpaymentScenario,
    RatePeriod,
    SimulationRequest,
    SubsidyTerms,
)

PERCENT = Decimal("100")
ZERO = Decimal("0")
FIXED_OVERPAYMENT_STRATEGY = "Fixed overpayment"
CONSTANT_CASH_OUTFLOW_STRATEGY = "Constant cash outflow"
OVERPAYMENT_STRATEGIES = (FIXED_OVERPAYMENT_STRATEGY, CONSTANT_CASH_OUTFLOW_STRATEGY)
ColumnConfig = dict[str, Any]


class MortgageInputs(TypedDict):
    """Raw values collected from mortgage setup widgets."""

    first_payment_date: date
    interest_calculation_method: InterestCalculationMethod
    principal: float
    contractual_term_years: int
    horizon: int
    settle_remaining_principal_at_horizon: bool
    first_rate: float
    second_rate: float
    subsidy_enabled: bool
    second_subsidy_coefficient: float
    subsidy_coefficient: float
    subsidy_reference: float
    annual_fee: float
    insurance_rate: float
    insurance_calculation_method: InsuranceCalculationMethod
    monthly_fees: float
    insurance_end: int | None


def build_terms(inputs: MortgageInputs) -> MortgageTerms:
    """Build validated mortgage terms from raw input-widget values.

    Args:
        inputs: Raw values from the mortgage-assumptions input widgets.

    Returns:
        Validated terms shared by every simulation scenario.
    """
    return MortgageTerms(
        first_payment_date=inputs["first_payment_date"],
        interest_calculation_method=inputs["interest_calculation_method"],
        principal=_decimal(inputs["principal"]),
        contractual_term_months=inputs["contractual_term_years"] * 12,
        analysis_horizon_months=inputs["horizon"],
        settle_remaining_principal_at_horizon=inputs["settle_remaining_principal_at_horizon"],
        rate_periods=(
            RatePeriod(start_month=1, end_month=60, annual_rate=_percentage(inputs["first_rate"])),
            RatePeriod(start_month=61, end_month=120, annual_rate=_percentage(inputs["second_rate"])),
        ),
        subsidy=SubsidyTerms(
            enabled=inputs["subsidy_enabled"],
            coefficient=_percentage(inputs["subsidy_coefficient"]),
            second_coefficient=_percentage(inputs["second_subsidy_coefficient"]),
            reference_rate=_percentage(inputs["subsidy_reference"]),
        ),
        fees=FeeTerms(
            annual_fixed_fee=_decimal(inputs["annual_fee"]),
            monthly_insurance_rate=_percentage(inputs["insurance_rate"]),
            insurance_calculation_method=inputs["insurance_calculation_method"],
            monthly_fixed_fees=_decimal(inputs["monthly_fees"]),
            insurance_end_month=inputs["insurance_end"],
        ),
    )


def build_request(
    settings: AppSettings,
    terms: MortgageTerms,
    scenario_data: pl.DataFrame,
    lump_sum_data: pl.DataFrame,
) -> SimulationRequest:
    """Build a validated simulation request from edited scenario frames.

    Args:
        settings: Application-wide defaults, including the baseline scenario name.
        terms: Validated mortgage terms to use for every scenario.
        scenario_data: Edited rows for recurring overpayment scenarios.
        lump_sum_data: Edited rows for one-off overpayments.

    Returns:
        Validated request with the baseline scenario first.
    """
    lump_sums_by_scenario = _parse_lump_sums(lump_sum_data)
    scenario_rows = scenario_data.to_dicts()
    scenario_names = {_scenario_name(row["name"]) for row in scenario_rows}
    baseline_name = settings.scenarios.baseline_name
    _validate_lump_sum_scenarios(lump_sums_by_scenario, scenario_names | {baseline_name})
    scenarios = [OverpaymentScenario(name=baseline_name)]
    for row in scenario_rows:
        name = _scenario_name(row["name"])
        recurring_value = _decimal(row["recurring_value"])
        recurring_amount, cash_outflow_target = _recurring_values(row["strategy"], recurring_value)
        start_value = row["start_month"]
        scenarios.append(
            OverpaymentScenario(
                name=name,
                recurring_amount=recurring_amount,
                cash_outflow_target=cash_outflow_target,
                recurring_start_month=int(start_value) if start_value is not None else None,
                lump_sums=tuple(lump_sums_by_scenario.get(name, [])),
            )
        )
    return SimulationRequest(terms=terms, scenarios=tuple(scenarios))


def scenario_column_config(horizon: int) -> ColumnConfig:
    """Build recurring-payment editor column configuration.

    Args:
        horizon: Maximum valid payment month.

    Returns:
        Streamlit column configuration keyed by frame column.
    """
    return {
        "name": st.column_config.TextColumn("Scenario name", required=True),
        "strategy": st.column_config.SelectboxColumn("Strategy", options=OVERPAYMENT_STRATEGIES, required=True),
        "recurring_value": st.column_config.NumberColumn(
            "Monthly amount or target (PLN)", min_value=0.0, step=100.0, format="%.2f PLN", required=True
        ),
        "start_month": st.column_config.NumberColumn(
            "Starting month", min_value=1, max_value=horizon, step=1, format="%d"
        ),
    }


def lump_sum_column_config(horizon: int) -> ColumnConfig:
    """Build lump-sum editor column configuration.

    Args:
        horizon: Maximum valid payment month.

    Returns:
        Streamlit column configuration keyed by frame column.
    """
    return {
        "scenario": st.column_config.TextColumn("Scenario", required=True),
        "month": st.column_config.NumberColumn(
            "Payment month", min_value=1, max_value=horizon, step=1, format="%d", required=True
        ),
        "amount": st.column_config.NumberColumn(
            "Amount (PLN)", min_value=0.01, step=1000.0, format="%.2f PLN", required=True
        ),
    }


def _percentage(value: int | float | object) -> Decimal:
    return _decimal(value) / PERCENT


def _decimal(value: int | float | object) -> Decimal:
    return Decimal(str(value))


def _scenario_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("scenario name must be text")
    return value.strip()


def _recurring_values(strategy: object, value: Decimal) -> tuple[Decimal, Decimal]:
    if strategy == FIXED_OVERPAYMENT_STRATEGY:
        return value, ZERO
    if strategy == CONSTANT_CASH_OUTFLOW_STRATEGY:
        return ZERO, value
    raise ValueError(f"unsupported overpayment strategy: {strategy}")


def _parse_lump_sums(frame: pl.DataFrame) -> dict[str, list[LumpSum]]:
    lump_sums: dict[str, list[LumpSum]] = {}
    for row in frame.to_dicts():
        scenario_name = _scenario_name(row["scenario"])
        lump_sums.setdefault(scenario_name, []).append(LumpSum(month=int(row["month"]), amount=_decimal(row["amount"])))
    return lump_sums


def _validate_lump_sum_scenarios(lump_sums: dict[str, list[LumpSum]], scenario_names: set[str]) -> None:
    unknown_names = set(lump_sums) - scenario_names
    if unknown_names:
        formatted_names = ", ".join(sorted(unknown_names))
        raise ValueError(f"lump sums refer to unknown scenarios: {formatted_names}")
