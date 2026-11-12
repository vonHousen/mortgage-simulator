"""Tests for construction of validated simulation inputs."""

from datetime import date
from decimal import Decimal
from typing import cast

import polars as pl
import pytest

from mortgage_simulator.app.simulation_inputs import (
    MortgageInputs,
    build_request,
    build_terms,
    lump_sum_column_config,
    scenario_column_config,
)
from mortgage_simulator.settings import AppSettings
from mortgage_simulator.simulation.models import InsuranceCalculationMethod, InterestCalculationMethod


def test_build_request_when_lump_sum_scenario_is_unknown_expect_validation_error() -> None:
    """Reject one-off payments that cannot be assigned to a scenario."""
    # Arrange
    scenario_data = pl.DataFrame(
        {
            "name": ["Known"],
            "strategy": ["Fixed overpayment"],
            "recurring_value": [0.0],
            "start_month": [None],
        }
    )
    lump_sum_data = pl.DataFrame({"scenario": ["Unknown"], "month": [37], "amount": [1000.0]})

    # Act / Assert
    with pytest.raises(ValueError, match="unknown scenarios"):
        build_request(_settings_without_dotenv(), build_terms(_valid_inputs()), scenario_data, lump_sum_data)


class TestBuildTerms:
    """Tests for validated mortgage setup conversion."""

    def test_build_terms_when_payment_date_selected_expect_exact_date(self) -> None:
        """Store the selected first payment date as the schedule anchor."""
        # Arrange
        inputs = _valid_inputs()
        inputs["first_payment_date"] = date(2027, 8, 18)

        # Act
        terms = build_terms(inputs)

        # Assert
        assert terms.first_payment_date == date(2027, 8, 18)

    def test_build_terms_when_interest_method_selected_expect_preserved_method(self) -> None:
        """Store the selected interest calculation with the mortgage terms."""
        # Arrange
        inputs = _valid_inputs()
        inputs["interest_calculation_method"] = InterestCalculationMethod.EQUAL_MONTHS

        # Act
        terms = build_terms(inputs)

        # Assert
        assert terms.interest_calculation_method == InterestCalculationMethod.EQUAL_MONTHS

    def test_build_terms_when_insurance_method_selected_expect_preserved_method(self) -> None:
        """Store the selected monthly-insurance calculation with the fee terms."""
        # Arrange
        inputs = _valid_inputs()
        inputs["insurance_calculation_method"] = InsuranceCalculationMethod.MIDPOINT_BALANCE

        # Act
        terms = build_terms(inputs)

        # Assert
        assert terms.fees.insurance_calculation_method == InsuranceCalculationMethod.MIDPOINT_BALANCE

    def test_build_terms_when_horizon_settlement_disabled_expect_preserved_option(self) -> None:
        """Store the selected horizon-settlement behavior with the mortgage terms."""
        # Arrange
        inputs = _valid_inputs()
        inputs["settle_remaining_principal_at_horizon"] = False

        # Act
        terms = build_terms(inputs)

        # Assert
        assert terms.settle_remaining_principal_at_horizon is False

    def test_build_terms_when_subsidy_disabled_expect_preserved_option_and_rates(self) -> None:
        """Store disabled subsidy without discarding its configured rates."""
        # Arrange
        inputs = _valid_inputs()
        inputs["subsidy_enabled"] = False

        # Act
        terms = build_terms(inputs)

        # Assert
        assert terms.subsidy.enabled is False
        assert terms.subsidy.coefficient == Decimal("0.05")
        assert terms.subsidy.reference_rate == Decimal("0.02")

    def test_build_terms_when_fee_end_is_missing_expect_indefinite_fees(self) -> None:
        """Preserve an empty fee-end widget as an indefinite duration."""
        # Arrange
        inputs = _valid_inputs()
        inputs["insurance_end"] = None

        # Act
        terms = build_terms(inputs)

        # Assert
        assert terms.fees.insurance_end_month is None

    def test_build_terms_when_fee_end_is_present_expect_inclusive_month(self) -> None:
        """Preserve an explicit inclusive fee-end month."""
        # Arrange
        inputs = _valid_inputs()
        inputs["insurance_end"] = 60

        # Act
        terms = build_terms(inputs)

        # Assert
        assert terms.fees.insurance_end_month == 60


