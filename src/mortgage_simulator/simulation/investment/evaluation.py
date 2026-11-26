"""Deposit maturities and mortgage-cost optimization."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from mortgage_simulator.simulation.investment.schedule import calculate_investment_schedule
from mortgage_simulator.simulation.models import (
    DepositInvestment,
    DepositOutcome,
    InvestmentCandidate,
    InvestmentMode,
    InvestmentSummary,
    LumpSum,
    MortgageTerms,
    OverpaymentScenario,
    SimulationResult,
)
from mortgage_simulator.simulation.mortgage.schedule import calculate_schedule

ZERO = Decimal("0")


@dataclass(frozen=True)
class _DepositPlan:
    """One scheduled opening and its payout before any early payoff."""

    investment_index: int
    deposit: DepositInvestment
    count: int
    balance: Decimal
    completion: int


def evaluate_investment(terms: MortgageTerms, scenario: OverpaymentScenario) -> SimulationResult:
    """Return the best investment-funded result for mortgage terms and a scenario.

    Args:
        terms: Mortgage assumptions and analysis horizon.
        scenario: Mortgage overpayments and configured deposit entries.
    """
    entries = scenario.deposit_entries
    automatic = next((entry for entry in entries if entry.mode == InvestmentMode.AUTOMATIC), None)
    if automatic is None:
        result = _evaluate_plan(terms, scenario, 0)
        if result.investment is None:
            return result
        candidate = _candidate(result, 1)
        return result.model_copy(update={"investment_candidates": (candidate,)})

    automatic_index = next(index for index, entry in enumerate(entries, 1) if entry.mode == InvestmentMode.AUTOMATIC)
    maximum = (terms.analysis_horizon_months - automatic.start_month) // automatic.term_months
    results = []
    for count in range(maximum + 1):
        result = _evaluate_plan(terms, scenario, count)
        results.append((result, _candidate(result, automatic_index)))
    results.sort(key=lambda item: (item[1].net_financing_cost, item[1].repayment_month, item[1].term_count))
    return results[0][0].model_copy(update={"investment_candidates": tuple(candidate for _, candidate in results)})


def _evaluate_plan(terms: MortgageTerms, scenario: OverpaymentScenario, automatic_count: int) -> SimulationResult:
    plans = _deposit_plans(scenario.deposit_entries, automatic_count)
    balloons = tuple(LumpSum(month=plan.completion, amount=plan.balance) for plan in plans)
    # Payouts after payoff cannot affect the mortgage. The actual payoff then determines which deposits opened.
    result = calculate_schedule(terms, scenario.model_copy(update={"lump_sums": (*scenario.lump_sums, *balloons)}))
    available = {payment.month: payment.lump_sum for payment in result.payments}
    for lump_sum in scenario.lump_sums:
        available[lump_sum.month] = max(available.get(lump_sum.month, ZERO) - lump_sum.amount, ZERO)

    outcomes = _deposit_outcomes(plans, result.summary.payoff_month, available)
    entries = scenario.deposit_entries
    legacy = outcomes[0].summary if len(entries) == 1 and entries[0].contribution_months == 1 else None
    return result.model_copy(update={"investments": outcomes, "investment": legacy})


def _deposit_plans(entries: tuple[DepositInvestment, ...], automatic_count: int) -> list[_DepositPlan]:
    plans: list[_DepositPlan] = []
    indexed = sorted(enumerate(entries, 1), key=lambda item: item[1].contribution_months == 1)
    for index, entry in indexed:
        count = automatic_count if entry.term_count is None else entry.term_count
        for month in range(entry.start_month, entry.start_month + entry.contribution_months):
            deposit = entry.model_copy(update={"start_month": month})
            balance, completion, _ = calculate_investment_schedule(deposit, count, None)
            plans.append(_DepositPlan(index, deposit, count, balance, completion))
    return plans


def _deposit_outcomes(
    plans: list[_DepositPlan], payoff: int | None, available: dict[int, Decimal]
) -> tuple[DepositOutcome, ...]:
    outcomes: list[DepositOutcome] = []
    remaining = defaultdict(lambda: ZERO, available)
    for plan in plans:
        deposit = plan.deposit
        if deposit.contribution_months > 1 and payoff is not None and payoff <= deposit.start_month:
            continue
        # A mortgage paid by other payments on the maturity date consumes no deposit funds.
        applied = min(remaining[plan.completion], plan.balance)
        remaining[plan.completion] -= applied
        balance, completion, ledger = calculate_investment_schedule(deposit, plan.count, payoff)
        gross = sum((term.gross_interest for term in ledger), ZERO)
        tax = sum((term.tax for term in ledger), ZERO)
        outcomes.append(
            DepositOutcome(
                investment_index=plan.investment_index,
                opening_month=deposit.start_month,
                initial_amount=deposit.initial_amount,
                summary=InvestmentSummary(
                    planned_term_count=plan.count,
                    completion_month=completion,
                    gross_interest=gross,
                    tax=tax,
                    net_earnings=gross - tax,
                    applied_repayment=applied,
                    retained_surplus=balance - applied,
                    terms=ledger,
                ),
            )
        )
    return tuple(sorted(outcomes, key=lambda item: (item.investment_index, item.opening_month)))


def _candidate(result: SimulationResult, index: int) -> InvestmentCandidate:
    outcome = next(item for item in result.investments if item.investment_index == index)
    summary = outcome.summary
    other = tuple(item.summary for item in result.investments if item.investment_index != index)
    return InvestmentCandidate(
        term_count=summary.planned_term_count,
        repayment_month=summary.completion_month,
        total_mortgage_cost=result.summary.total_mortgage_cost,
        ending_balance=result.summary.ending_balance,
        investment=summary,
        other_net_earnings=sum((item.net_earnings for item in other), ZERO),
        other_retained_surplus=sum((item.retained_surplus for item in other), ZERO),
    )
