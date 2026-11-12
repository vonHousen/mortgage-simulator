"""Explicit test-data factories for required mortgage domain inputs."""

from datetime import date
from decimal import Decimal

from mortgage_simulator.simulation.models import (
    FeeTerms,
    InsuranceCalculationMethod,
    InterestCalculationMethod,
    LumpSum,
    MortgageTerms,
    OverpaymentScenario,
    RatePeriod,
    SubsidyTerms,
)


def default_subsidy_terms(**updates: object) -> SubsidyTerms:
    """Build representative subsidy terms with selected field replacements."""
    values: dict[str, object] = {
        "enabled": True,
        "coefficient": Decimal("0.05"),
        "second_coefficient": updates.get("coefficient", Decimal("0.05")),
        "reference_rate": Decimal("0.02"),
    }
    values.update(updates)
    return SubsidyTerms.model_validate(values)


def default_fee_terms(**updates: object) -> FeeTerms:
    """Build representative fee terms with selected field replacements."""
    values: dict[str, object] = {
        "annual_fixed_fee": Decimal("0"),
        "monthly_insurance_rate": Decimal("0"),
        "insurance_calculation_method": InsuranceCalculationMethod.TWO_INTERVAL_WEIGHTED,
        "monthly_fixed_fees": Decimal("0"),
        "insurance_end_month": None,
    }
    values.update(updates)
    return FeeTerms.model_validate(values)


def default_mortgage_terms(**updates: object) -> MortgageTerms:
    """Build representative mortgage terms with selected field replacements."""
    values: dict[str, object] = {
        "first_payment_date": date(2024, 1, 1),
        "interest_calculation_method": InterestCalculationMethod.CALENDAR_DAYS,
        "principal": Decimal("500000"),
        "contractual_term_months": 360,
        "analysis_horizon_months": 120,
        "settle_remaining_principal_at_horizon": True,
        "rate_periods": (
            RatePeriod(start_month=1, end_month=60, annual_rate=Decimal("0.07")),
            RatePeriod(start_month=61, end_month=120, annual_rate=Decimal("0.08")),
        ),
        "subsidy": default_subsidy_terms(),
        "fees": default_fee_terms(),
    }
    values.update(updates)
    return MortgageTerms.model_validate(values)


def synthetic_terms(
    *,
    interest_calculation_method: InterestCalculationMethod = InterestCalculationMethod.CALENDAR_DAYS,
) -> MortgageTerms:
    """Build the shared synthetic mortgage profile.

    Args:
        interest_calculation_method: Period-interest calculation used by the test.

    Returns:
        Complete synthetic mortgage terms shared across test layers.
    """
    return MortgageTerms(
        first_payment_date=date(2024, 1, 1),
        interest_calculation_method=interest_calculation_method,
        principal=Decimal("500000"),
        contractual_term_months=360,
        analysis_horizon_months=120,
        settle_remaining_principal_at_horizon=False,
        rate_periods=(
            RatePeriod(start_month=1, end_month=60, annual_rate=Decimal("0.07")),
            RatePeriod(start_month=61, end_month=120, annual_rate=Decimal("0.08")),
        ),
        subsidy=SubsidyTerms(
            enabled=True,
            second_coefficient=Decimal("0.05"),
            coefficient=Decimal("0.05"),
            reference_rate=Decimal("0.02"),
        ),
        fees=default_fee_terms(),
    )


def non_zero_synthetic_fee_terms(**updates: object) -> FeeTerms:
    """Build the previous synthetic fee profile with selected replacements."""
    values: dict[str, object] = {
        "annual_fixed_fee": Decimal("600"),
        "monthly_insurance_rate": Decimal("0.0005"),
        "insurance_calculation_method": InsuranceCalculationMethod.TWO_INTERVAL_WEIGHTED,
        "monthly_fixed_fees": Decimal("15"),
        "insurance_end_month": None,
    }
    values.update(updates)
    return FeeTerms.model_validate(values)


def synthetic_overpayment_scenario() -> OverpaymentScenario:
    """Build the shared synthetic recurring-plus-lump-sum scenario."""
    return OverpaymentScenario(
        name="Overpayment",
        recurring_amount=Decimal("1000"),
        recurring_start_month=25,
        lump_sums=(LumpSum(month=25, amount=Decimal("12000")),),
    )
