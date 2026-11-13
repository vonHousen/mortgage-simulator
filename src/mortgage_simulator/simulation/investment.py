"""Deposit maturities and mortgage-cost optimization."""

from decimal import Decimal

from mortgage_simulator.simulation.investment_schedule import calculate_investment_schedule
from mortgage_simulator.simulation.models import (
    DepositInvestment,
    DepositTerm,
    InvestmentCandidate,
    InvestmentMode,
    InvestmentSummary,
    LumpSum,
    MortgageTerms,
    OverpaymentScenario,
    SimulationRequest,
    SimulationResult,
)
from mortgage_simulator.simulation.mortgage_schedule import calculate_schedule

ZERO = Decimal("0")


def evaluate_investment(
    terms: MortgageTerms,
    scenario: OverpaymentScenario,
) -> SimulationResult:
    """Evaluate scenario deposit candidates using the shared mortgage schedule calculator.

    Args:
        terms: Shared mortgage assumptions.
        scenario: Scenario containing one investment.

    Returns:
        Selected mortgage schedule, investment ledger, and candidate comparisons.
    """
    SimulationRequest(terms=terms, scenarios=(scenario,))
    candidates = _evaluate_candidates(terms, scenario)
    return _select_result(candidates)


def _evaluate_candidates(
    terms: MortgageTerms, scenario: OverpaymentScenario
) -> list[tuple[SimulationResult, InvestmentCandidate]]:
    investment = scenario.investment
    assert investment is not None
    scenario_without_investment = scenario.model_copy(update={"investment": None})
    result_without_investment = calculate_schedule(terms, scenario_without_investment)
    payoff = result_without_investment.summary.payoff_month
    if result_without_investment.summary.horizon_settlement > ZERO:
        payoff = None
    return [
        _evaluate_candidate(terms, scenario_without_investment, result_without_investment, investment, count, payoff)
        for count in _candidate_counts(terms, investment)
    ]


def _select_result(results: list[tuple[SimulationResult, InvestmentCandidate]]) -> SimulationResult:
    results.sort(key=lambda item: (item[1].total_mortgage_cost, item[1].repayment_month, item[1].term_count))
    winner, candidate = results[0]
    return winner.model_copy(
        update={"investment": candidate.investment, "investment_candidates": tuple(item[1] for item in results)}
    )


def _candidate_counts(terms: MortgageTerms, investment: DepositInvestment) -> range | tuple[int]:
    if investment.mode == InvestmentMode.AUTOMATIC:
        maximum = (terms.analysis_horizon_months - investment.start_month) // investment.term_months
        return range(maximum + 1)
    assert investment.term_count is not None
    return (investment.term_count,)


def _apply_repayment(
    terms: MortgageTerms,
    scenario: OverpaymentScenario,
    result_without_investment: SimulationResult,
    balance: Decimal,
    completion: int,
) -> tuple[SimulationResult, Decimal]:
    payment_scenario = scenario.model_copy(
        update={"lump_sums": (*scenario.lump_sums, LumpSum(month=completion, amount=balance))}
    )
    result = calculate_schedule(terms, payment_scenario)
    previous_lump = next((p.lump_sum for p in result_without_investment.payments if p.month == completion), ZERO)
    actual_lump = next((p.lump_sum for p in result.payments if p.month == completion), ZERO)
    return result, actual_lump - previous_lump


def _investment_summary(
    count: int, balance: Decimal, completion: int, ledger: tuple[DepositTerm, ...], applied: Decimal
) -> InvestmentSummary:
    gross = sum((term.gross_interest for term in ledger), ZERO)
    tax = sum((term.tax for term in ledger), ZERO)
    return InvestmentSummary(
        planned_term_count=count,
        completion_month=completion,
        gross_interest=gross,
        tax=tax,
        net_earnings=gross - tax,
        applied_repayment=applied,
        retained_surplus=balance - applied,
        terms=ledger,
    )


def _evaluate_candidate(
    terms: MortgageTerms,
    scenario: OverpaymentScenario,
    result_without_investment: SimulationResult,
    investment: DepositInvestment,
    count: int,
    payoff: int | None,
) -> tuple[SimulationResult, InvestmentCandidate]:
    balance, completion, ledger = calculate_investment_schedule(investment, count, payoff)
    result, applied = result_without_investment, ZERO
    # A mortgage paid by other payments on the maturity date consumes no deposit funds.
    if payoff is None or payoff > completion:
        result, applied = _apply_repayment(terms, scenario, result_without_investment, balance, completion)
    summary = _investment_summary(count, balance, completion, ledger, applied)
    return result, InvestmentCandidate(
        term_count=count,
        repayment_month=completion,
        total_mortgage_cost=result.summary.total_mortgage_cost,
        ending_balance=result.summary.ending_balance,
        investment=summary,
    )
