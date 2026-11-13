"""Baseline-relative scenario comparison reporting."""

from collections.abc import Sequence
from decimal import Decimal

import polars as pl

from mortgage_simulator.simulation.models import (
    ComparisonReport,
    ScenarioComparison,
    SimulationResult,
)

ZERO = Decimal("0")


def compare(results: Sequence[SimulationResult]) -> ComparisonReport:
    """Compare scenario summaries against the first result.

    Args:
        results: Ordered simulation results with the baseline first.

    Returns:
        A report containing each summary and its baseline deltas.

    Raises:
        ValueError: If no simulation results are supplied.
    """
    if not results:
        raise ValueError("at least one simulation result is required")
    baseline = results[0].summary
    comparisons = tuple(
        ScenarioComparison(
            scenario_name=result.scenario_name,
            summary=result.summary,
            net_investment_earnings=result.investment.net_earnings if result.investment else ZERO,
            retained_surplus=result.investment.retained_surplus if result.investment else ZERO,
            net_financing_cost_delta=result.net_financing_cost - results[0].net_financing_cost,
            cash_outflow_delta=result.summary.total_cash_outflow - baseline.total_cash_outflow,
            interest_delta=result.summary.total_interest - baseline.total_interest,
            ending_balance_delta=result.summary.ending_balance - baseline.ending_balance,
            mortgage_cost_delta=result.summary.total_mortgage_cost - baseline.total_mortgage_cost,
            horizon_settlement_delta=result.summary.horizon_settlement - baseline.horizon_settlement,
            subsidy_delta=result.summary.total_subsidy - baseline.total_subsidy,
            net_average_annual_interest_rate_percentage_point_delta=(
                result.summary.net_average_annual_interest_rate - baseline.net_average_annual_interest_rate
            )
            * Decimal("100"),
            mortgage_cost_savings_to_overpayment_ratio=_mortgage_cost_savings_to_overpayment_ratio(
                result,
                baseline.total_mortgage_cost,
            ),
        )
        for result in results
    )
    return ComparisonReport(scenarios=comparisons)


def comparison_frame(report: ComparisonReport, *, include_subsidy: bool = True) -> pl.DataFrame:
    """Convert a comparison report into a display-ready Polars DataFrame.

    Args:
        report: Baseline-relative scenario comparison.
        include_subsidy: Whether to include subsidy totals and differences.

    Returns:
        One summary row for every scenario.
    """
    rows = [
        {
            "scenario": scenario.scenario_name,
            "net_financing_cost": scenario.net_financing_cost,
            "net_investment_earnings": scenario.net_investment_earnings,
            "retained_surplus": scenario.retained_surplus,
            "net_financing_cost_delta": scenario.net_financing_cost_delta,
            "total_principal": scenario.summary.total_principal,
            "principal_repaid_before_horizon_settlement": (scenario.summary.principal_repaid_before_horizon_settlement),
            "horizon_settlement": scenario.summary.horizon_settlement,
            "total_interest": scenario.summary.total_interest,
            "total_subsidy": scenario.summary.total_subsidy,
            "total_fees": scenario.summary.total_fees,
            "total_cash_outflow": scenario.summary.total_cash_outflow,
            "total_mortgage_cost": scenario.summary.total_mortgage_cost,
            "mortgage_cost_to_original_principal": scenario.summary.mortgage_cost_to_original_principal,
            "mortgage_cost_to_principal_repaid": scenario.summary.mortgage_cost_to_principal_repaid,
            "net_average_annual_interest_rate": scenario.summary.net_average_annual_interest_rate,
            "ending_balance": scenario.summary.ending_balance,
            "payoff_month": scenario.summary.payoff_month,
            "cash_outflow_delta": scenario.cash_outflow_delta,
            "interest_delta": scenario.interest_delta,
            "ending_balance_delta": scenario.ending_balance_delta,
            "mortgage_cost_delta": scenario.mortgage_cost_delta,
            "horizon_settlement_delta": scenario.horizon_settlement_delta,
            "subsidy_delta": scenario.subsidy_delta,
            "net_average_annual_interest_rate_percentage_point_delta": (
                scenario.net_average_annual_interest_rate_percentage_point_delta
            ),
        }
        for scenario in report.scenarios
    ]
    frame = pl.DataFrame(rows)
    if include_subsidy:
        return frame
    return frame.drop("total_subsidy", "subsidy_delta")


def _mortgage_cost_savings_to_overpayment_ratio(
    result: SimulationResult,
    baseline_total_mortgage_cost: Decimal,
) -> Decimal | None:
    total_overpayment = sum(
        (payment.recurring_overpayment + payment.lump_sum for payment in result.payments),
        start=ZERO,
    )
    if total_overpayment == ZERO:
        return None
    return (baseline_total_mortgage_cost - result.summary.total_mortgage_cost) / total_overpayment
