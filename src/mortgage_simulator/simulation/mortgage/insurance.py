"""Monthly balance-insurance calculations."""

from decimal import Decimal
from typing import assert_never

from mortgage_simulator.simulation.models import InsuranceCalculationMethod

TWO = Decimal("2")


def calculate_monthly_insurance(
    *,
    method: InsuranceCalculationMethod,
    monthly_rate: Decimal,
    previous_opening_balance: Decimal,
    opening_balance: Decimal,
    previous_period_days: int,
    current_period_days: int,
) -> Decimal:
    """Calculate monthly insurance from adjacent balances and payment periods.

    Args:
        method: Insured-balance selection method.
        monthly_rate: Monthly insurance rate expressed as a decimal fraction.
        previous_opening_balance: Opening balance of the preceding installment.
        opening_balance: Opening balance of the current installment.
        previous_period_days: Days in the preceding payment interval.
        current_period_days: Days in the current payment interval.

    Returns:
        The full-precision monthly insurance charge.
    """
    if method == InsuranceCalculationMethod.OPENING_BALANCE:
        insured_balance = opening_balance
    elif method == InsuranceCalculationMethod.MIDPOINT_BALANCE:
        insured_balance = (previous_opening_balance + opening_balance) / TWO
    elif method == InsuranceCalculationMethod.TWO_INTERVAL_WEIGHTED:
        insured_balance = (
            previous_opening_balance * Decimal(current_period_days) + opening_balance * Decimal(previous_period_days)
        ) / Decimal(previous_period_days + current_period_days)
    else:
        assert_never(method)
    return insured_balance * monthly_rate
