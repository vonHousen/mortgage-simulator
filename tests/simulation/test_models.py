"""Tests for validated mortgage simulation models."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

import mortgage_simulator.simulation.models as models
from mortgage_simulator.simulation.models import (
    FeeTerms,
    LumpSum,
    MortgageTerms,
    OverpaymentScenario,
    SimulationRequest,
    SubsidyTerms,
)
from tests.factories import default_fee_terms, default_mortgage_terms, default_subsidy_terms


class TestMortgageTerms:
    """Tests for mortgage-term validation."""

    @pytest.mark.parametrize("model", [SubsidyTerms, FeeTerms, MortgageTerms, SimulationRequest])
    def test_model_when_application_values_are_omitted_expect_validation_error(
        self,
        model: type[SubsidyTerms] | type[FeeTerms] | type[MortgageTerms] | type[SimulationRequest],
    ) -> None:
        """Keep application fallback values outside domain model construction."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="Field required"):
            model.model_validate({})

    def test_terms_when_created_with_complete_values_expect_preserved_values(self) -> None:
        """Preserve complete validated mortgage assumptions."""
        # Arrange / Act
        terms = default_mortgage_terms()

        # Assert
        assert terms.principal == Decimal("500000")
        assert terms.first_payment_date == date(2024, 1, 1)
        assert terms.fees.insurance_end_month is None
        assert terms.contractual_term_months == 360
        assert terms.analysis_horizon_months == 120
        assert terms.settle_remaining_principal_at_horizon is True
        assert terms.rate_periods[0].annual_rate == Decimal("0.07")
        assert terms.rate_periods[1].annual_rate == Decimal("0.08")
        assert terms.subsidy.enabled is True
        assert terms.subsidy.coefficient == Decimal("0.05")
        assert terms.subsidy.reference_rate == Decimal("0.02")
        assert terms.fees.annual_fixed_fee == Decimal("0")
        assert terms.fees.monthly_insurance_rate == Decimal("0")
        assert terms.fees.monthly_fixed_fees == Decimal("0")
        assert terms.model_dump()["interest_calculation_method"] == "calendar_days"
        assert terms.fees.model_dump()["insurance_calculation_method"] == "two_interval_weighted"

    def test_fee_terms_when_insurance_method_selected_expect_serialized_value(self) -> None:
        """Preserve the selected monthly-insurance calculation method."""
        # Arrange
        method = models.InsuranceCalculationMethod.MIDPOINT_BALANCE

        # Act
        terms = default_fee_terms(insurance_calculation_method=method)

        # Assert
        assert terms.insurance_calculation_method == method
        assert terms.model_dump()["insurance_calculation_method"] == "midpoint_balance"

    def test_terms_when_horizon_exceeds_v1_expect_validation_error(self) -> None:
        """Reject simulation beyond the workbook-derived V1 horizon."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="less than or equal to 120"):
            default_mortgage_terms(analysis_horizon_months=121)

    def test_terms_when_subsidy_is_negative_expect_validation_error(self) -> None:
        """Reject a coefficient below the subsidized reference rate."""
        # Arrange
        subsidy = default_subsidy_terms(
            coefficient=Decimal("0.01"),
            second_coefficient=Decimal("0.01"),
            reference_rate=Decimal("0.02"),
        )

        # Act / Assert
        with pytest.raises(ValidationError, match="coefficient"):
            default_mortgage_terms(subsidy=subsidy)

    def test_terms_when_payment_day_exceeds_28_expect_validation_error(self) -> None:
        """Reject payment dates that cannot recur in every calendar month."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="day 1 through 28"):
            default_mortgage_terms(first_payment_date=date(2024, 2, 29))

    def test_terms_when_preceding_payment_boundary_exceeds_calendar_expect_validation_error(self) -> None:
        """Reject a first payment without a representable preceding monthly boundary."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="preceding payment boundary"):
            default_mortgage_terms(first_payment_date=date(1, 1, 15))

    def test_terms_when_horizon_exceeds_calendar_expect_validation_error(self) -> None:
        """Reject a start and horizon that exceed Python's calendar range."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="calendar range"):
            default_mortgage_terms(first_payment_date=date(9999, 12, 15))

    def test_fee_terms_when_end_month_is_negative_expect_validation_error(self) -> None:
        """Reject a negative inclusive fee-end month."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            default_fee_terms(insurance_end_month=-1)


class TestOverpaymentScenario:
    """Tests for overpayment scenario validation."""

    def test_scenario_when_cash_outflow_target_has_start_expect_preserved_value(self) -> None:
        """Accept a positive cash-outflow target with its inclusive start month."""
        # Arrange / Act
        scenario = OverpaymentScenario(
            name="Constant outflow",
            cash_outflow_target=Decimal("5000"),
            recurring_start_month=13,
        )

        # Assert
        assert scenario.cash_outflow_target == Decimal("5000")
        assert scenario.recurring_start_month == 13

    def test_scenario_when_recurring_amount_has_no_start_expect_validation_error(self) -> None:
        """Require a start month for a positive recurring overpayment."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="start month"):
            OverpaymentScenario(name="Recurring", recurring_amount=Decimal("1500"))

    def test_scenario_when_cash_outflow_target_has_no_start_expect_validation_error(self) -> None:
        """Require a start month for a positive cash-outflow target."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="start month"):
            OverpaymentScenario(name="Constant outflow", cash_outflow_target=Decimal("5000"))

    def test_scenario_when_both_recurring_modes_are_positive_expect_validation_error(self) -> None:
        """Reject conflicting fixed-overpayment and cash-outflow strategies."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="cannot both be positive"):
            OverpaymentScenario(
                name="Conflicting",
                recurring_amount=Decimal("1500"),
                cash_outflow_target=Decimal("5000"),
                recurring_start_month=1,
            )

    def test_scenario_when_start_has_no_positive_recurring_value_expect_validation_error(self) -> None:
        """Reject a start month without either recurring strategy value."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="positive amount or cash-outflow target"):
            OverpaymentScenario(name="Missing value", recurring_start_month=1)

    def test_scenario_when_name_is_whitespace_expect_validation_error(self) -> None:
        """Treat a whitespace-only scenario name as empty input."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="at least 1 character"):
            OverpaymentScenario(name="   ")

    def test_scenario_when_lump_sums_share_month_expect_preserved_order(self) -> None:
        """Allow multiple lump sums in one month and preserve input order."""
        # Arrange
        first = LumpSum(month=37, amount=Decimal("1000"))
        second = LumpSum(month=37, amount=Decimal("2000"))

        # Act
        scenario = OverpaymentScenario(name="Two lumps", lump_sums=(first, second))

        # Assert
        assert scenario.lump_sums == (first, second)


class TestSimulationRequest:
    """Tests for validation spanning all scenarios in a run."""

    def test_request_when_scenario_names_repeat_expect_validation_error(self) -> None:
        """Reject duplicate scenario names before calculation."""
        # Arrange
        first = OverpaymentScenario(name="Same")
        second = OverpaymentScenario(name="Same")

        # Act / Assert
        with pytest.raises(ValidationError, match="unique"):
            SimulationRequest(terms=default_mortgage_terms(), scenarios=(first, second))

    def test_request_when_lump_sum_exceeds_horizon_expect_validation_error(self) -> None:
        """Reject overpayments outside the configured analysis horizon."""
        # Arrange
        scenario = OverpaymentScenario(
            name="Late",
            lump_sums=(LumpSum(month=121, amount=Decimal("1000")),),
        )

        # Act / Assert
        with pytest.raises(ValidationError, match="horizon"):
            SimulationRequest(terms=default_mortgage_terms(), scenarios=(scenario,))
