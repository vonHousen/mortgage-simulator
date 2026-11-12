"""Tests for financial result presentation helpers."""

from decimal import Decimal

from mortgage_simulator.app.presentation.result_metrics import (
    additional_cash_paid,
    balance_reduction,
    interest_saved,
    payoff_label,
    percentage,
    percentage_or_na,
    percentage_points,
    pln,
    settlement_reduction,
    total_mortgage_cost_saved,
)
from mortgage_simulator.simulation.models import ScenarioComparison, SimulationSummary


class TestResultFormatting:
    """Tests for readable financial result presentation."""

    def test_pln_when_large_value_expect_complete_currency_text(self) -> None:
        """Format values without metric truncation."""
        # Arrange
        value = Decimal("329800.4167")

        # Act
        formatted = pln(value)

        # Assert
        assert formatted == "329,800.42 PLN"

    def test_payoff_label_when_month_exists_expect_month_number(self) -> None:
        """Describe payoff within the analysis horizon."""
        # Arrange / Act / Assert
        assert payoff_label(84) == "Month 84"

    def test_payoff_label_when_month_is_missing_expect_horizon_status(self) -> None:
        """Describe a balance remaining after the horizon."""
        # Arrange / Act / Assert
        assert payoff_label(None) == "After horizon"

    def test_percentage_when_ratio_provided_expect_two_decimal_percent(self) -> None:
        """Format decimal ratios as complete percentages."""
        # Arrange / Act / Assert
        assert percentage(Decimal("0.185694")) == "18.57%"

    def test_percentage_or_na_when_ratio_provided_expect_two_decimal_percent(self) -> None:
        """Format an available optional ratio as a percentage."""
        # Arrange / Act / Assert
        assert percentage_or_na(Decimal("0.128855")) == "12.89%"

    def test_percentage_or_na_when_ratio_missing_expect_not_available(self) -> None:
        """Describe a ratio with no applied overpayment as unavailable."""
        # Arrange / Act / Assert
        assert percentage_or_na(None) == "N/A"

    def test_percentage_points_when_difference_provided_expect_percentage_point_unit(self) -> None:
        """Format an already scaled percentage-point difference."""
        # Arrange / Act / Assert
        assert percentage_points(Decimal("-0.047103")) == "-0.05 p.p."


class TestDecisionDeltas:
    """Tests for baseline-relative decision metrics."""

    def test_interest_saved_when_interest_delta_is_negative_expect_positive_saving(self) -> None:
        """Present a cost reduction as a positive saving."""
        # Arrange
        selected = _scenario_comparison(interest_delta=Decimal("-52323.75"))

        # Act / Assert
        assert interest_saved(selected) == Decimal("52323.75")

    def test_mortgage_cost_saved_when_cost_delta_is_negative_expect_positive_saving(self) -> None:
        """Present a total mortgage cost reduction as a positive saving."""
        # Arrange
        selected = _scenario_comparison(mortgage_cost_delta=Decimal("-20825.25"))

        # Act / Assert
        assert total_mortgage_cost_saved(selected) == Decimal("20825.25")

    def test_balance_reduction_when_balance_delta_is_negative_expect_positive_reduction(self) -> None:
        """Present a lower ending balance as a positive reduction."""
        # Arrange
        selected = _scenario_comparison(ending_balance_delta=Decimal("-162000"))

        # Act / Assert
        assert balance_reduction(selected) == Decimal("162000")

    def test_additional_cash_when_outflow_delta_is_positive_expect_positive_amount(self) -> None:
        """Present extra cash paid relative to Baseline."""
        # Arrange
        selected = _scenario_comparison(cash_outflow_delta=Decimal("143616"))

        # Act / Assert
        assert additional_cash_paid(selected) == Decimal("143616")

    def test_settlement_reduction_when_delta_is_negative_expect_positive_reduction(self) -> None:
        """Present a smaller terminal settlement as a positive reduction."""
        # Arrange
        selected = _scenario_comparison(horizon_settlement_delta=Decimal("-162000"))

        # Act / Assert
        assert settlement_reduction(selected) == Decimal("162000")


def _scenario_comparison(
    *,
    cash_outflow_delta: Decimal = Decimal("0"),
    interest_delta: Decimal = Decimal("0"),
    ending_balance_delta: Decimal = Decimal("0"),
    mortgage_cost_delta: Decimal = Decimal("0"),
    horizon_settlement_delta: Decimal = Decimal("0"),
    subsidy_delta: Decimal = Decimal("0"),
    net_average_annual_interest_rate_percentage_point_delta: Decimal = Decimal("0"),
    mortgage_cost_savings_to_overpayment_ratio: Decimal | None = None,
) -> ScenarioComparison:
    summary = SimulationSummary(
        total_principal=Decimal("362000"),
        principal_repaid_before_horizon_settlement=Decimal("362000"),
        horizon_settlement=Decimal("0"),
        total_interest=Decimal("309407.5"),
        total_subsidy=Decimal("217043.8833"),
        total_fees=Decimal("19052.8"),
        total_cash_outflow=Decimal("473416.4167"),
        total_mortgage_cost=Decimal("111416.4167"),
        mortgage_cost_to_original_principal=Decimal("0.1856940277"),
        mortgage_cost_to_principal_repaid=Decimal("0.3077801564"),
        net_average_annual_interest_rate=Decimal("0.0185"),
        ending_balance=Decimal("238000"),
        payoff_month=None,
    )
    return ScenarioComparison(
        scenario_name="Overpayment",
        summary=summary,
        cash_outflow_delta=cash_outflow_delta,
        interest_delta=interest_delta,
        ending_balance_delta=ending_balance_delta,
        mortgage_cost_delta=mortgage_cost_delta,
        horizon_settlement_delta=horizon_settlement_delta,
        subsidy_delta=subsidy_delta,
        net_average_annual_interest_rate_percentage_point_delta=(
            net_average_annual_interest_rate_percentage_point_delta
        ),
        mortgage_cost_savings_to_overpayment_ratio=mortgage_cost_savings_to_overpayment_ratio,
    )
