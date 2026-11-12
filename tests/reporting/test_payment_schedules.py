"""Tests for payment-schedule projections and CSV serialization."""

from decimal import Decimal

import polars as pl

from mortgage_simulator.reporting.payment_schedules import schedule_csv, schedule_frame
from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import (
    LumpSum,
    OverpaymentScenario,
    SimulationResult,
)
from tests.factories import default_mortgage_terms, synthetic_overpayment_scenario, synthetic_terms


class TestScheduleFrame:
    """Tests for typed-result conversion to Polars."""

    def test_schedule_frame_when_results_provided_expect_long_scenario_table(self) -> None:
        """Create one row per scenario payment with all monthly components."""
        # Arrange
        results = _results()

        # Act
        frame = schedule_frame(results)

        # Assert
        assert isinstance(frame, pl.DataFrame)
        assert frame.height == 240
        assert frame.columns == [
            "scenario",
            "month",
            "payment_date",
            "opening_balance",
            "scheduled_principal",
            "overpayments",
            "recurring_overpayment",
            "lump_sum",
            "horizon_settlement",
            "interest",
            "subsidy",
            "monthly_insurance",
            "monthly_fixed_fees",
            "annual_fixed_fee",
            "fees",
            "cash_outflow_without_fees",
            "cash_outflow",
            "closing_balance",
        ]
        assert frame[0, "scenario"] == "Baseline"
        assert frame.schema["payment_date"] == pl.Date
        assert frame[0, "payment_date"].isoformat() == "2024-01-01"
        assert frame[0, "overpayments"] == Decimal("0")
        assert frame[0, "monthly_insurance"] == Decimal("0")
        assert frame[0, "monthly_fixed_fees"] == Decimal("0")
        assert frame[0, "annual_fixed_fee"] == Decimal("0")
        assert frame[0, "fees"] == Decimal("0")
        assert frame[144, "overpayments"] == Decimal("13000")
        assert frame[0, "cash_outflow"] == frame[0, "cash_outflow_without_fees"] + frame[0, "fees"]

    def test_schedule_csv_when_results_provided_expect_combined_csv(self) -> None:
        """Serialize all scenario rows with stable component columns."""
        # Arrange
        results = _results()

        # Act
        csv_text = schedule_csv(results)

        # Assert
        assert csv_text.splitlines()[0] == (
            "scenario,month,payment_date,opening_balance,scheduled_principal,overpayments,"
            "recurring_overpayment,lump_sum,horizon_settlement,interest,subsidy,monthly_insurance,"
            "monthly_fixed_fees,annual_fixed_fee,fees,cash_outflow_without_fees,cash_outflow,closing_balance"
        )
        assert "Baseline,1,2024-01-01,500000" in csv_text
        assert "Overpayment,120" in csv_text

    def test_schedule_frame_when_subsidy_excluded_expect_column_omitted(self) -> None:
        """Remove subsidy from a conventional-mortgage reporting schema."""
        # Arrange
        results = _results()

        # Act
        frame = schedule_frame(results, include_subsidy=False)

        # Assert
        assert "subsidy" not in frame.columns

    def test_schedule_csv_when_subsidy_excluded_expect_column_omitted(self) -> None:
        """Remove subsidy from conventional-mortgage CSV exports."""
        # Arrange
        results = _results()

        # Act
        header = schedule_csv(results, include_subsidy=False).splitlines()[0]

        # Assert
        assert "subsidy" not in header.split(",")

    def test_schedule_frame_when_overpayments_are_applied_expect_all_components_aggregated(self) -> None:
        """Sum recurring, lump-sum, and horizon-settlement overpayments by month."""
        # Arrange
        terms = default_mortgage_terms(
            principal=Decimal("1000"),
            contractual_term_months=4,
            analysis_horizon_months=2,
        )
        scenario = OverpaymentScenario(
            name="Components",
            recurring_amount=Decimal("100"),
            recurring_start_month=1,
            lump_sums=(LumpSum(month=1, amount=Decimal("200")),),
        )
        result = simulate(terms, scenario)

        # Act
        frame = schedule_frame([result])

        # Assert
        assert frame[0, "overpayments"] == Decimal("300")
        assert frame[1, "overpayments"] == Decimal("200")


def _results() -> tuple[SimulationResult, SimulationResult]:
    terms = synthetic_terms()
    baseline = simulate(terms, OverpaymentScenario(name="Baseline"))
    overpayment = simulate(terms, synthetic_overpayment_scenario())
    return baseline, overpayment
