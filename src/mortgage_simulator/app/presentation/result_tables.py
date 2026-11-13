"""Shared Streamlit table projections and formatting."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import polars as pl
import streamlit as st

from mortgage_simulator.app.presentation.result_metrics import (
    MORTGAGE_COST_HELP,
    MORTGAGE_PAYMENTS_HELP,
    payoff_label,
    percentage,
    percentage_or_na,
    pln,
)
from mortgage_simulator.simulation.models import ComparisonReport, ScenarioComparison

PLN_TABLE_FORMAT = "%,.2f PLN"
PERCENT_TABLE_FORMAT = "%.2f%%"
_SCHEDULE_PREFIX_COLUMNS = [
    "month",
    "payment_date",
    "opening_balance",
    "scheduled_principal",
]
_SPLIT_OVERPAYMENT_COLUMNS = [
    "recurring_overpayment",
    "lump_sum",
    "horizon_settlement",
]
_SPLIT_FEE_COLUMNS = [
    "monthly_insurance",
    "monthly_fixed_fees",
    "annual_fixed_fee",
]
_SCHEDULE_SUFFIX_COLUMNS = [
    "interest",
    "subsidy",
    "cash_outflow_without_fees",
    "cash_outflow",
    "closing_balance",
]


def schedule_columns(
    *,
    split_fees: bool,
    split_overpayments: bool,
    include_subsidy: bool = True,
) -> list[str]:
    """Build an ordered schedule-table projection for the selected component toggles.

    Args:
        split_fees: Whether to display individual monthly and annual fee columns.
        split_overpayments: Whether to display individual recurring, lump-sum, and settlement columns.
        include_subsidy: Whether to display the monthly subsidy column.

    Returns:
        Ordered names of schedule-frame columns for a monthly schedule table.
    """
    overpayment_columns = _SPLIT_OVERPAYMENT_COLUMNS if split_overpayments else ["overpayments"]
    fee_columns = _SPLIT_FEE_COLUMNS if split_fees else ["fees"]
    subsidy_columns = ["subsidy"] if include_subsidy else []
    return [
        *_SCHEDULE_PREFIX_COLUMNS,
        *overpayment_columns,
        "interest",
        *subsidy_columns,
        *fee_columns,
        *_SCHEDULE_SUFFIX_COLUMNS[2:],
    ]


SCHEDULE_COLUMNS = schedule_columns(split_fees=False, split_overpayments=True)
SCHEDULE_COLUMN_CONFIG: dict[str, Any] = {
    "month": st.column_config.NumberColumn("Month", format="%d"),
    "payment_date": st.column_config.DateColumn("Payment date", format="DD/MM/YYYY"),
    "opening_balance": st.column_config.NumberColumn("Opening balance", format=PLN_TABLE_FORMAT),
    "scheduled_principal": st.column_config.NumberColumn("Principal", format=PLN_TABLE_FORMAT),
    "overpayments": st.column_config.NumberColumn("Overpayments", format=PLN_TABLE_FORMAT),
    "recurring_overpayment": st.column_config.NumberColumn("Recur. overpayment", format=PLN_TABLE_FORMAT),
    "lump_sum": st.column_config.NumberColumn("Lump sum", format=PLN_TABLE_FORMAT),
    "horizon_settlement": st.column_config.NumberColumn("Horizon settlement", format=PLN_TABLE_FORMAT),
    "interest": st.column_config.NumberColumn("Gross mortgage interest", format=PLN_TABLE_FORMAT),
    "subsidy": st.column_config.NumberColumn("Subsidy", format=PLN_TABLE_FORMAT),
    "monthly_insurance": st.column_config.NumberColumn("Monthly insurance", format=PLN_TABLE_FORMAT),
    "monthly_fixed_fees": st.column_config.NumberColumn("Monthly fixed fees", format=PLN_TABLE_FORMAT),
    "annual_fixed_fee": st.column_config.NumberColumn("Annual fixed fee", format=PLN_TABLE_FORMAT),
    "fees": st.column_config.NumberColumn("Fees", format=PLN_TABLE_FORMAT),
    "cash_outflow_without_fees": st.column_config.NumberColumn("Outflow excl. fees", format=PLN_TABLE_FORMAT),
    "cash_outflow": st.column_config.NumberColumn("Outflow", format=PLN_TABLE_FORMAT),
    "closing_balance": st.column_config.NumberColumn("Closing balance", format=PLN_TABLE_FORMAT),
}
COMPARISON_COLUMN_CONFIG: dict[str, Any] = {
    "scenario": st.column_config.TextColumn("Scenario"),
    "total_principal": st.column_config.NumberColumn("Principal repaid", format=PLN_TABLE_FORMAT),
    "principal_repaid_before_horizon_settlement": st.column_config.NumberColumn(
        "Principal before settlement", format=PLN_TABLE_FORMAT
    ),
    "horizon_settlement": st.column_config.NumberColumn("Horizon settlement", format=PLN_TABLE_FORMAT),
    "total_interest": st.column_config.NumberColumn("Gross mortgage interest", format=PLN_TABLE_FORMAT),
    "total_subsidy": st.column_config.NumberColumn("Subsidy received", format=PLN_TABLE_FORMAT),
    "total_fees": st.column_config.NumberColumn("Fees paid", format=PLN_TABLE_FORMAT),
    "total_cash_outflow": st.column_config.NumberColumn(
        "Total mortgage payments", format=PLN_TABLE_FORMAT, help=MORTGAGE_PAYMENTS_HELP
    ),
    "total_mortgage_cost": st.column_config.NumberColumn(
        "Total mortgage cost", format=PLN_TABLE_FORMAT, help=MORTGAGE_COST_HELP
    ),
    "mortgage_cost_to_original_principal": st.column_config.NumberColumn(
        "Cost / original principal", format=PERCENT_TABLE_FORMAT
    ),
    "mortgage_cost_to_principal_repaid": st.column_config.NumberColumn(
        "Cost / principal repaid", format=PERCENT_TABLE_FORMAT
    ),
    "net_average_annual_interest_rate": st.column_config.NumberColumn(
        "Net average annual interest rate", format=PERCENT_TABLE_FORMAT
    ),
    "ending_balance": st.column_config.NumberColumn("Ending balance", format=PLN_TABLE_FORMAT),
    "payoff_month": st.column_config.NumberColumn("Payoff month", format="%d"),
    "cash_outflow_delta": st.column_config.NumberColumn("Mortgage payments difference", format=PLN_TABLE_FORMAT),
    "interest_delta": st.column_config.NumberColumn("Interest difference", format=PLN_TABLE_FORMAT),
    "ending_balance_delta": st.column_config.NumberColumn("Ending balance difference", format=PLN_TABLE_FORMAT),
    "mortgage_cost_delta": st.column_config.NumberColumn("Total mortgage cost difference", format=PLN_TABLE_FORMAT),
    "horizon_settlement_delta": st.column_config.NumberColumn("Horizon settlement difference", format=PLN_TABLE_FORMAT),
    "subsidy_delta": st.column_config.NumberColumn("Subsidy difference", format=PLN_TABLE_FORMAT),
    "net_average_annual_interest_rate_percentage_point_delta": st.column_config.NumberColumn(
        "Net average annual interest rate difference", format="%.2f p.p."
    ),
}


def comparison_table_frame(
    report: ComparisonReport,
    *,
    show_ending_balance: bool,
    include_subsidy: bool = True,
) -> pl.DataFrame:
    """Build the transposed, formatted scenario comparison table.

    Args:
        report: Ordered Baseline-relative scenario comparison.
        show_ending_balance: Whether ending-balance metrics should be included.
        include_subsidy: Whether subsidy-specific metrics should be included.

    Returns:
        Metrics as rows and scenario names as columns.
    """
    metrics = [
        metric
        for metric in _COMPARISON_METRICS
        if (show_ending_balance or not metric.ending_balance_metric) and (include_subsidy or not metric.subsidy_metric)
    ]
    rows = [
        {
            "Metric": _comparison_metric_label(metric.label, include_subsidy),
            **{scenario.scenario_name: metric.format_value(scenario) for scenario in report.scenarios},
        }
        for metric in metrics
    ]
    return pl.DataFrame(rows)


@dataclass(frozen=True, slots=True)
class _ComparisonMetric:
    """Define one formatted row in the scenario comparison table."""

    label: str
    format_value: Callable[[ScenarioComparison], str]
    ending_balance_metric: bool = False
    subsidy_metric: bool = False


def _percentage_points(value: Decimal) -> str:
    """Format an interest-rate difference in percentage points.

    Args:
        value: Interest-rate difference already expressed in percentage points.

    Returns:
        Difference with two decimal places and its unit.
    """
    return f"{value:,.2f} p.p."


def _comparison_metric_label(label: str, include_subsidy: bool) -> str:
    if include_subsidy:
        return label
    return label.replace("Net average annual", "Average annual")


_COMPARISON_METRICS = (
    _ComparisonMetric("Net financing cost", lambda scenario: pln(scenario.net_financing_cost)),
    _ComparisonMetric("Net investment earnings", lambda scenario: pln(scenario.net_investment_earnings)),
    _ComparisonMetric("Retained surplus", lambda scenario: pln(scenario.retained_surplus)),
    _ComparisonMetric("Net financing cost difference", lambda scenario: pln(scenario.net_financing_cost_delta)),
    _ComparisonMetric("Principal repaid", lambda scenario: pln(scenario.summary.total_principal)),
    _ComparisonMetric(
        "Principal before settlement",
        lambda scenario: pln(scenario.summary.principal_repaid_before_horizon_settlement),
    ),
    _ComparisonMetric("Horizon settlement", lambda scenario: pln(scenario.summary.horizon_settlement)),
    _ComparisonMetric("Gross mortgage interest", lambda scenario: pln(scenario.summary.total_interest)),
    _ComparisonMetric(
        "Subsidy received",
        lambda scenario: pln(scenario.summary.total_subsidy),
        subsidy_metric=True,
    ),
    _ComparisonMetric("Fees paid", lambda scenario: pln(scenario.summary.total_fees)),
    _ComparisonMetric("Total mortgage payments", lambda scenario: pln(scenario.summary.total_cash_outflow)),
    _ComparisonMetric("Total mortgage cost", lambda scenario: pln(scenario.summary.total_mortgage_cost)),
    _ComparisonMetric(
        "Cost / original principal",
        lambda scenario: percentage(scenario.summary.mortgage_cost_to_original_principal),
    ),
    _ComparisonMetric(
        "Cost / principal repaid",
        lambda scenario: percentage(scenario.summary.mortgage_cost_to_principal_repaid),
    ),
    _ComparisonMetric(
        "Net average annual interest rate",
        lambda scenario: percentage(scenario.summary.net_average_annual_interest_rate),
    ),
    _ComparisonMetric(
        "Ending balance",
        lambda scenario: pln(scenario.summary.ending_balance),
        ending_balance_metric=True,
    ),
    _ComparisonMetric("Payoff month", lambda scenario: payoff_label(scenario.summary.payoff_month)),
    _ComparisonMetric("Mortgage payments difference", lambda scenario: pln(scenario.cash_outflow_delta)),
    _ComparisonMetric("Interest difference", lambda scenario: pln(scenario.interest_delta)),
    _ComparisonMetric(
        "Ending balance difference",
        lambda scenario: pln(scenario.ending_balance_delta),
        ending_balance_metric=True,
    ),
    _ComparisonMetric("Total mortgage cost difference", lambda scenario: pln(scenario.mortgage_cost_delta)),
    _ComparisonMetric(
        "Overpayment savings rate",
        lambda scenario: percentage_or_na(scenario.mortgage_cost_savings_to_overpayment_ratio),
    ),
    _ComparisonMetric("Horizon settlement difference", lambda scenario: pln(scenario.horizon_settlement_delta)),
    _ComparisonMetric(
        "Subsidy difference",
        lambda scenario: pln(scenario.subsidy_delta),
        subsidy_metric=True,
    ),
    _ComparisonMetric(
        "Net average annual interest rate difference",
        lambda scenario: _percentage_points(scenario.net_average_annual_interest_rate_percentage_point_delta),
    ),
)
