"""Tests for strict local regression manifest loading."""

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from mortgage_simulator.reference_data.regression_manifest_loader import (
    load_excel_regression_manifest,
    load_insurance_regression_manifest,
)
from mortgage_simulator.simulation.models import InsuranceCalculationMethod, InterestCalculationMethod


def _synthetic_excel_manifest() -> dict[str, object]:
    return {
        "artifact": {
            "sha256": "a" * 64,
            "sheets": ["Synthetic baseline", "Synthetic scenario"],
        },
        "terms": {
            "first_payment_date": "2025-01-01",
            "interest_calculation_method": "equal_months",
            "principal": "100000",
            "contractual_term_months": 240,
            "analysis_horizon_months": 120,
            "settle_remaining_principal_at_horizon": False,
            "rate_periods": [
                {"start_month": 1, "end_month": 60, "annual_rate": "0.06"},
                {"start_month": 61, "end_month": 120, "annual_rate": "0.09"},
            ],
            "subsidy": {"enabled": True, "coefficient": "0.05", "reference_rate": "0.02"},
            "fees": {
                "annual_fixed_fee": "600",
                "monthly_insurance_rate": "0.0005",
                "insurance_calculation_method": "opening_balance",
                "monthly_fixed_fees": "15",
                "insurance_end_month": 60,
            },
        },
        "tolerances": {"monthly": "0.01", "summary": "0.05"},
        "representative_months": [1, 60, 61, 120],
        "scenarios": [
            {
                "sheet_name": "Synthetic baseline",
                "summary_row": 130,
                "scenario": {
                    "name": "Baseline",
                    "recurring_amount": "0",
                    "cash_outflow_target": "0",
                    "recurring_start_month": None,
                    "lump_sums": [],
                },
            }
        ],
        "worksheet_mapping": {
            "payment_row_offset": 5,
            "principal_column": 2,
            "interest_column": 3,
            "subsidy_column": 5,
            "fees_column": 7,
            "cash_outflow_column": 8,
            "closing_balance_column": 10,
            "ending_balance_cell": "J125",
        },
        "excluded_comparisons": [{"scenario_name": "Synthetic scenario", "month": 120, "comparison": "monthly"}],
        "accepted_capped_payoff_difference": {
            "scenario_name": "Synthetic scenario",
            "engine_ending_balance": "0",
            "engine_total_principal": "100000",
            "worksheet_ending_balance": "-100.25",
        },
    }


class TestLoadExcelRegressionManifest:
    """Verify successful parsing and strict validation of Excel manifests."""

    def test_manifest_when_valid_expect_typed_frozen_values(self, tmp_path: Path) -> None:
        """Parse ISO dates, decimal strings, enums, and domain terms."""
        # Arrange
        manifest_path = tmp_path / "excel.json"
        manifest_path.write_text(json.dumps(_synthetic_excel_manifest()), encoding="utf-8")

        # Act
        manifest = load_excel_regression_manifest(manifest_path)

        # Assert
        assert manifest.terms.interest_calculation_method is InterestCalculationMethod.EQUAL_MONTHS
        assert manifest.to_mortgage_terms().principal.as_integer_ratio() == (100000, 1)
        with pytest.raises(ValidationError):
            manifest.tolerances.__setattr__("monthly", manifest.tolerances.summary)

    def test_manifest_when_top_level_field_is_unknown_expect_validation_failure(self, tmp_path: Path) -> None:
        """Reject manifest drift instead of silently ignoring it."""
        # Arrange
        payload = _synthetic_excel_manifest()
        payload["unexpected"] = True
        manifest_path = tmp_path / "excel.json"
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")

        # Act / Assert
        with pytest.raises(ValidationError, match="unexpected"):
            load_excel_regression_manifest(manifest_path)

    def test_manifest_when_nested_data_is_invalid_expect_validation_failure(self, tmp_path: Path) -> None:
        """Reject unknown fields in nested governed values."""
        # Arrange
        payload = _synthetic_excel_manifest()
        terms = cast(dict[str, object], payload["terms"])
        fees = cast(dict[str, object], terms["fees"])
        fees["unexpected"] = "private"
        manifest_path = tmp_path / "excel.json"
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")

        # Act / Assert
        with pytest.raises(ValidationError, match="unexpected"):
            load_excel_regression_manifest(manifest_path)

    def test_manifest_when_coercible_nested_type_is_invalid_expect_validation_failure(self, tmp_path: Path) -> None:
        """Reject incorrect JSON types instead of silently coercing them."""
        # Arrange
        payload = _synthetic_excel_manifest()
        terms = cast(dict[str, object], payload["terms"])
        rate_periods = cast(list[dict[str, object]], terms["rate_periods"])
        rate_periods[0]["start_month"] = "1"
        manifest_path = tmp_path / "excel.json"
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")

        # Act / Assert
        with pytest.raises(ValidationError, match="start_month"):
            load_excel_regression_manifest(manifest_path)

    def test_manifest_when_file_is_missing_expect_file_not_found(self, tmp_path: Path) -> None:
        """Fail clearly when an explicitly requested private manifest is absent."""
        # Arrange
        manifest_path = tmp_path / "missing.json"

        # Act / Assert
        with pytest.raises(FileNotFoundError, match=r"missing\.json"):
            load_excel_regression_manifest(manifest_path)


class TestLoadInsuranceRegressionManifest:
    """Verify deep immutability of insurance strategy limits."""

    def test_manifest_when_loaded_expect_residual_limits_immutable(self, tmp_path: Path) -> None:
        """Prevent in-place removal of governed residual limits."""
        # Arrange
        payload = {
            "artifact": {"sha256": "b" * 64, "expected_installments": [0, 1, 2]},
            "monthly_rate": "0.0005",
            "residual_limits": [
                {
                    "method": method.value,
                    "limits": {
                        "maximum_residual": "0.10",
                        "total_absolute_error": "1.00",
                        "mean_absolute_error": "0.05",
                        "mean_squared_error": "0.01",
                    },
                }
                for method in InsuranceCalculationMethod
            ],
        }
        manifest_path = tmp_path / "insurance.json"
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")

        # Act
        manifest = load_insurance_regression_manifest(manifest_path)

        # Assert
        limits = manifest.limits_for(InsuranceCalculationMethod.OPENING_BALANCE)
        with pytest.raises(AttributeError):
            cast(dict[object, object], manifest.residual_limits).clear()
        assert manifest.limits_for(InsuranceCalculationMethod.OPENING_BALANCE) == limits
