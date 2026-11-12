"""Tests for monthly-insurance calculation strategies."""

from decimal import Decimal
from importlib import import_module

import mortgage_simulator.simulation.models as models


class TestCalculateMonthlyInsurance:
    """Tests for the supported insured-balance strategies."""

    def test_calculate_when_opening_balance_selected_expect_current_balance_charge(self) -> None:
        """Apply the monthly rate to the current opening balance."""
        # Arrange
        calculator = import_module("mortgage_simulator.simulation.monthly_insurance").calculate_monthly_insurance
        current_balance = Decimal("9900")
        rate = Decimal("0.0005")

        # Act
        result = calculator(
            method=models.InsuranceCalculationMethod.OPENING_BALANCE,
            monthly_rate=rate,
            previous_opening_balance=Decimal("10000"),
            opening_balance=current_balance,
            previous_period_days=29,
            current_period_days=31,
        )

        # Assert
        assert result == current_balance * rate

    def test_calculate_when_midpoint_selected_expect_average_balance_charge(self) -> None:
        """Apply the monthly rate to the arithmetic mean of adjacent balances."""
        # Arrange
        calculator = import_module("mortgage_simulator.simulation.monthly_insurance").calculate_monthly_insurance
        previous_balance = Decimal("10000")
        current_balance = Decimal("9900")
        rate = Decimal("0.0005")

        # Act
        result = calculator(
            method=models.InsuranceCalculationMethod.MIDPOINT_BALANCE,
            monthly_rate=rate,
            previous_opening_balance=previous_balance,
            opening_balance=current_balance,
            previous_period_days=29,
            current_period_days=31,
        )

        # Assert
        assert result == (previous_balance + current_balance) / Decimal("2") * rate

    def test_calculate_when_weighted_selected_expect_opposite_interval_weights(self) -> None:
        """Weight each adjacent balance by the opposite payment interval."""
        # Arrange
        calculator = import_module("mortgage_simulator.simulation.monthly_insurance").calculate_monthly_insurance
        previous_balance = Decimal("10000")
        current_balance = Decimal("9900")
        previous_days = 29
        current_days = 31
        rate = Decimal("0.0005")

        # Act
        result = calculator(
            method=models.InsuranceCalculationMethod.TWO_INTERVAL_WEIGHTED,
            monthly_rate=rate,
            previous_opening_balance=previous_balance,
            opening_balance=current_balance,
            previous_period_days=previous_days,
            current_period_days=current_days,
        )

        # Assert
        expected_balance = (
            previous_balance * Decimal(current_days) + current_balance * Decimal(previous_days)
        ) / Decimal(previous_days + current_days)
        assert result == expected_balance * rate

    def test_calculate_when_balances_match_expect_all_methods_to_match(self) -> None:
        """Produce the same first-month charge when adjacent balances match."""
        # Arrange
        calculator = import_module("mortgage_simulator.simulation.monthly_insurance").calculate_monthly_insurance
        balance = Decimal("10000")
        rate = Decimal("0.0005")

        # Act
        results = {
            calculator(
                method=method,
                monthly_rate=rate,
                previous_opening_balance=balance,
                opening_balance=balance,
                previous_period_days=29,
                current_period_days=31,
            )
            for method in models.InsuranceCalculationMethod
        }

        # Assert
        assert results == {Decimal("5")}
