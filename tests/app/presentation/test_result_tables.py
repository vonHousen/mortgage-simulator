"""Tests for shared Streamlit table presentation."""

from decimal import Decimal
from typing import cast

import polars as pl
import pytest

from mortgage_simulator.app.presentation.result_tables import (
    COMPARISON_COLUMN_CONFIG,
    SCHEDULE_COLUMN_CONFIG,
    SCHEDULE_COLUMNS,
    comparison_table_frame,
    schedule_columns,
)
from mortgage_simulator.simulation.models import ComparisonReport, ScenarioComparison, SimulationSummary


class TestTableConfiguration:
    """Tests for shared financial table presentation."""

    def test_schedule_config_when_loaded_expect_grouped_pln_and_payment_date(self) -> None:
        """Format money and exact payment dates without converting source columns to text."""
        # Arrange / Act
        money_config = _as_mapping(SCHEDULE_COLUMN_CONFIG["opening_balance"])
        calendar_config = _as_mapping(SCHEDULE_COLUMN_CONFIG["payment_date"])
        principal_config = _as_mapping(SCHEDULE_COLUMN_CONFIG["scheduled_principal"])
        recurring_config = _as_mapping(SCHEDULE_COLUMN_CONFIG["recurring_overpayment"])
        settlement_config = _as_mapping(SCHEDULE_COLUMN_CONFIG["horizon_settlement"])
        interest_config = _as_mapping(SCHEDULE_COLUMN_CONFIG["interest"])
        fee_free_config = _as_mapping(SCHEDULE_COLUMN_CONFIG["cash_outflow_without_fees"])
        outflow_config = _as_mapping(SCHEDULE_COLUMN_CONFIG["cash_outflow"])
        closing_config = _as_mapping(SCHEDULE_COLUMN_CONFIG["closing_balance"])
        money_type_config = _as_mapping(money_config["type_config"])
        calendar_type_config = _as_mapping(calendar_config["type_config"])
        fee_free_type_config = _as_mapping(fee_free_config["type_config"])

        # Assert
        assert money_type_config["format"] == "%,.2f PLN"
        assert calendar_type_config["format"] == "DD/MM/YYYY"
        assert calendar_config["label"] == "Payment date"
        assert SCHEDULE_COLUMNS.index("cash_outflow_without_fees") + 1 == SCHEDULE_COLUMNS.index("cash_outflow")
        assert SCHEDULE_COLUMNS.index("lump_sum") + 1 == SCHEDULE_COLUMNS.index("horizon_settlement")
        assert money_config["label"] == "Opening balance"
        assert principal_config["label"] == "Principal"
        assert recurring_config["label"] == "Recur. overpayment"
        assert settlement_config["label"] == "Horizon settlement"
        assert interest_config["label"] == "Gross mortgage interest"
        assert fee_free_config["label"] == "Outflow excl. fees"
        assert outflow_config["label"] == "Outflow"
        assert closing_config["label"] == "Closing balance"
        assert fee_free_type_config["format"] == "%,.2f PLN"

    @pytest.mark.parametrize(
        ("split_fees", "split_overpayments", "expected_columns"),
        [
            (
                False,
                False,
                [
                    "month",
                    "payment_date",
                    "opening_balance",
                    "scheduled_principal",
                    "overpayments",
                    "interest",
                    "subsidy",
                    "fees",
                    "cash_outflow_without_fees",
                    "cash_outflow",
                    "closing_balance",
                ],
            ),
            (
                False,
                True,
                [
                    "month",
                    "payment_date",
                    "opening_balance",
                    "scheduled_principal",
                    "recurring_overpayment",
                    "lump_sum",
                    "horizon_settlement",
                    "interest",
                    "subsidy",
                    "fees",
                    "cash_outflow_without_fees",
                    "cash_outflow",
                    "closing_balance",
                ],
            ),
            (
                True,
                False,
                [
                    "month",
                    "payment_date",
                    "opening_balance",
                    "scheduled_principal",
                    "overpayments",
                    "interest",
                    "subsidy",
                    "monthly_insurance",
                    "monthly_fixed_fees",
                    "annual_fixed_fee",
                    "cash_outflow_without_fees",
                    "cash_outflow",
                    "closing_balance",
                ],
            ),
            (
                True,
                True,
                [
                    "month",
                    "payment_date",
                    "opening_balance",
                    "scheduled_principal",
                    "recurring_overpayment",
                    "lump_sum",
                    "horizon_settlement",
                    "interest",
                    "subsidy",
                    "monthly_insurance",
                    "monthly_fixed_fees",
                    "annual_fixed_fee",
                    "cash_outflow_without_fees",
                    "cash_outflow",
                    "closing_balance",
                ],
            ),
        ],
    )
    def test_schedule_columns_when_toggles_selected_expect_exact_order(
        self,
        split_fees: bool,
        split_overpayments: bool,
        expected_columns: list[str],
    ) -> None:
        """Select aggregate or split payment components in their display order."""
        # Arrange / Act
        columns = schedule_columns(
            split_fees=split_fees,
            split_overpayments=split_overpayments,
        )

        # Assert
        assert columns == expected_columns

    def test_schedule_config_when_loaded_expect_split_component_labels_and_formats(self) -> None:
        """Format aggregate and split payment components as Polish currency."""
        # Arrange / Act
        overpayments = _as_mapping(SCHEDULE_COLUMN_CONFIG["overpayments"])
        monthly_insurance = _as_mapping(SCHEDULE_COLUMN_CONFIG["monthly_insurance"])
        monthly_fixed_fees = _as_mapping(SCHEDULE_COLUMN_CONFIG["monthly_fixed_fees"])
        annual_fixed_fee = _as_mapping(SCHEDULE_COLUMN_CONFIG["annual_fixed_fee"])

        # Assert
        assert overpayments["label"] == "Overpayments"
        assert monthly_insurance["label"] == "Monthly insurance"
        assert monthly_fixed_fees["label"] == "Monthly fixed fees"
        assert annual_fixed_fee["label"] == "Annual fixed fee"
        assert _as_mapping(overpayments["type_config"])["format"] == "%,.2f PLN"
        assert _as_mapping(monthly_insurance["type_config"])["format"] == "%,.2f PLN"
        assert _as_mapping(monthly_fixed_fees["type_config"])["format"] == "%,.2f PLN"
        assert _as_mapping(annual_fixed_fee["type_config"])["format"] == "%,.2f PLN"

    def test_schedule_columns_when_subsidy_excluded_expect_column_omitted(self) -> None:
        """Remove the subsidy column from a conventional-mortgage schedule."""
        # Arrange / Act
        columns = schedule_columns(split_fees=False, split_overpayments=False, include_subsidy=False)

        # Assert
        assert "subsidy" not in columns

    def test_comparison_config_when_loaded_expect_new_difference_labels_and_units(self) -> None:
        """Label new Baseline differences and format the rate in percentage points."""
        # Arrange / Act
        mortgage_cost = _as_mapping(COMPARISON_COLUMN_CONFIG["mortgage_cost_delta"])
        subsidy = _as_mapping(COMPARISON_COLUMN_CONFIG["subsidy_delta"])
        rate = _as_mapping(COMPARISON_COLUMN_CONFIG["net_average_annual_interest_rate_percentage_point_delta"])
        rate_type_config = _as_mapping(rate["type_config"])

        # Assert
        assert mortgage_cost["label"] == "Total mortgage cost difference"
        assert subsidy["label"] == "Subsidy difference"
        assert rate["label"] == "Net average annual interest rate difference"
        assert rate_type_config["format"] == "%.2f p.p."


