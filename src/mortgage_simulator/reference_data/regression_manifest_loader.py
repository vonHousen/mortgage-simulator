"""Strict loaders for ignored local regression manifests."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from mortgage_simulator.simulation.models import (
    FeeTerms,
    InsuranceCalculationMethod,
    InterestCalculationMethod,
    LumpSum,
    MortgageTerms,
    OverpaymentScenario,
    RatePeriod,
    SubsidyTerms,
)

ZERO = Decimal("0")
Sha256Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class RegressionManifestModel(BaseModel):
    """Base model for immutable manifests that reject unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ArtifactIdentity(RegressionManifestModel):
    """Digest shared by every private regression artifact."""

    sha256: Sha256Digest


class ExcelArtifactIdentity(ArtifactIdentity):
    """Reviewed workbook identity and worksheet order."""

    sheets: tuple[str, ...]


class RegressionRatePeriod(RegressionManifestModel):
    """Manifest representation of one governed rate period."""

    start_month: int = Field(ge=1)
    end_month: int = Field(ge=1)
    annual_rate: Decimal = Field(ge=ZERO)


class RegressionSubsidyTerms(RegressionManifestModel):
    """Manifest representation of governed subsidy assumptions."""

    enabled: bool
    coefficient: Decimal = Field(ge=ZERO)
    reference_rate: Decimal = Field(ge=ZERO)


class RegressionFeeTerms(RegressionManifestModel):
    """Manifest representation of governed fee assumptions."""

    annual_fixed_fee: Decimal = Field(ge=ZERO)
    monthly_insurance_rate: Decimal = Field(ge=ZERO)
    insurance_calculation_method: InsuranceCalculationMethod
    monthly_fixed_fees: Decimal = Field(ge=ZERO)
    insurance_end_month: int | None = Field(ge=0)


class RegressionMortgageTerms(RegressionManifestModel):
    """Complete governed mortgage terms without application defaults."""

    first_payment_date: date
    interest_calculation_method: InterestCalculationMethod
    principal: Decimal = Field(gt=ZERO)
    contractual_term_months: int = Field(gt=0)
    analysis_horizon_months: int = Field(gt=0)
    settle_remaining_principal_at_horizon: bool
    rate_periods: tuple[RegressionRatePeriod, ...]
    subsidy: RegressionSubsidyTerms
    fees: RegressionFeeTerms

    def to_domain(self) -> MortgageTerms:
        """Build the simulation-domain mortgage terms represented by this manifest."""
        return MortgageTerms(
            first_payment_date=self.first_payment_date,
            interest_calculation_method=self.interest_calculation_method,
            principal=self.principal,
            contractual_term_months=self.contractual_term_months,
            analysis_horizon_months=self.analysis_horizon_months,
            settle_remaining_principal_at_horizon=self.settle_remaining_principal_at_horizon,
            rate_periods=tuple(
                RatePeriod(
                    start_month=period.start_month,
                    end_month=period.end_month,
                    annual_rate=period.annual_rate,
                )
                for period in self.rate_periods
            ),
            subsidy=SubsidyTerms(
                enabled=self.subsidy.enabled,
                coefficient=self.subsidy.coefficient,
                second_coefficient=self.subsidy.coefficient,
                reference_rate=self.subsidy.reference_rate,
            ),
            fees=FeeTerms(
                annual_fixed_fee=self.fees.annual_fixed_fee,
                monthly_insurance_rate=self.fees.monthly_insurance_rate,
                insurance_calculation_method=self.fees.insurance_calculation_method,
                monthly_fixed_fees=self.fees.monthly_fixed_fees,
                insurance_end_month=self.fees.insurance_end_month,
            ),
        )


class RegressionLumpSum(RegressionManifestModel):
    """Manifest representation of one governed lump sum."""

    month: int = Field(ge=1)
    amount: Decimal = Field(gt=ZERO)


class RegressionScenario(RegressionManifestModel):
    """Complete governed scenario without domain defaults."""

    name: str = Field(min_length=1)
    recurring_amount: Decimal = Field(ge=ZERO)
    cash_outflow_target: Decimal = Field(ge=ZERO)
    recurring_start_month: int | None = Field(ge=1)
    lump_sums: tuple[RegressionLumpSum, ...]

    def to_domain(self) -> OverpaymentScenario:
        """Build the simulation-domain scenario represented by this manifest."""
        return OverpaymentScenario(
            name=self.name,
            recurring_amount=self.recurring_amount,
            cash_outflow_target=self.cash_outflow_target,
            recurring_start_month=self.recurring_start_month,
            lump_sums=tuple(LumpSum(month=lump_sum.month, amount=lump_sum.amount) for lump_sum in self.lump_sums),
        )


class ExcelTolerances(RegressionManifestModel):
    """Approved workbook comparison tolerances."""

    monthly: Decimal = Field(ge=ZERO)
    summary: Decimal = Field(ge=ZERO)


class ExcelRegressionCase(RegressionManifestModel):
    """Worksheet and scenario pairing for one workbook parity case."""

    sheet_name: str = Field(min_length=1)
    summary_row: int = Field(ge=1)
    scenario: RegressionScenario


