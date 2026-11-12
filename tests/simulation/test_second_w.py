"""Independent second-period subsidy assumptions."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from mortgage_simulator.settings import SubsidyConfig
from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import OverpaymentScenario
from tests.factories import default_mortgage_terms, default_subsidy_terms


class TestSecondW:
    def test_reset_when_second_w_changes_expect_only_later_subsidies_change(self) -> None:
        """Switch W inclusively at month 61 without changing contractual payments."""
        # Arrange
        original = default_mortgage_terms()
        changed = default_mortgage_terms(subsidy=default_subsidy_terms(second_coefficient=Decimal("0.04")))
        scenario = OverpaymentScenario(name="Baseline")
        # Act
        before = simulate(original, scenario)
        after = simulate(changed, scenario)
        # Assert
        assert before.payments[:60] == after.payments[:60]
        for index in (60, 119):
            old, new = before.payments[index], after.payments[index]
            difference = old.opening_balance * Decimal("0.01") / Decimal("12")
            assert abs(old.subsidy - new.subsidy - difference) < Decimal("1e-20")
            assert old.scheduled_principal == new.scheduled_principal
            assert old.interest == new.interest
            assert new.cash_outflow > old.cash_outflow
        assert after.summary.total_mortgage_cost > before.summary.total_mortgage_cost

    def test_settings_when_unconfigured_expect_forecast_default(self) -> None:
        """Keep the forecast in configuration rather than domain fallbacks."""
        # Arrange / Act
        settings = SubsidyConfig()
        # Assert
        assert settings.coefficient_months_61_120 == Decimal("0.055")

    def test_terms_when_second_w_below_reference_expect_validation_error(self) -> None:
        """Validate the second coefficient even when subsidies are disabled."""
        # Arrange
        subsidy = default_subsidy_terms(enabled=False, second_coefficient=Decimal("0.01"))
        # Act / Assert
        with pytest.raises(ValidationError, match="reference rate"):
            default_mortgage_terms(subsidy=subsidy)
