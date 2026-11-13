"""Payment calendar boundaries and annual interest fractions."""

import calendar
from datetime import date
from decimal import Decimal
from typing import assert_never

from mortgage_simulator.simulation.models import InterestCalculationMethod

MONTHS_PER_YEAR = Decimal("12")
ORDINARY_YEAR_DAYS = Decimal("365")
LEAP_YEAR_DAYS = Decimal("366")
ZERO = Decimal("0")


def calculate_payment_date(first_payment_date: date, month: int) -> date:
    """Return the installment date for first_payment_date and one-based month."""
    zero_based_month = first_payment_date.year * 12 + first_payment_date.month - 1 + month - 1
    year, month_index = divmod(zero_based_month, 12)
    return date(year, month_index + 1, first_payment_date.day)


def previous_payment_date(payment_date: date) -> date:
    """Return the preceding monthly boundary for payment_date."""
    zero_based_month = payment_date.year * 12 + payment_date.month - 2
    year, month_index = divmod(zero_based_month, 12)
    return date(year, month_index + 1, payment_date.day)


def interest_year_fraction(method: InterestCalculationMethod, period_start: date, period_end: date) -> Decimal:
    """Return the fraction between period_start and period_end under method."""
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
