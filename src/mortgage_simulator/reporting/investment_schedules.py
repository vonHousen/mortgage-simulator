"""Exact investment projections shared by headless exports and presentation."""

import polars as pl

from mortgage_simulator.simulation.models import InvestmentSummary, SimulationResult


def investment_ledger_frame(result: SimulationResult) -> pl.DataFrame:
    """Project credited maturities using decimal strings to preserve precision.

    Args:
        result: Scenario whose investment ledger is required.

    Returns:
        Scenario-tagged maturity rows, or an empty frame without an investment.
    """
    deposits: list[tuple[int, int | None, InvestmentSummary]] = [
        (item.investment_index, item.opening_month, item.summary) for item in result.investments
    ]
    if not deposits and result.investment is not None:
        deposits = [(1, None, result.investment)]
    return pl.DataFrame(
        [
            {
                "scenario": result.scenario_name,
                "investment_index": index,
                "opening_month": opening,
                "maturity_month": term.maturity_month,
                "opening_balance": str(term.opening_balance),
                "gross_interest": str(term.gross_interest),
                "tax": str(term.tax),
                "closing_balance": str(term.closing_balance),
            }
            for index, opening, summary in deposits
            for term in summary.terms
        ],
        schema_overrides={"opening_month": pl.Int64},
    )


def deposit_outcomes_frame(result: SimulationResult) -> pl.DataFrame:
    """Project funding and disposition for every deposit in a result.

    Args:
        result: Scenario whose individual deposit outcomes are required.
    """
    return pl.DataFrame(
        [
            {
                "scenario": result.scenario_name,
                "investment_index": item.investment_index,
                "opening_month": item.opening_month,
                "completion_month": item.summary.completion_month,
                "initial_amount": str(item.initial_amount),
                "gross_interest": str(item.summary.gross_interest),
                "tax": str(item.summary.tax),
                "net_earnings": str(item.summary.net_earnings),
                "applied_repayment": str(item.summary.applied_repayment),
                "retained_surplus": str(item.summary.retained_surplus),
            }
            for item in result.investments
        ]
    )


def investment_candidates_frame(result: SimulationResult) -> pl.DataFrame:
    """Project deposit timing candidates in the engine's ranked order.

    Args:
        result: Scenario whose candidate comparison is required.

    Returns:
        Scenario-tagged candidate rows with exact decimal strings.
    """
    return pl.DataFrame(
        [
            {
                "scenario": result.scenario_name,
                "recommended": index == 0,
                "term_count": candidate.term_count,
                "repayment_month": candidate.repayment_month,
                "net_financing_cost": str(candidate.net_financing_cost),
                "total_mortgage_cost": str(candidate.total_mortgage_cost),
                "ending_balance": str(candidate.ending_balance),
                "net_earnings": str(candidate.net_earnings),
                "retained_surplus": str(candidate.retained_surplus),
            }
            for index, candidate in enumerate(result.investment_candidates)
        ]
    )
