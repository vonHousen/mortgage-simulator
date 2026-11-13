"""Mortgage schedule and aggregate financial calculations."""

import calendar
from datetime import date
from decimal import Decimal
from typing import assert_never

from mortgage_simulator.simulation.models import (
    InterestCalculationMethod,
    MonthlyPayment,
    MortgageTerms,
    OverpaymentScenario,
    RatePeriod,
    SimulationResult,
    SimulationSummary,
    SubsidyTerms,
)
from mortgage_simulator.simulation.monthly_insurance import calculate_monthly_insurance

MONTHS_PER_YEAR = Decimal("12")
ANNUAL_FEE_INTERVAL_MONTHS = 12
ORDINARY_YEAR_DAYS = Decimal("365")
LEAP_YEAR_DAYS = Decimal("366")
ZERO = Decimal("0")


def calculate_schedule(terms: MortgageTerms, scenario: OverpaymentScenario) -> SimulationResult:
    """Calculate a mortgage schedule from explicit recurring and lump-sum payments.

    Args:
        terms: Mortgage, subsidy, fee, rate, and horizon assumptions.
        scenario: Principal payments to apply; investment evaluation belongs to the caller.

    Returns:
        Ordered mortgage payments and their aggregate summary.
    """
    opening_balance = terms.principal
    previous_opening_balance = opening_balance
    payments: list[MonthlyPayment] = []

    for month in range(1, terms.analysis_horizon_months + 1):
        payment = _calculate_payment(terms, scenario, month, opening_balance, previous_opening_balance)
        payments.append(payment)
        previous_opening_balance = opening_balance
        opening_balance = payment.closing_balance
        if opening_balance == ZERO:
            break

    payment_tuple = tuple(payments)
    return SimulationResult(
        scenario_name=scenario.name,
        payments=payment_tuple,
        summary=_summarize(payment_tuple, terms),
    )


def _calculate_payment(
    terms: MortgageTerms,
    scenario: OverpaymentScenario,
    month: int,
    opening_balance: Decimal,
    previous_opening_balance: Decimal,
) -> MonthlyPayment:
    payment_date = _payment_date(terms.first_payment_date, month)
    period_start = _previous_payment_date(payment_date)
    previous_period_start = _previous_payment_date(period_start)
    annual_rate = _annual_rate_for_month(terms.rate_periods, month)
    interest = (
        opening_balance
        * annual_rate
        * _interest_year_fraction(
            terms.interest_calculation_method,
            period_start,
            payment_date,
        )
    )
    subsidy = _calculate_subsidy(opening_balance, terms.subsidy, month)
    monthly_insurance, monthly_fixed_fees, annual_fixed_fee = _calculate_fee_components(
        terms,
        previous_opening_balance,
        opening_balance,
        previous_period_start,
        period_start,
        payment_date,
        month,
    )
    fees = monthly_insurance + monthly_fixed_fees + annual_fixed_fee

    applied_scheduled, applied_recurring, applied_lump_sum, horizon_settlement, remaining_balance = _apply_principal(
        terms,
        scenario,
        month,
        opening_balance,
        min(terms.principal / Decimal(terms.contractual_term_months), opening_balance) + interest - subsidy + fees,
    )

    principal = applied_scheduled + applied_recurring + applied_lump_sum + horizon_settlement
    cash_outflow_without_fees = principal + interest - subsidy
    cash_outflow = cash_outflow_without_fees + fees
    return MonthlyPayment(
        month=month,
        payment_date=payment_date,
        opening_balance=opening_balance,
        scheduled_principal=applied_scheduled,
        recurring_overpayment=applied_recurring,
        lump_sum=applied_lump_sum,
        horizon_settlement=horizon_settlement,
        interest=interest,
        subsidy=subsidy,
        monthly_insurance=monthly_insurance,
        monthly_fixed_fees=monthly_fixed_fees,
        annual_fixed_fee=annual_fixed_fee,
        fees=fees,
        cash_outflow_without_fees=cash_outflow_without_fees,
        cash_outflow=cash_outflow,
        closing_balance=remaining_balance,
    )