class TestBuildRequest:
    """Tests for complete scenario request construction."""

    def test_build_request_when_editors_empty_expect_baseline_only(self) -> None:
        """Build a valid request without prepopulated overpayment scenarios."""
        # Arrange
        scenario_data = pl.DataFrame(
            schema={
                "name": pl.String,
                "strategy": pl.String,
                "recurring_value": pl.Float64,
                "start_month": pl.Int64,
            }
        )
        lump_sum_data = pl.DataFrame(schema={"scenario": pl.String, "month": pl.Int64, "amount": pl.Float64})

        # Act
        request = build_request(_settings_without_dotenv(), build_terms(_valid_inputs()), scenario_data, lump_sum_data)

        # Assert
        assert [scenario.name for scenario in request.scenarios] == ["Baseline"]

    def test_build_request_when_fixed_strategy_selected_expect_recurring_amount(self) -> None:
        """Map the editor value to a fixed recurring overpayment."""
        # Arrange
        scenario_data = _scenario_frame("Fixed overpayment", 1500.0, 13)

        # Act
        request = build_request(
            _settings_without_dotenv(), build_terms(_valid_inputs()), scenario_data, _empty_lump_sums()
        )

        # Assert
        scenario = request.scenarios[1]
        assert scenario.recurring_amount == 1500
        assert scenario.cash_outflow_target == 0
        assert scenario.recurring_start_month == 13

    def test_build_request_when_target_strategy_selected_expect_cash_outflow_target(self) -> None:
        """Map the editor value to a constant cash-outflow target."""
        # Arrange
        scenario_data = _scenario_frame("Constant cash outflow", 5000.0, 13)

        # Act
        request = build_request(
            _settings_without_dotenv(), build_terms(_valid_inputs()), scenario_data, _empty_lump_sums()
        )

        # Assert
        scenario = request.scenarios[1]
        assert scenario.recurring_amount == 0
        assert scenario.cash_outflow_target == 5000
        assert scenario.recurring_start_month == 13

    def test_build_request_when_zero_value_has_lump_sum_expect_valid_scenario(self) -> None:
        """Allow a scenario row used only to associate one-off overpayments."""
        # Arrange
        scenario_data = _scenario_frame("Fixed overpayment", 0.0, None)
        lump_sum_data = pl.DataFrame({"scenario": ["Custom"], "month": [13], "amount": [10000.0]})

        # Act
        request = build_request(_settings_without_dotenv(), build_terms(_valid_inputs()), scenario_data, lump_sum_data)

        # Assert
        scenario = request.scenarios[1]
        assert scenario.recurring_amount == 0
        assert scenario.cash_outflow_target == 0
        assert scenario.recurring_start_month is None
        assert scenario.lump_sums[0].amount == 10000

    def test_build_request_when_strategy_is_unknown_expect_validation_error(self) -> None:
        """Reject editor rows with an unsupported recurring strategy."""
        # Arrange
        scenario_data = _scenario_frame("Unknown", 1500.0, 13)

        # Act / Assert
        with pytest.raises(ValueError, match="unsupported overpayment strategy"):
            build_request(_settings_without_dotenv(), build_terms(_valid_inputs()), scenario_data, _empty_lump_sums())


def test_column_config_when_built_expect_human_readable_labels() -> None:
    """Expose readable labels and constrained financial values."""
    # Arrange / Act
    scenario_config = scenario_column_config(120)
    lump_sum_config = lump_sum_column_config(120)

    # Assert
    scenario_name_config = _as_mapping(scenario_config["name"])
    strategy_config = _as_mapping(scenario_config["strategy"])
    recurring_value_config = _as_mapping(scenario_config["recurring_value"])
    start_month_config = _as_mapping(scenario_config["start_month"])
    lump_sum_amount_config = _as_mapping(lump_sum_config["amount"])

    assert scenario_name_config["label"] == "Scenario name"
    assert strategy_config["label"] == "Strategy"
    assert strategy_config["type_config"] == {
        "type": "selectbox",
        "options": ["Fixed overpayment", "Constant cash outflow"],
    }
    assert recurring_value_config["label"] == "Monthly amount or target (PLN)"
    assert start_month_config["label"] == "Starting month"
    assert lump_sum_amount_config["label"] == "Amount (PLN)"
    assert recurring_value_config["type_config"] == {
        "type": "number",
        "min_value": 0.0,
        "max_value": None,
        "format": "%.2f PLN",
        "step": 100.0,
    }
    assert start_month_config["type_config"] == {
        "type": "number",
        "min_value": 1,
        "max_value": 120,
        "format": "%d",
        "step": 1,
    }
    assert lump_sum_amount_config["type_config"] == {
        "type": "number",
        "min_value": 0.01,
        "max_value": None,
        "format": "%.2f PLN",
        "step": 1000.0,
    }


def _valid_inputs() -> MortgageInputs:
    """Return synthetic values accepted by the input widgets."""
    return {
        "first_payment_date": date(2025, 1, 1),
        "interest_calculation_method": InterestCalculationMethod.CALENDAR_DAYS,
        "principal": 100000.0,
        "contractual_term_years": 20,
        "horizon": 120,
        "settle_remaining_principal_at_horizon": True,
        "first_rate": 6.0,
        "second_rate": 9.0,
        "subsidy_enabled": True,
        "second_subsidy_coefficient": 5.0,
        "subsidy_coefficient": 5.0,
        "subsidy_reference": 2.0,
        "annual_fee": 600.0,
        "insurance_rate": 0.05,
        "insurance_calculation_method": InsuranceCalculationMethod.TWO_INTERVAL_WEIGHTED,
        "monthly_fees": 15.0,
        "insurance_end": None,
    }


def _settings_without_dotenv() -> AppSettings:
    return AppSettings(
        _env_file=None  # type: ignore[call-arg]  # Pydantic's generated signature omits runtime settings keywords.
    )


def _scenario_frame(strategy: str, recurring_value: float, start_month: int | None) -> pl.DataFrame:
    """Build one scenario-editor row for request conversion tests."""
    return pl.DataFrame(
        {
            "name": ["Custom"],
            "strategy": [strategy],
            "recurring_value": [recurring_value],
            "start_month": [start_month],
        }
    )


def _empty_lump_sums() -> pl.DataFrame:
    """Build an empty one-off payment editor frame."""
    return pl.DataFrame(schema={"scenario": pl.String, "month": pl.Int64, "amount": pl.Float64})


def _as_mapping(value: object) -> dict[str, object]:
    """Return a Streamlit column configuration as a dictionary."""
    if not isinstance(value, dict):
        raise TypeError("column configuration must be a dictionary")
    return cast(dict[str, object], value)
