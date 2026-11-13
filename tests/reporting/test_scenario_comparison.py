"""Tests for baseline-relative scenario comparisons."""

from decimal import Decimal

from mortgage_simulator.reporting.scenario_comparison import compare, comparison_frame
from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import (
    DepositInvestment,
    OverpaymentScenario,
    SimulationResult,
)
from tests.factories import default_mortgage_terms, synthetic_overpayment_scenario, synthetic_terms


class TestCompare:
    """Tests for baseline-relative scenario comparison."""

    def test_compare_when_results_provided_expect_baseline_deltas(self) -> None:
        """Calculate every scenario difference from the first result."""
        # Arrange
        baseline, overpayment = _results()

        # Act
        report = compare([baseline, overpayment])

        # Assert
        assert report.scenarios[0].cash_outflow_delta == Decimal("0")
        assert report.scenarios[0].mortgage_cost_savings_to_overpayment_ratio is None
        assert report.scenarios[0].mortgage_cost_delta == Decimal("0")
        assert report.scenarios[0].horizon_settlement_delta == Decimal("0")
        assert report.scenarios[0].subsidy_delta == Decimal("0")
        assert report.scenarios[0].net_average_annual_interest_rate_percentage_point_delta == Decimal("0")
        assert report.scenarios[1].scenario_name == "Overpayment"
        assert report.scenarios[1].ending_balance_delta == Decimal("-108000.0000000000000000000000")
        assert report.scenarios[1].cash_outflow_delta == Decimal("85124.1306984055692791376601")
        assert report.scenarios[1].horizon_settlement_delta == Decimal("0")
        assert report.scenarios[1].mortgage_cost_delta == Decimal("-22875.8693015944307208623401")
        assert report.scenarios[1].subsidy_delta == Decimal("-14250.0000000000000000000001")
        assert report.scenarios[1].net_average_annual_interest_rate_percentage_point_delta == Decimal(
            "-0.04698484117877636052779395200"
        )
        applied_overpayment = sum(
            (payment.recurring_overpayment + payment.lump_sum for payment in overpayment.payments),
            start=Decimal("0"),
        )
        expected_ratio = -report.scenarios[1].mortgage_cost_delta / applied_overpayment
        assert applied_overpayment == Decimal("108000")
        assert report.scenarios[1].mortgage_cost_savings_to_overpayment_ratio == expected_ratio

    def test_compare_when_requested_overpayment_is_capped_expect_applied_amount_in_ratio(self) -> None:
        """Divide savings by the overpayment accepted before payoff."""
        # Arrange
        configured_overpayment = Decimal("1000000")
        terms = default_mortgage_terms()
        baseline = simulate(terms, OverpaymentScenario(name="Baseline"))
        overpayment = simulate(
            terms,
            OverpaymentScenario(
                name="Immediate payoff",
                recurring_amount=configured_overpayment,
                recurring_start_month=1,
            ),
        )

        # Act
        report = compare([baseline, overpayment])

        # Assert
        applied_overpayment = sum(
            (payment.recurring_overpayment + payment.lump_sum for payment in overpayment.payments),
            start=Decimal("0"),
        )
        expected_ratio = -report.scenarios[1].mortgage_cost_delta / applied_overpayment
        ratio = report.scenarios[1].mortgage_cost_savings_to_overpayment_ratio
        assert applied_overpayment < configured_overpayment
        assert ratio == expected_ratio

    def test_compare_when_investment_present_expect_net_cost_and_surplus(self) -> None:
        # Arrange
        terms = default_mortgage_terms()
        baseline = simulate(terms, OverpaymentScenario(name="Baseline"))
        investment = DepositInvestment(
            initial_amount=Decimal("10000"), start_month=1, annual_rate=Decimal("0.10"), term_months=12, term_count=1
        )
        result = simulate(terms, OverpaymentScenario(name="Deposit", investment=investment))
        # Act
        comparison = compare([baseline, result]).scenarios[1]
        # Assert
        assert result.investment is not None
        assert comparison.net_investment_earnings == Decimal("810")
        assert comparison.retained_surplus == result.investment.retained_surplus
        assert comparison.net_financing_cost == result.summary.total_mortgage_cost - Decimal("810")
        assert comparison.net_financing_cost_delta == result.net_financing_cost - baseline.net_financing_cost


class TestComparisonFrame:
    """Tests for comparison summary conversion."""

    def test_comparison_frame_when_report_provided_expect_summary_columns(self) -> None:
        """Expose totals and baseline deltas for display."""
        # Arrange
        report = compare(list(_results()))

        # Act
        frame = comparison_frame(report)

        # Assert
        assert frame.height == 2
        assert "total_interest" in frame.columns
        assert "cash_outflow_delta" in frame.columns
        assert {
            "total_mortgage_cost",
            "mortgage_cost_to_original_principal",
            "mortgage_cost_to_principal_repaid",
            "net_average_annual_interest_rate",
            "principal_repaid_before_horizon_settlement",
            "horizon_settlement",
            "mortgage_cost_delta",
            "horizon_settlement_delta",
            "subsidy_delta",
            "net_average_annual_interest_rate_percentage_point_delta",
        }.issubset(frame.columns)
        assert frame[0, "scenario"] == "Baseline"
        assert frame[1, "mortgage_cost_delta"] == Decimal("-22875.8693015944307208623401")
        assert frame[1, "subsidy_delta"] == Decimal("-14250.0000000000000000000001")
        assert frame[1, "net_average_annual_interest_rate_percentage_point_delta"] == Decimal(
            "-0.04698484117877636052779395200"
        )

    def test_comparison_frame_when_subsidy_excluded_expect_columns_omitted(self) -> None:
        """Remove subsidy totals and differences from conventional-mortgage reports."""
        # Arrange
        report = compare(list(_results()))

        # Act
        frame = comparison_frame(report, include_subsidy=False)

        # Assert
        assert "total_subsidy" not in frame.columns
        assert "subsidy_delta" not in frame.columns


def _results() -> tuple[SimulationResult, SimulationResult]:
    terms = synthetic_terms()
    baseline = simulate(terms, OverpaymentScenario(name="Baseline"))
    overpayment = simulate(terms, synthetic_overpayment_scenario())
    return baseline, overpayment
