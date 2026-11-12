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
    maximum_count = (terms.analysis_horizon_months - investment.start_month) // investment.term_months
    counts = range(maximum_count + 1) if investment.mode == InvestmentMode.AUTOMATIC else (investment.term_count,)
    results: list[tuple[SimulationResult, InvestmentCandidate]] = []
    for count in counts:
        assert count is not None
        balance = investment.initial_amount
        ledger: list[DepositTerm] = []
        completion = investment.start_month
        if payoff is None or payoff > investment.start_month:
            for index in range(1, count + 1):
                completion = investment.start_month + index * investment.term_months
                term = deposit_term(balance, investment, completion)
                ledger.append(term)
                balance = term.closing_balance
                if payoff is not None and payoff <= completion:
                    break
        applicable = payoff is None or payoff > completion
        # A mortgage paid by other payments on the maturity date consumes no deposit funds.
        if applicable:
            payment_scenario = base_scenario.model_copy(
                update={"lump_sums": (*base_scenario.lump_sums, LumpSum(month=completion, amount=balance))}
            )
            result = mortgage_simulator(terms, payment_scenario)
            previous_lump = next((p.lump_sum for p in base_result.payments if p.month == completion), ZERO)
            actual_lump = next((p.lump_sum for p in result.payments if p.month == completion), ZERO)
            applied = actual_lump - previous_lump
        else:
            result = base_result
            applied = ZERO
        gross = sum((term.gross_interest for term in ledger), ZERO)
        tax = sum((term.tax for term in ledger), ZERO)
        summary = InvestmentSummary(
            planned_term_count=count,
            completion_month=completion,
            gross_interest=gross,
            tax=tax,
            net_earnings=gross - tax,
            applied_repayment=applied,
            retained_surplus=balance - applied,
            terms=tuple(ledger),
        )
        candidate = InvestmentCandidate(
            term_count=count,
            repayment_month=completion,
            total_mortgage_cost=result.summary.total_mortgage_cost,
            ending_balance=result.summary.ending_balance,
            investment=summary,
        )
        results.append((result, candidate))
    results.sort(key=lambda item: (item[1].total_mortgage_cost, item[1].repayment_month, item[1].term_count))
    winner, candidate = results[0]
    return winner.model_copy(
        update={"investment": candidate.investment, "investment_candidates": tuple(item[1] for item in results)}
    )