class ExcelWorksheetMapping(RegressionManifestModel):
    """Coordinates used to map cached workbook values to engine fields."""

    payment_row_offset: int = Field(ge=0)
    principal_column: int = Field(ge=1)
    interest_column: int = Field(ge=1)
    subsidy_column: int = Field(ge=1)
    fees_column: int = Field(ge=1)
    cash_outflow_column: int = Field(ge=1)
    closing_balance_column: int = Field(ge=1)
    ending_balance_cell: str = Field(min_length=1)


class ExcludedExcelComparison(RegressionManifestModel):
    """One intentionally omitted workbook comparison."""

    scenario_name: str = Field(min_length=1)
    month: int = Field(ge=1)
    comparison: str = Field(min_length=1)


class AcceptedCappedPayoffDifference(RegressionManifestModel):
    """Reviewed payoff difference caused by capped principal settlement."""

    scenario_name: str = Field(min_length=1)
    engine_ending_balance: Decimal
    engine_total_principal: Decimal = Field(gt=ZERO)
    worksheet_ending_balance: Decimal


class ExcelRegressionManifest(RegressionManifestModel):
    """All governed inputs for workbook identity and parity tests."""

    artifact: ExcelArtifactIdentity
    terms: RegressionMortgageTerms
    tolerances: ExcelTolerances
    representative_months: tuple[int, ...]
    scenarios: tuple[ExcelRegressionCase, ...]
    worksheet_mapping: ExcelWorksheetMapping
    excluded_comparisons: tuple[ExcludedExcelComparison, ...]
    accepted_capped_payoff_difference: AcceptedCappedPayoffDifference

    def to_mortgage_terms(self) -> MortgageTerms:
        """Build the domain mortgage terms governed by this manifest."""
        return self.terms.to_domain()


class CalendarArtifactIdentity(ArtifactIdentity):
    """Reviewed calendar CSV identity and expected shape."""

    expected_rows: int = Field(gt=0)
    expected_installments: tuple[int, ...]


class CalendarTolerances(RegressionManifestModel):
    """Approved calendar component tolerances."""

    component: Decimal = Field(ge=ZERO)
    installment: Decimal = Field(ge=ZERO)
    closing_balance: Decimal = Field(ge=ZERO)


class CalendarRegressionManifest(RegressionManifestModel):
    """All governed inputs for calendar schedule parity."""

    artifact: CalendarArtifactIdentity
    terms: RegressionMortgageTerms
    scenario: RegressionScenario
    tolerances: CalendarTolerances

    def to_mortgage_terms(self) -> MortgageTerms:
        """Build the domain mortgage terms governed by this manifest."""
        return self.terms.to_domain()


class InsuranceArtifactIdentity(ArtifactIdentity):
    """Reviewed insurance CSV identity and installment sequence."""

    expected_installments: tuple[int, ...]


class InsuranceResidualLimits(RegressionManifestModel):
    """Approved residual limits for one insurance strategy."""

    maximum_residual: Decimal = Field(ge=ZERO)
    total_absolute_error: Decimal = Field(ge=ZERO)
    mean_absolute_error: Decimal = Field(ge=ZERO)
    mean_squared_error: Decimal = Field(ge=ZERO)


class InsuranceStrategyResidualLimits(RegressionManifestModel):
    """Approved residual limits paired with one insurance strategy."""

    method: InsuranceCalculationMethod
    limits: InsuranceResidualLimits


class InsuranceRegressionManifest(RegressionManifestModel):
    """All governed inputs for monthly-insurance parity."""

    artifact: InsuranceArtifactIdentity
    monthly_rate: Decimal = Field(ge=ZERO)
    residual_limits: tuple[InsuranceStrategyResidualLimits, ...]

    def limits_for(self, method: InsuranceCalculationMethod) -> InsuranceResidualLimits:
        """Return the governed residual limits for a strategy.

        Args:
            method: Insurance calculation strategy to look up.

        Returns:
            The immutable residual limits paired with the strategy.
        """
        return next(entry.limits for entry in self.residual_limits if entry.method is method)

    @model_validator(mode="after")
    def validate_strategy_coverage(self) -> Self:
        """Require residual limits for every supported strategy."""
        methods = [entry.method for entry in self.residual_limits]
        if len(methods) != len(set(methods)) or set(methods) != set(InsuranceCalculationMethod):
            raise ValueError("residual limits must cover every insurance calculation method")
        return self


def load_excel_regression_manifest(path: Path) -> ExcelRegressionManifest:
    """Load the ignored workbook regression manifest.

    Args:
        path: Filesystem path to the JSON manifest.

    Returns:
        The validated immutable workbook manifest.
    """
    return _load_manifest(path, ExcelRegressionManifest)


def load_calendar_regression_manifest(path: Path) -> CalendarRegressionManifest:
    """Load the ignored calendar regression manifest.

    Args:
        path: Filesystem path to the JSON manifest.

    Returns:
        The validated immutable calendar manifest.
    """
    return _load_manifest(path, CalendarRegressionManifest)


def load_insurance_regression_manifest(path: Path) -> InsuranceRegressionManifest:
    """Load the ignored insurance regression manifest.

    Args:
        path: Filesystem path to the JSON manifest.

    Returns:
        The validated immutable insurance manifest.
    """
    return _load_manifest(path, InsuranceRegressionManifest)


def _load_manifest[ManifestT: RegressionManifestModel](path: Path, manifest_type: type[ManifestT]) -> ManifestT:
    return manifest_type.model_validate_json(path.read_text(encoding="utf-8"))
