"""Exact investment projections shared by headless exports and presentation."""

import polars as pl

from mortgage_simulator.simulation.models import SimulationResult


def investment_ledger_frame(result: SimulationResult) -> pl.DataFrame:
    """Project credited maturities using decimal strings to preserve precision.

    Args:
        result: Scenario whose investment ledger is required.

    Returns:
        Scenario-tagged maturity rows, or an empty frame without an investment.
    """
    if result.investment is None:
        return pl.DataFrame()
    return pl.DataFrame(
        [
            {
                "scenario": result.scenario_name,
                "maturity_month": term.maturity_month,
                "opening_balance": str(term.opening_balance),
                "gross_interest": str(term.gross_interest),
                "tax": str(term.tax),
                "closing_balance": str(term.closing_balance),
            }
            for term in result.investment.terms
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
                "net_earnings": str(candidate.investment.net_earnings),
                "retained_surplus": str(candidate.investment.retained_surplus),
            }
            for index, candidate in enumerate(result.investment_candidates)
        ]
    )