class TestComparisonTableFrame:
    """Tests for the transposed scenario comparison projection."""

    def test_when_ending_balance_visible_expect_formatted_metrics_as_rows(self) -> None:
        """Transpose scenarios while preserving each metric's display unit."""
        # Arrange
        report = _comparison_report()

        # Act
        frame = comparison_table_frame(report, show_ending_balance=True)

        # Assert
        assert frame.columns == ["Metric", "Baseline", "Overpayment"]
        assert _metric_value(frame, "Cost / original principal", "Baseline") == "23.00%"
        assert _metric_value(frame, "Net average annual interest rate", "Baseline") == "2.00%"
        assert _metric_value(frame, "Net average annual interest rate difference", "Overpayment") == "-0.05 p.p."
        assert _metric_value(frame, "Overpayment savings rate", "Baseline") == "N/A"
        assert _metric_value(frame, "Overpayment savings rate", "Overpayment") == "12.89%"
        assert _metric_value(frame, "Total mortgage cost", "Baseline") == "30,000.00 PLN"
        assert _metric_value(frame, "Payoff month", "Baseline") == "After horizon"
        metric_labels = frame["Metric"].to_list()
        assert (
            metric_labels.index("Overpayment savings rate") == metric_labels.index("Total mortgage cost difference") + 1
        )
        assert {"Ending balance", "Ending balance difference"}.issubset(set(frame["Metric"]))

    def test_when_ending_balance_hidden_expect_balance_metrics_omitted(self) -> None:
        """Omit balance rows that always converge under horizon settlement."""
        # Arrange
        report = _comparison_report()

        # Act
        frame = comparison_table_frame(report, show_ending_balance=False)

        # Assert
        assert "Ending balance" not in frame["Metric"].to_list()
        assert "Ending balance difference" not in frame["Metric"].to_list()
        assert _metric_value(frame, "Overpayment savings rate", "Overpayment") == "12.89%"

    def test_when_subsidy_excluded_expect_rows_omitted_and_rate_labels_adapted(self) -> None:
        """Present conventional-mortgage comparisons without subsidy terminology."""
        # Arrange
        report = _comparison_report()

        # Act
        frame = comparison_table_frame(report, show_ending_balance=True, include_subsidy=False)

        # Assert
        labels = frame["Metric"].to_list()
        assert "Subsidy received" not in labels
        assert "Subsidy difference" not in labels
        assert "Net average annual interest rate" not in labels
        assert "Net average annual interest rate difference" not in labels
        assert "Average annual interest rate" in labels
        assert "Average annual interest rate difference" in labels


