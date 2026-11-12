"""Deposit maturities and mortgage-cost optimization."""

from collections.abc import Callable
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

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

CENT = Decimal("0.01")
TAX_RATE = Decimal("0.19")
MONTHS_PER_YEAR = Decimal("12")
ZERO = Decimal("0")


def deposit_term(balance: Decimal, investment: DepositInvestment, maturity_month: int) -> DepositTerm:
    """Calculate one term using balance, deposit terms, and its maturity month."""
    gross = (balance * investment.annual_rate * investment.term_months / MONTHS_PER_YEAR).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    taxable = gross.quantize(CENT, rounding=ROUND_CEILING)
    tax = (taxable * TAX_RATE).quantize(CENT, rounding=ROUND_CEILING)
    return DepositTerm(
        maturity_month=maturity_month,
        opening_balance=balance,
        gross_interest=gross,
        tax=tax,
        closing_balance=balance + gross - tax,
    )


def evaluate_investment(
    terms: MortgageTerms,
    scenario: OverpaymentScenario,
    mortgage_simulator: Callable[[MortgageTerms, OverpaymentScenario], SimulationResult],
) -> SimulationResult:
    """Evaluate scenario deposit candidates using the supplied mortgage calculator.

    Args:
        terms: Shared mortgage assumptions.
        scenario: Scenario containing one investment.
        mortgage_simulator: Existing mortgage calculation path.

    Returns:
        Selected mortgage schedule, investment ledger, and candidate comparisons.
    """
    SimulationRequest(terms=terms, scenarios=(scenario,))
    investment = scenario.investment
    assert investment is not None
    base_scenario = scenario.model_copy(update={"investment": None})
    base_result = mortgage_simulator(terms, base_scenario)
    payoff = base_result.summary.payoff_month
    if base_result.summary.horizon_settlement > ZERO:
        payoff = None
    results = [
        _evaluate_candidate(terms, base_scenario, base_result, investment, count, payoff, mortgage_simulator)
        for count in _candidate_counts(terms, investment)
    ]
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


def _grow_deposit(
    investment: DepositInvestment, count: int, payoff: int | None
) -> tuple[Decimal, int, tuple[DepositTerm, ...]]:
    balance = investment.initial_amount
    completion = investment.start_month
    ledger: list[DepositTerm] = []
    if payoff is not None and payoff <= completion:
        return balance, completion, ()
    for index in range(1, count + 1):
        completion = investment.start_month + index * investment.term_months
        term = deposit_term(balance, investment, completion)
        ledger.append(term)
        balance = term.closing_balance
        if payoff is not None and payoff <= completion:
            break
    return balance, completion, tuple(ledger)


def _apply_repayment(
    terms: MortgageTerms,
    scenario: OverpaymentScenario,
    base_result: SimulationResult,
    balance: Decimal,
    completion: int,
    mortgage_simulator: Callable[[MortgageTerms, OverpaymentScenario], SimulationResult],
) -> tuple[SimulationResult, Decimal]:
    payment_scenario = scenario.model_copy(
        update={"lump_sums": (*scenario.lump_sums, LumpSum(month=completion, amount=balance))}
    )
    result = mortgage_simulator(terms, payment_scenario)
    previous_lump = next((p.lump_sum for p in base_result.payments if p.month == completion), ZERO)
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
    base_result: SimulationResult,
    investment: DepositInvestment,
    count: int,
    payoff: int | None,
    mortgage_simulator: Callable[[MortgageTerms, OverpaymentScenario], SimulationResult],
) -> tuple[SimulationResult, InvestmentCandidate]:
    balance, completion, ledger = _grow_deposit(investment, count, payoff)
    result, applied = base_result, ZERO
    # A mortgage paid by other payments on the maturity date consumes no deposit funds.
    if payoff is None or payoff > completion:
        result, applied = _apply_repayment(terms, scenario, base_result, balance, completion, mortgage_simulator)
    summary = _investment_summary(count, balance, completion, ledger, applied)
    return result, InvestmentCandidate(
        term_count=count,
        repayment_month=completion,
        total_mortgage_cost=result.summary.total_mortgage_cost,
        ending_balance=result.summary.ending_balance,
        investment=summary,
    )
