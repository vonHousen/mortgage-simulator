"""Identity checks for the ignored local reference workbook."""

from hashlib import sha256
from pathlib import Path

import pytest
from openpyxl import load_workbook

from mortgage_simulator.reference_data.regression_manifest_loader import (
    ExcelRegressionManifest,
    load_excel_regression_manifest,
)

REFERENCE_WORKBOOK = Path("data/mortgage-simulation-v2.xlsx")
REFERENCE_MANIFEST = Path("data/regression/excel.json")
PRIVATE_INPUTS_PRESENT = REFERENCE_WORKBOOK.exists() and REFERENCE_MANIFEST.exists()
MANIFEST: ExcelRegressionManifest | None = (
    load_excel_regression_manifest(REFERENCE_MANIFEST) if PRIVATE_INPUTS_PRESENT else None
)


@pytest.mark.excel
@pytest.mark.skipif(not PRIVATE_INPUTS_PRESENT, reason="local workbook artifact or manifest is absent")
class TestReferenceWorkbook:
    """Verify the identity and structure expected by parity tests."""

    def test_workbook_when_loaded_expect_documented_identity(self) -> None:
        """Verify that local regression uses the reviewed workbook version."""
        # Arrange
        assert MANIFEST is not None
        workbook_bytes = REFERENCE_WORKBOOK.read_bytes()

        # Act
        workbook_digest = sha256(workbook_bytes).hexdigest()

        # Assert
        assert workbook_digest == MANIFEST.artifact.sha256

    def test_workbook_when_loaded_expect_documented_sheets(self) -> None:
        """Verify that all reviewed worksheets are present in order."""
        # Arrange
        assert MANIFEST is not None
        workbook = load_workbook(REFERENCE_WORKBOOK, read_only=True, data_only=True)

        # Act
        sheet_names = workbook.sheetnames
        workbook.close()

        # Assert
        assert sheet_names == list(MANIFEST.artifact.sheets)
