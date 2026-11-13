"""Public scenario orchestration tests."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import DepositInvestment, LumpSum, OverpaymentScenario
from mortgage_simulator.simulation.mortgage.schedule import calculate_schedule
from tests.factories import default_mortgage_terms, synthetic_overpayment_scenario


class TestSimulate:
    """The public entry point shares the mortgage calculator."""

    def test_when_no_investment_expect_identical_schedule(self) -> None:
        # Arrange
        terms = default_mortgage_terms()
        scenarios = (OverpaymentScenario(name="Baseline"), synthetic_overpayment_scenario())
        for scenario in scenarios:
            # Act
            actual = simulate(terms, scenario)
            expected = calculate_schedule(terms, scenario)
            # Assert
            assert actual == expected

    @pytest.mark.parametrize("with_investment", [False, True])
    def test_when_balloon_exceeds_horizon_expect_validation_error(self, with_investment: bool) -> None:
        # Arrange
        terms = default_mortgage_terms()
        investment = (
            DepositInvestment(
                initial_amount=Decimal("1000"), start_month=1, annual_rate=Decimal("0.05"), term_months=3, term_count=1
            )
            if with_investment
            else None
        )
        scenario = OverpaymentScenario(
            name="Invalid",
            investment=investment,
            lump_sums=(LumpSum(month=terms.analysis_horizon_months + 1, amount=Decimal("1000")),),
        )
        # Act / Assert
        with pytest.raises(ValidationError, match="lump-sum month must be within the analysis horizon"):
            simulate(terms, scenario)
