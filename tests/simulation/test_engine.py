"""Public scenario orchestration tests."""

from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import OverpaymentScenario
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
