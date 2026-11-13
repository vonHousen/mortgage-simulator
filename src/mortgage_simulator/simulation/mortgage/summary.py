"""Aggregate mortgage costs and balance exposure."""

from dataclasses import dataclass
from decimal import Decimal

from mortgage_simulator.simulation.models import (
    InterestCalculationMethod,
    MonthlyPayment,
    MortgageTerms,
    SimulationSummary,
)
from mortgage_simulator.simulation.mortgage.calendar import interest_year_fraction, previous_payment_date

ZERO = Decimal("0")
MONTHS_PER_YEAR = Decimal("12")


@dataclass(frozen=True)
class _MortgageTotals:
    """Accumulated payment values after horizon accounting."""

    total_principal: Decimal
    principal_repaid_before_horizon_settlement: Decimal
    horizon_settlement: Decimal
    total_interest: Decimal
    total_subsidy: Decimal
    total_fees: Decimal
    total_cash_outflow: Decimal
    total_mortgage_cost: Decimal
    ending_balance: Decimal


def summarize(payments: tuple[MonthlyPayment, ...], terms: MortgageTerms) -> SimulationSummary:
    """Summarize payments using mortgage terms for principal and exposure."""
    totals = _aggregate(payments, terms)
    return SimulationSummary(
        total_principal=totals.total_principal,
        principal_repaid_before_horizon_settlement=totals.principal_repaid_before_horizon_settlement,
        horizon_settlement=totals.horizon_settlement,
        total_interest=totals.total_interest,
        total_subsidy=totals.total_subsidy,
        total_fees=totals.total_fees,
        total_cash_outflow=totals.total_cash_outflow,
        total_mortgage_cost=totals.total_mortgage_cost,
        mortgage_cost_to_original_principal=totals.total_mortgage_cost / terms.principal,
        mortgage_cost_to_principal_repaid=totals.total_mortgage_cost / totals.total_principal,
        net_average_annual_interest_rate=_net_average_annual_interest_rate(
            payments,
            totals.total_interest - totals.total_subsidy,
            terms.interest_calculation_method,
        ),
        ending_balance=totals.ending_balance,
        payoff_month=payments[-1].month if totals.ending_balance == ZERO else None,
    )


def _aggregate(payments: tuple[MonthlyPayment, ...], terms: MortgageTerms) -> _MortgageTotals:
    principal_repaid_before_horizon_settlement = sum(
        (payment.scheduled_principal + payment.recurring_overpayment + payment.lump_sum for payment in payments),
        start=ZERO,
    )
    horizon_settlement = sum((payment.horizon_settlement for payment in payments), start=ZERO)
    total_interest = sum((payment.interest for payment in payments), start=ZERO)
    total_subsidy = sum((payment.subsidy for payment in payments), start=ZERO)
    total_fees = sum((payment.fees for payment in payments), start=ZERO)
    total_mortgage_cost = total_interest - total_subsidy + total_fees
    ending_balance = payments[-1].closing_balance
    total_cash_outflow = sum((payment.cash_outflow for payment in payments), start=ZERO)
    total_principal = principal_repaid_before_horizon_settlement + horizon_settlement
    if terms.settle_remaining_principal_at_horizon:
        total_principal = terms.principal - ending_balance
        principal_repaid_before_horizon_settlement = total_principal - horizon_settlement
        total_cash_outflow = total_principal + total_mortgage_cost
    return _MortgageTotals(
        total_principal,
        principal_repaid_before_horizon_settlement,
        horizon_settlement,
        total_interest,
        total_subsidy,
        total_fees,
        total_cash_outflow,
        total_mortgage_cost,
        ending_balance,
    )


def _net_average_annual_interest_rate(
    payments: tuple[MonthlyPayment, ...],
    net_interest: Decimal,
    method: InterestCalculationMethod,
) -> Decimal:
    if method == InterestCalculationMethod.EQUAL_MONTHS:
        opening_balance_total = sum((payment.opening_balance for payment in payments), start=ZERO)
        return net_interest * MONTHS_PER_YEAR / opening_balance_total
    balance_exposure = sum(
        (
            payment.opening_balance
            * interest_year_fraction(method, previous_payment_date(payment.payment_date), payment.payment_date)
            for payment in payments
        ),
        start=ZERO,
    )
    return net_interest / balance_exposure
