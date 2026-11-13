"""Monthly mortgage charges and principal allocation."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from mortgage_simulator.simulation.models import (
    MonthlyPayment,
    MortgageTerms,
    OverpaymentScenario,
    RatePeriod,
    SubsidyTerms,
)
from mortgage_simulator.simulation.mortgage.calendar import (
    calculate_payment_date,
    interest_year_fraction,
    previous_payment_date,
)
from mortgage_simulator.simulation.mortgage.insurance import calculate_monthly_insurance

ZERO = Decimal("0")
MONTHS_PER_YEAR = Decimal("12")
ANNUAL_FEE_INTERVAL_MONTHS = 12


@dataclass(frozen=True)
class _PrincipalAllocation:
    """Principal applied in mortgage payment order."""

    scheduled: Decimal
    recurring: Decimal
    lump_sum: Decimal
    horizon_settlement: Decimal
    remaining_balance: Decimal


@dataclass(frozen=True)
class _Charges:
    """Interest, subsidy, and fee components for one month."""

    interest: Decimal
    subsidy: Decimal
    monthly_insurance: Decimal
    monthly_fixed_fees: Decimal
    annual_fixed_fee: Decimal

    @property
    def fees(self) -> Decimal:
        """Return the sum of the monthly fee components."""
        return self.monthly_insurance + self.monthly_fixed_fees + self.annual_fixed_fee


def calculate_payment(
    terms: MortgageTerms,
    scenario: OverpaymentScenario,
    month: int,
    opening_balance: Decimal,
    previous_opening_balance: Decimal,
) -> MonthlyPayment:
    """Calculate one month from terms, scenario, month, and adjacent opening balances."""
    payment_date = calculate_payment_date(terms.first_payment_date, month)
    charges = _calculate_charges(terms, month, opening_balance, previous_opening_balance, payment_date)

    scheduled = min(terms.principal / Decimal(terms.contractual_term_months), opening_balance)
    allocation = _apply_principal(
        terms,
        scenario,
        month,
        opening_balance,
        scheduled,
        scheduled + charges.interest - charges.subsidy + charges.fees,
    )

    principal = allocation.scheduled + allocation.recurring + allocation.lump_sum + allocation.horizon_settlement
    cash_outflow_without_fees = principal + charges.interest - charges.subsidy
    cash_outflow = cash_outflow_without_fees + charges.fees
    return MonthlyPayment(
        month=month,
        payment_date=payment_date,
        opening_balance=opening_balance,
        scheduled_principal=allocation.scheduled,
        recurring_overpayment=allocation.recurring,
        lump_sum=allocation.lump_sum,
        horizon_settlement=allocation.horizon_settlement,
        interest=charges.interest,
        subsidy=charges.subsidy,
        monthly_insurance=charges.monthly_insurance,
        monthly_fixed_fees=charges.monthly_fixed_fees,
        annual_fixed_fee=charges.annual_fixed_fee,
        fees=charges.fees,
        cash_outflow_without_fees=cash_outflow_without_fees,
        cash_outflow=cash_outflow,
        closing_balance=allocation.remaining_balance,
    )


def _calculate_charges(
    terms: MortgageTerms,
    month: int,
    opening_balance: Decimal,
    previous_opening_balance: Decimal,
    payment_date: date,
) -> _Charges:
    period_start = previous_payment_date(payment_date)
    previous_period_start = previous_payment_date(period_start)
    annual_rate = _annual_rate_for_month(terms.rate_periods, month)
    interest = (
        opening_balance
        * annual_rate
        * interest_year_fraction(
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
    return _Charges(interest, subsidy, monthly_insurance, monthly_fixed_fees, annual_fixed_fee)


def _apply_principal(
    terms: MortgageTerms,
    scenario: OverpaymentScenario,
    month: int,
    opening_balance: Decimal,
    applied_scheduled: Decimal,
    base_cash_outflow: Decimal,
) -> _PrincipalAllocation:
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

    return _PrincipalAllocation(
        applied_scheduled, applied_recurring, applied_lump_sum, horizon_settlement, remaining_balance
    )


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
