"""Local parity tests against the reviewed bank repayment schedule."""

from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import polars as pl
import pytest

from mortgage_simulator.reference_data.regression_manifest_loader import (
    CalendarRegressionManifest,
    load_calendar_regression_manifest,
)
from mortgage_simulator.simulation.engine import simulate

REFERENCE_CSV = Path("data/calendar-day-mortgage-reference.csv")
REFERENCE_MANIFEST = Path("data/regression/calendar.json")
PRIVATE_INPUTS_PRESENT = REFERENCE_CSV.exists() and REFERENCE_MANIFEST.exists()
MANIFEST: CalendarRegressionManifest | None = (
    load_calendar_regression_manifest(REFERENCE_MANIFEST) if PRIVATE_INPUTS_PRESENT else None
)
MONEY_COLUMNS = (
    "scheduled_principal",
    "interest",
    "installment_without_subsidy",
    "subsidy",
    "installment_with_subsidy",
    "closing_balance",
)


@pytest.mark.calendar
@pytest.mark.skipif(not PRIVATE_INPUTS_PRESENT, reason="local calendar artifact or manifest is absent")
class TestCalendarReference:
    """Verify the reviewed artifact identity, schema, and engine parity."""

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
        assert reference.shape == (MANIFEST.artifact.expected_rows, 7)
        assert reference.schema["installment"] == pl.Int64
        for column in MONEY_COLUMNS:
            assert reference.schema[column] == pl.Decimal(precision=12, scale=2)
        assert reference.get_column("installment").to_list() == list(MANIFEST.artifact.expected_installments)

    def test_baseline_when_simulated_expect_bank_schedule_parity(self) -> None:
        """Match every supplied installment within the approved source tolerances."""
        # Arrange
        assert MANIFEST is not None
        terms = MANIFEST.to_mortgage_terms()
        reference = _load_reference().filter(pl.col("installment") <= terms.analysis_horizon_months)

        # Act
        result = simulate(terms, MANIFEST.scenario.to_domain())

        # Assert
        for row in reference.iter_rows(named=True):
            payment = result.payments[row["installment"] - 1]
            _assert_close(payment.scheduled_principal, row["scheduled_principal"], MANIFEST.tolerances.component)
            _assert_close(payment.interest, row["interest"], MANIFEST.tolerances.component)
            _assert_close(payment.subsidy, row["subsidy"], MANIFEST.tolerances.component)
            _assert_close(
                payment.scheduled_principal + payment.interest,
                row["installment_without_subsidy"],
                MANIFEST.tolerances.installment,
            )
            _assert_close(
                payment.cash_outflow_without_fees,
                row["installment_with_subsidy"],
                MANIFEST.tolerances.installment,
            )
            _assert_close(
                payment.closing_balance,
                row["closing_balance"],
                MANIFEST.tolerances.closing_balance,
            )


def _load_reference() -> pl.DataFrame:
    return pl.read_csv(
        REFERENCE_CSV,
        schema_overrides={
            "installment": pl.Int64,
            **{column: pl.Decimal(precision=12, scale=2) for column in MONEY_COLUMNS},
        },
    )


def _assert_close(actual: Decimal, expected: Decimal, tolerance: Decimal) -> None:
    assert abs(actual - expected) <= tolerance
