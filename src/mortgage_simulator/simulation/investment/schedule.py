"""Deposit interest, tax, and renewal schedule calculations."""

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from mortgage_simulator.simulation.models import DepositInvestment, DepositTerm

CENT = Decimal("0.01")
TAX_RATE = Decimal("0.19")
MONTHS_PER_YEAR = Decimal("12")


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


def calculate_investment_schedule(
    investment: DepositInvestment, count: int, payoff: int | None
) -> tuple[Decimal, int, tuple[DepositTerm, ...]]:
    """Simulate deposit terms, stopping renewals after the mortgage payoff month.

    Args:
        investment: Initial capital, annual rate, and deposit term duration.
        count: Planned number of completed terms.
        payoff: Mortgage payoff month, or None if it remains outstanding.

    Returns:
        Final balance, completion month, and chronological maturity records.
    """
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
