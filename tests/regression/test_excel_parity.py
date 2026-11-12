"""Local parity tests against cached values in the ignored Excel workbook."""

from decimal import Decimal
from pathlib import Path

import pytest

from mortgage_simulator.reference_data.excel_workbook_loader import load_reference_workbook
from mortgage_simulator.reference_data.regression_manifest_loader import (
    ExcelRegressionCase,
    ExcelRegressionManifest,
    load_excel_regression_manifest,
)
from mortgage_simulator.simulation.engine import simulate

REFERENCE_WORKBOOK = Path("data/mortgage-simulation-v2.xlsx")
REFERENCE_MANIFEST = Path("data/regression/excel.json")
PRIVATE_INPUTS_PRESENT = REFERENCE_WORKBOOK.exists() and REFERENCE_MANIFEST.exists()
MANIFEST: ExcelRegressionManifest | None = (
    load_excel_regression_manifest(REFERENCE_MANIFEST) if PRIVATE_INPUTS_PRESENT else None
)
REGRESSION_CASES = MANIFEST.scenarios if MANIFEST is not None else ()


@pytest.mark.excel
@pytest.mark.skipif(not PRIVATE_INPUTS_PRESENT, reason="local workbook artifact or manifest is absent")
class TestExcelParity:
    """Compare engine output with reviewed cached workbook values."""

    @pytest.mark.parametrize("case", REGRESSION_CASES, ids=lambda case: case.scenario.name)
    def test_scenario_when_simulated_expect_representative_months_match(self, case: ExcelRegressionCase) -> None:
        """Match payment components at scenario and period boundaries."""
        # Arrange
        assert MANIFEST is not None
        workbook = load_reference_workbook(REFERENCE_WORKBOOK)
        worksheet = workbook[case.sheet_name]
        terms = MANIFEST.to_mortgage_terms()
        scenario = case.scenario.to_domain()
        mapping = MANIFEST.worksheet_mapping

        # Act
        result = simulate(terms, scenario)

        # Assert
        for month in MANIFEST.representative_months:
            if _is_excluded(case.scenario.name, month, "monthly"):
                continue
            payment = result.payments[month - 1]
            row = month + mapping.payment_row_offset
            _assert_close(
                payment.scheduled_principal + payment.recurring_overpayment + payment.lump_sum,
                worksheet.cell(row=row, column=mapping.principal_column).value,
                MANIFEST.tolerances.monthly,
            )
            _assert_close(
                payment.interest,
                worksheet.cell(row=row, column=mapping.interest_column).value,
                MANIFEST.tolerances.monthly,
            )
            _assert_close(
                payment.subsidy,
                worksheet.cell(row=row, column=mapping.subsidy_column).value,
                MANIFEST.tolerances.monthly,
            )
            _assert_close(
                payment.fees,
                _annual_fee_adjusted_workbook_value(
                    worksheet.cell(row=row, column=mapping.fees_column).value,
                    month,
                ),
                MANIFEST.tolerances.monthly,
            )
            _assert_close(
                payment.cash_outflow,
                _annual_fee_adjusted_workbook_value(
                    worksheet.cell(row=row, column=mapping.cash_outflow_column).value,
                    month,
                ),
                MANIFEST.tolerances.monthly,
            )
            assert payment.cash_outflow == payment.cash_outflow_without_fees + payment.fees
            _assert_close(
                payment.closing_balance,
                worksheet.cell(row=row, column=mapping.closing_balance_column).value,
                MANIFEST.tolerances.monthly,
            )
        workbook.close()

    @pytest.mark.parametrize("case", REGRESSION_CASES, ids=lambda case: case.scenario.name)
    def test_scenario_when_simulated_expect_summary_matches(self, case: ExcelRegressionCase) -> None:
        """Match ten-year totals except for the documented payoff correction."""
        # Arrange
        assert MANIFEST is not None
        workbook = load_reference_workbook(REFERENCE_WORKBOOK)
        worksheet = workbook[case.sheet_name]
        accepted_difference = MANIFEST.accepted_capped_payoff_difference

        # Act
        result = simulate(MANIFEST.to_mortgage_terms(), case.scenario.to_domain())

        # Assert
        if case.scenario.name == accepted_difference.scenario_name:
            assert result.summary.ending_balance == accepted_difference.engine_ending_balance
            _assert_close(
                result.summary.total_principal,
                accepted_difference.engine_total_principal,
                MANIFEST.tolerances.summary,
            )
            _assert_close(
                _decimal(worksheet[MANIFEST.worksheet_mapping.ending_balance_cell].value),
                accepted_difference.worksheet_ending_balance,
                MANIFEST.tolerances.summary,
            )
            assert (
                _decimal(worksheet.cell(row=case.summary_row, column=MANIFEST.worksheet_mapping.principal_column).value)
                > accepted_difference.engine_total_principal
            )
            workbook.close()
            return
        _assert_close(
            result.summary.total_principal,
            worksheet.cell(row=case.summary_row, column=MANIFEST.worksheet_mapping.principal_column).value,
            MANIFEST.tolerances.summary,
        )
        _assert_close(
            result.summary.total_interest,
            worksheet.cell(row=case.summary_row, column=MANIFEST.worksheet_mapping.interest_column).value,
            MANIFEST.tolerances.summary,
        )
        _assert_close(
            result.summary.total_subsidy,
            worksheet.cell(row=case.summary_row, column=MANIFEST.worksheet_mapping.subsidy_column).value,
            MANIFEST.tolerances.summary,
        )
        _assert_close(
            result.summary.total_fees,
            worksheet.cell(row=case.summary_row, column=MANIFEST.worksheet_mapping.fees_column).value,
            MANIFEST.tolerances.summary,
        )
        _assert_close(
            result.summary.total_cash_outflow,
            worksheet.cell(row=case.summary_row, column=MANIFEST.worksheet_mapping.cash_outflow_column).value,
            MANIFEST.tolerances.summary,
        )
        _assert_close(
            result.summary.ending_balance,
            worksheet[MANIFEST.worksheet_mapping.ending_balance_cell].value,
            MANIFEST.tolerances.summary,
        )
        workbook.close()


def _assert_close(actual: Decimal, expected: object, tolerance: Decimal) -> None:
    assert abs(actual - _decimal(expected)) <= tolerance


def _annual_fee_adjusted_workbook_value(value: object, month: int) -> Decimal:
    assert MANIFEST is not None
    annual_fee = MANIFEST.terms.fees.annual_fixed_fee
    annual_fee_share = annual_fee / Decimal("12")
    anniversary_fee = annual_fee if (month - 1) % 12 == 0 else Decimal("0")
    return _decimal(value) - annual_fee_share + anniversary_fee


def _is_excluded(scenario_name: str, month: int, comparison: str) -> bool:
    assert MANIFEST is not None
    return any(
        exclusion.scenario_name == scenario_name and exclusion.month == month and exclusion.comparison == comparison
        for exclusion in MANIFEST.excluded_comparisons
    )


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))
