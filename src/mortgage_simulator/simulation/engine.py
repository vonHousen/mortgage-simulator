"""Scenario simulation orchestration."""

from mortgage_simulator.simulation.investment.evaluation import evaluate_investment
from mortgage_simulator.simulation.models import MortgageTerms, OverpaymentScenario, SimulationResult
from mortgage_simulator.simulation.mortgage.schedule import calculate_schedule


def simulate(terms: MortgageTerms, scenario: OverpaymentScenario) -> SimulationResult:
    """Coordinate mortgage-only or investment-funded scenario evaluation.

    Args:
        terms: Mortgage, subsidy, fee, rate, and horizon assumptions.
        scenario: Recurring, lump-sum, and optional investment inputs.

    Returns:
        Mortgage schedule and summary, including investment results when configured.
    """
    if scenario.investment is not None:
        return evaluate_investment(terms, scenario)
    return calculate_schedule(terms, scenario)
