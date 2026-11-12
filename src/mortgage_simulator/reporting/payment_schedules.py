"""Payment-schedule projections and CSV serialization."""

from collections.abc import Sequence

import polars as pl

from mortgage_simulator.simulation.models import SimulationResult


def schedule_frame(results: Sequence[SimulationResult], *, include_subsidy: bool = True) -> pl.DataFrame:
    """Convert simulation schedules into one long Polars DataFrame.

    Args:
        results: Simulation results to include in scenario order.
        include_subsidy: Whether to include the monthly subsidy column.

    Returns:
        One row for every calculated scenario month.
    """
    rows = [
        {
            "scenario": result.scenario_name,
            "month": payment.month,
            "payment_date": payment.payment_date,
            "opening_balance": payment.opening_balance,
            "scheduled_principal": payment.scheduled_principal,
            "overpayments": payment.recurring_overpayment + payment.lump_sum + payment.horizon_settlement,
            "recurring_overpayment": payment.recurring_overpayment,
            "lump_sum": payment.lump_sum,
            "horizon_settlement": payment.horizon_settlement,
            "interest": payment.interest,
            "subsidy": payment.subsidy,
            "monthly_insurance": payment.monthly_insurance,
            "monthly_fixed_fees": payment.monthly_fixed_fees,
            "annual_fixed_fee": payment.annual_fixed_fee,
            "fees": payment.fees,
            "cash_outflow_without_fees": payment.cash_outflow_without_fees,
            "cash_outflow": payment.cash_outflow,
            "closing_balance": payment.closing_balance,
        }
        for result in results
        for payment in result.payments
    ]
    frame = pl.DataFrame(rows)
    return frame if include_subsidy else frame.drop("subsidy")


def schedule_csv(results: Sequence[SimulationResult], *, include_subsidy: bool = True) -> str:
    """Serialize all monthly scenario values to one CSV document.

    Args:
        results: Simulation results to serialize.
        include_subsidy: Whether to include the monthly subsidy column.

    Returns:
        UTF-8-compatible CSV text with scenario and exact payment-date columns.
    """
    return schedule_frame(results, include_subsidy=include_subsidy).write_csv()