def _apply_principal(
    terms: MortgageTerms,
    scenario: OverpaymentScenario,
    month: int,
    opening_balance: Decimal,
    base_cash_outflow: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    scheduled_principal = terms.principal / Decimal(terms.contractual_term_months)
    applied_scheduled = min(scheduled_principal, opening_balance)
    remaining_balance = opening_balance - applied_scheduled

    recurring_requested = ZERO
    if scenario.recurring_start_month is not None and month >= scenario.recurring_start_month:
        if scenario.cash_outflow_target > ZERO:
            recurring_requested = max(scenario.cash_outflow_target - base_cash_outflow, ZERO)
        else:
            recurring_requested = scenario.recurring_amount
    applied_recurring = min(recurring_requested, remaining_balance)
    remaining_balance -= applied_recurring

    applied_lump_sum = ZERO
    for lump_sum in scenario.lump_sums:
        if lump_sum.month == month:
            applied_amount = min(lump_sum.amount, remaining_balance)
            applied_lump_sum += applied_amount
            remaining_balance -= applied_amount

    horizon_settlement = ZERO
    if terms.settle_remaining_principal_at_horizon and month == terms.analysis_horizon_months:
        horizon_settlement = remaining_balance
        remaining_balance = ZERO

    return applied_scheduled, applied_recurring, applied_lump_sum, horizon_settlement, remaining_balance


def _annual_rate_for_month(rate_periods: tuple[RatePeriod, ...], month: int) -> Decimal:
    for period in rate_periods:
        if period.start_month <= month <= period.end_month:
            return period.annual_rate
    raise ValueError(f"no annual rate configured for month {month}")


def _calculate_subsidy(opening_balance: Decimal, terms: SubsidyTerms, month: int) -> Decimal:
    if not terms.enabled:
        return ZERO
    coefficient = terms.coefficient if month <= 60 else terms.second_coefficient
    return opening_balance * (coefficient - terms.reference_rate) / MONTHS_PER_YEAR


def _payment_date(first_payment_date: date, month: int) -> date:
    zero_based_month = first_payment_date.year * 12 + first_payment_date.month - 1 + month - 1
    year, month_index = divmod(zero_based_month, 12)
    return date(year, month_index + 1, first_payment_date.day)


def _previous_payment_date(payment_date: date) -> date:
    zero_based_month = payment_date.year * 12 + payment_date.month - 2
    year, month_index = divmod(zero_based_month, 12)
    return date(year, month_index + 1, payment_date.day)


def _interest_year_fraction(method: InterestCalculationMethod, period_start: date, period_end: date) -> Decimal:
    if method == InterestCalculationMethod.EQUAL_MONTHS:
        return Decimal("1") / MONTHS_PER_YEAR
    if method == InterestCalculationMethod.CALENDAR_DAYS:
        return _calendar_year_fraction(period_start, period_end)
    assert_never(method)


def _calendar_year_fraction(period_start: date, period_end: date) -> Decimal:
    fraction = ZERO
    segment_start = period_start
    while segment_start < period_end:
        next_year = date(segment_start.year + 1, 1, 1) if segment_start.year < 9999 else period_end
        segment_end = min(next_year, period_end)
        days_in_year = LEAP_YEAR_DAYS if calendar.isleap(segment_start.year) else ORDINARY_YEAR_DAYS
        fraction += Decimal((segment_end - segment_start).days) / days_in_year
        segment_start = segment_end
    return fraction


def _calculate_fee_components(
    terms: MortgageTerms,
    previous_opening_balance: Decimal,
    opening_balance: Decimal,
    previous_period_start: date,
    period_start: date,
    payment_date: date,
    month: int,
) -> tuple[Decimal, Decimal, Decimal]:
    monthly_insurance = ZERO
    monthly_fixed_fees = ZERO
    fee_end_month = terms.fees.insurance_end_month
    if fee_end_month is None or month <= fee_end_month:
        monthly_insurance = calculate_monthly_insurance(
            method=terms.fees.insurance_calculation_method,
            monthly_rate=terms.fees.monthly_insurance_rate,
            previous_opening_balance=previous_opening_balance,
            opening_balance=opening_balance,
            previous_period_days=(period_start - previous_period_start).days,
            current_period_days=(payment_date - period_start).days,
        )
        monthly_fixed_fees = terms.fees.monthly_fixed_fees
    annual_fixed_fee = terms.fees.annual_fixed_fee if (month - 1) % ANNUAL_FEE_INTERVAL_MONTHS == 0 else ZERO
    return monthly_insurance, monthly_fixed_fees, annual_fixed_fee


def _summarize(
    payments: tuple[MonthlyPayment, ...],
    terms: MortgageTerms,
) -> SimulationSummary:
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
    return SimulationSummary(
        total_principal=total_principal,
        principal_repaid_before_horizon_settlement=principal_repaid_before_horizon_settlement,
        horizon_settlement=horizon_settlement,
        total_interest=total_interest,
        total_subsidy=total_subsidy,
        total_fees=total_fees,
        total_cash_outflow=total_cash_outflow,
        total_mortgage_cost=total_mortgage_cost,
        mortgage_cost_to_original_principal=total_mortgage_cost / terms.principal,
        mortgage_cost_to_principal_repaid=total_mortgage_cost / total_principal,
        net_average_annual_interest_rate=_net_average_annual_interest_rate(
            payments,
            total_interest - total_subsidy,
            terms.interest_calculation_method,
        ),
        ending_balance=ending_balance,
        payoff_month=payments[-1].month if ending_balance == ZERO else None,
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
            * _interest_year_fraction(method, _previous_payment_date(payment.payment_date), payment.payment_date)
            for payment in payments
        ),
        start=ZERO,
    )
    return net_interest / balance_exposure