def _as_mapping(value: object) -> dict[str, object]:
    """Return a Streamlit column configuration as a dictionary.

    Args:
        value: Streamlit column configuration object.

    Returns:
        Configuration represented as a dictionary.

    Raises:
        TypeError: If the supplied value is not dictionary-backed.
    """
    if not isinstance(value, dict):
        raise TypeError("column configuration must be a dictionary")
    return cast(dict[str, object], value)


def _comparison_report() -> ComparisonReport:
    """Create two scenarios with hand-selected values for display assertions."""
    baseline_summary = _summary()
    overpayment_summary = _summary(
        mortgage_cost_to_original_principal=Decimal("0.22"),
        mortgage_cost_to_principal_repaid=Decimal("0.22"),
        net_average_annual_interest_rate=Decimal("0.0195"),
        payoff_month=96,
    )
    return ComparisonReport(
        scenarios=(
            _comparison("Baseline", baseline_summary),
            _comparison(
                "Overpayment",
                overpayment_summary,
                net_average_annual_interest_rate_percentage_point_delta=Decimal("-0.05"),
                mortgage_cost_savings_to_overpayment_ratio=Decimal("0.128855"),
            ),
        )
    )


def _summary(
    *,
    mortgage_cost_to_original_principal: Decimal = Decimal("0.23"),
    mortgage_cost_to_principal_repaid: Decimal = Decimal("0.23"),
    net_average_annual_interest_rate: Decimal = Decimal("0.02"),
    payoff_month: int | None = None,
) -> SimulationSummary:
    """Create a summary with representative values for table projection tests."""
    return SimulationSummary(
        total_principal=Decimal("100000"),
        principal_repaid_before_horizon_settlement=Decimal("80000"),
        horizon_settlement=Decimal("20000"),
        total_interest=Decimal("40000"),
        total_subsidy=Decimal("15000"),
        total_fees=Decimal("5000"),
        total_cash_outflow=Decimal("130000"),
        total_mortgage_cost=Decimal("30000"),
        mortgage_cost_to_original_principal=mortgage_cost_to_original_principal,
        mortgage_cost_to_principal_repaid=mortgage_cost_to_principal_repaid,
        net_average_annual_interest_rate=net_average_annual_interest_rate,
        ending_balance=Decimal("20000"),
        payoff_month=payoff_month,
    )


def _comparison(
    scenario_name: str,
    summary: SimulationSummary,
    *,
    net_average_annual_interest_rate_percentage_point_delta: Decimal = Decimal("0"),
    mortgage_cost_savings_to_overpayment_ratio: Decimal | None = None,
) -> ScenarioComparison:
    """Create a comparison with representative Baseline-relative differences."""
    return ScenarioComparison(
        scenario_name=scenario_name,
        summary=summary,
        cash_outflow_delta=Decimal("0"),
        interest_delta=Decimal("0"),
        ending_balance_delta=Decimal("0"),
        mortgage_cost_delta=Decimal("0"),
        horizon_settlement_delta=Decimal("0"),
        subsidy_delta=Decimal("0"),
        net_average_annual_interest_rate_percentage_point_delta=(
            net_average_annual_interest_rate_percentage_point_delta
        ),
        mortgage_cost_savings_to_overpayment_ratio=mortgage_cost_savings_to_overpayment_ratio,
    )


def _metric_value(frame: pl.DataFrame, metric: str, scenario: str) -> str:
    """Return one scenario value for a named comparison metric."""
    value = frame.filter(pl.col("Metric") == metric)[0, scenario]
    if not isinstance(value, str):
        raise TypeError("comparison table values must be formatted strings")
    return value
