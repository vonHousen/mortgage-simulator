"""Local parity tests against reviewed monthly-insurance charges."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import cast

import polars as pl
import pytest

from mortgage_simulator.reference_data.regression_manifest_loader import (
    InsuranceRegressionManifest,
    load_insurance_regression_manifest,
)
from mortgage_simulator.simulation.models import InsuranceCalculationMethod
from mortgage_simulator.simulation.mortgage.insurance import calculate_monthly_insurance

REFERENCE_CSV = Path("data/monthly-insurance-values.csv")
REFERENCE_MANIFEST = Path("data/regression/insurance.json")
PRIVATE_INPUTS_PRESENT = REFERENCE_CSV.exists() and REFERENCE_MANIFEST.exists()
MANIFEST: InsuranceRegressionManifest | None = (
    load_insurance_regression_manifest(REFERENCE_MANIFEST) if PRIVATE_INPUTS_PRESENT else None
)


@dataclass(frozen=True)
class InsuranceResidual:
    """One reference comparison with its absolute residual."""

    installment: int
    actual: Decimal
    predicted: Decimal

    @property
    def absolute(self) -> Decimal:
        """Return the absolute prediction residual."""
        return abs(self.actual - self.predicted)


@pytest.mark.insurance
@pytest.mark.skipif(not PRIVATE_INPUTS_PRESENT, reason="local insurance artifact or manifest is absent")
class TestInsuranceReference:
    """Verify artifact identity and bounded residuals for every strategy."""

    def test_csv_when_loaded_expect_documented_identity_and_schema(self) -> None:
        """Reject changes to the reviewed reference bytes or typed schema."""
        # Arrange
        assert MANIFEST is not None
        reference_bytes = REFERENCE_CSV.read_bytes()

        # Act
        digest = sha256(reference_bytes).hexdigest()
        reference = _load_reference()

        # Assert
        assert digest == MANIFEST.artifact.sha256
        assert reference.shape == (len(MANIFEST.artifact.expected_installments), 4)
        assert reference.schema == {
            "installment": pl.Int64,
            "date": pl.Date,
            "monthly_insurance_value": pl.Decimal(precision=12, scale=2),
            "closing_balance": pl.Decimal(precision=12, scale=2),
        }
        assert reference.get_column("installment").to_list() == list(MANIFEST.artifact.expected_installments)

    @pytest.mark.parametrize("method", tuple(InsuranceCalculationMethod))
    def test_strategy_when_compared_expect_approved_residual_limits(
        self,
        method: InsuranceCalculationMethod,
    ) -> None:
        """Keep per-row and aggregate residuals within reviewed limits."""
        # Arrange
        assert MANIFEST is not None
        rows = _load_reference().iter_rows(named=True)
        reference_rows = list(rows)
        limits = MANIFEST.limits_for(method)

        # Act
        residuals = _calculate_residuals(reference_rows, method)
        total_absolute_error = sum((residual.absolute for residual in residuals), start=Decimal("0"))
        observation_count = Decimal(len(residuals))
        mean_absolute_error = total_absolute_error / observation_count
        mean_squared_error = (
            sum((residual.absolute**2 for residual in residuals), start=Decimal("0")) / observation_count
        )

        # Assert
        for residual in residuals:
            assert residual.absolute <= limits.maximum_residual, (
                f"{method.value} installment {residual.installment}: actual {residual.actual}, "
                f"predicted {residual.predicted}, residual {residual.absolute}, "
                f"threshold {limits.maximum_residual}"
            )
        assert total_absolute_error <= limits.total_absolute_error
        assert mean_absolute_error <= limits.mean_absolute_error
        assert mean_squared_error <= limits.mean_squared_error


def _load_reference() -> pl.DataFrame:
    return pl.read_csv(
        REFERENCE_CSV,
        schema_overrides={
            "installment": pl.Int64,
            "date": pl.Date,
            "monthly_insurance_value": pl.Decimal(precision=12, scale=2),
            "closing_balance": pl.Decimal(precision=12, scale=2),
        },
        try_parse_dates=True,
    )


def _calculate_residuals(
    rows: list[dict[str, int | date | Decimal]],
    method: InsuranceCalculationMethod,
) -> list[InsuranceResidual]:
    assert MANIFEST is not None
    residuals: list[InsuranceResidual] = []
    for index in range(2, len(rows)):
        previous_row = rows[index - 2]
        opening_row = rows[index - 1]
        actual_row = rows[index]
        previous_date = cast(date, previous_row["date"])
        opening_date = cast(date, opening_row["date"])
        actual_date = cast(date, actual_row["date"])
        previous_balance = cast(Decimal, previous_row["closing_balance"])
        opening_balance = cast(Decimal, opening_row["closing_balance"])
        actual = cast(Decimal, actual_row["monthly_insurance_value"])
        predicted = calculate_monthly_insurance(
            method=method,
            monthly_rate=MANIFEST.monthly_rate,
            previous_opening_balance=previous_balance,
            opening_balance=opening_balance,
            previous_period_days=(opening_date - previous_date).days,
            current_period_days=(actual_date - opening_date).days,
        )
        residuals.append(
            InsuranceResidual(
                installment=cast(int, actual_row["installment"]),
                actual=actual,
                predicted=predicted,
            )
        )
    return residuals
