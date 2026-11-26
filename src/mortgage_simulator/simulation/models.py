"""Validated inputs and typed calculation results."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self, cast

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ZERO = Decimal("0")
MAX_V1_HORIZON_MONTHS = 120
NonEmptyName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class FrozenModel(BaseModel):
    """Base model for immutable domain values."""

    model_config = ConfigDict(frozen=True)


class InterestCalculationMethod(StrEnum):
    """Supported methods for converting an annual rate into period interest."""

    CALENDAR_DAYS = "calendar_days"
    EQUAL_MONTHS = "equal_months"


class InsuranceCalculationMethod(StrEnum):
    """Supported methods for selecting the balance insured each month."""

    OPENING_BALANCE = "opening_balance"
    MIDPOINT_BALANCE = "midpoint_balance"
    TWO_INTERVAL_WEIGHTED = "two_interval_weighted"


class RatePeriod(FrozenModel):
    """Annual mortgage rate applied to an inclusive month range."""

    start_month: int = Field(ge=1)
    end_month: int = Field(ge=1)
    annual_rate: Decimal = Field(ge=ZERO)

    @model_validator(mode="after")
    def validate_month_range(self) -> Self:
        """Ensure the period ends no earlier than it starts."""
        if self.end_month < self.start_month:
            raise ValueError("rate period end month must not precede its start month")
        return self


class SubsidyTerms(FrozenModel):
    """Mortgage subsidy assumptions."""

    enabled: bool
    coefficient: Decimal = Field(ge=ZERO)
    second_coefficient: Decimal = Field(ge=ZERO)
    reference_rate: Decimal = Field(ge=ZERO)


class FeeTerms(FrozenModel):
    """Fixed and balance-based mortgage costs."""

    annual_fixed_fee: Decimal = Field(ge=ZERO)
    monthly_insurance_rate: Decimal = Field(ge=ZERO)
    insurance_calculation_method: InsuranceCalculationMethod
    monthly_fixed_fees: Decimal = Field(ge=ZERO)
    insurance_end_month: int | None = Field(ge=0)


class MortgageTerms(FrozenModel):
    """Validated inputs shared by every simulation scenario."""

    first_payment_date: date
    interest_calculation_method: InterestCalculationMethod
    principal: Decimal = Field(gt=ZERO)
    contractual_term_months: int = Field(gt=0)
    analysis_horizon_months: int = Field(gt=0, le=MAX_V1_HORIZON_MONTHS)
    settle_remaining_principal_at_horizon: bool
    rate_periods: tuple[RatePeriod, ...]
    subsidy: SubsidyTerms
    fees: FeeTerms

    @model_validator(mode="after")
    def validate_terms(self) -> Self:
        """Validate cross-field term, subsidy, and rate-period rules."""
        if self.first_payment_date.day > 28:
            raise ValueError("first payment date must use day 1 through 28")
        first_month_index = self.first_payment_date.year * 12 + self.first_payment_date.month - 1
        if first_month_index - 1 < 12:
            raise ValueError("preceding payment boundary exceeds the supported calendar range")
        last_month_index = first_month_index + self.analysis_horizon_months - 1
        if last_month_index > 9999 * 12 + 11:
            raise ValueError("analysis horizon exceeds the supported calendar range")
        if self.analysis_horizon_months > self.contractual_term_months:
            raise ValueError("analysis horizon must not exceed the contractual term")
        if min(self.subsidy.coefficient, self.subsidy.second_coefficient) < self.subsidy.reference_rate:
            raise ValueError("subsidy coefficient must not be lower than the reference rate")
        self._validate_rate_coverage()
        return self

    def _validate_rate_coverage(self) -> None:
        expected_start = 1
        for period in self.rate_periods:
            if period.start_month != expected_start:
                raise ValueError("rate periods must be contiguous and start at month 1")
            expected_start = period.end_month + 1
            if period.end_month >= self.analysis_horizon_months:
                return
        raise ValueError("rate periods must cover the analysis horizon")


class LumpSum(FrozenModel):
    """One additional principal payment in a selected month."""

    month: int = Field(ge=1)
    amount: Decimal = Field(gt=ZERO)


class InvestmentMode(StrEnum):
    """Deposit repayment selection mode."""

    MANUAL = "manual"
    AUTOMATIC = "automatic"


class DepositInvestment(FrozenModel):
    """Fixed-rate deposit funded on a mortgage payment date."""

    initial_amount: Decimal = Field(gt=ZERO, decimal_places=2)
    start_month: int = Field(ge=1)
    annual_rate: Decimal = Field(ge=ZERO)
    term_months: int = Field(gt=0)
    mode: InvestmentMode = InvestmentMode.MANUAL
    term_count: int | None = Field(default=None, ge=0)
    contribution_months: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_mode(self) -> Self:
        """Require a term count only for manual selection."""
        if self.mode == InvestmentMode.MANUAL and self.term_count is None:
            raise ValueError("manual investment requires a term count")
        if self.mode == InvestmentMode.AUTOMATIC and self.term_count is not None:
            raise ValueError("automatic investment must not specify a term count")
        if self.contribution_months > 1 and (self.term_count is None or self.term_count == 0):
            raise ValueError("monthly deposits require a positive manual term count")
        return self


class DepositTerm(FrozenModel):
    """Credited interest and tax at one deposit maturity."""

    maturity_month: int
    opening_balance: Decimal
    gross_interest: Decimal
    tax: Decimal
    closing_balance: Decimal


class InvestmentSummary(FrozenModel):
    """Investment funding and disposition, separate from mortgage costs."""

    planned_term_count: int
    completion_month: int
    gross_interest: Decimal
    tax: Decimal
    net_earnings: Decimal
    applied_repayment: Decimal
    retained_surplus: Decimal
    terms: tuple[DepositTerm, ...]


class InvestmentTotals(FrozenModel):
    """Combined investment earnings and disposition for a scenario."""

    gross_interest: Decimal
    tax: Decimal
    net_earnings: Decimal
    applied_repayment: Decimal
    retained_surplus: Decimal


class DepositOutcome(FrozenModel):
    """Disposition of the capital assigned to one deposit."""

    investment_index: int
    opening_month: int
    initial_amount: Decimal
    summary: InvestmentSummary


def calculate_net_financing_cost(mortgage_cost: Decimal, net_earnings: Decimal) -> Decimal:
    """Subtract net deposit earnings from mortgage financing charges."""
    return mortgage_cost - net_earnings


class InvestmentCandidate(FrozenModel):
    """Mortgage-cost objective and investment outcome for one candidate."""

    term_count: int
    repayment_month: int
    total_mortgage_cost: Decimal
    ending_balance: Decimal
    investment: InvestmentSummary
    other_net_earnings: Decimal = ZERO
    other_retained_surplus: Decimal = ZERO

    @property
    def net_earnings(self) -> Decimal:
        """Return total earnings across deposits for this timing."""
        return self.investment.net_earnings + self.other_net_earnings

    @property
    def retained_surplus(self) -> Decimal:
        """Return total surplus across deposits for this timing."""
        return self.investment.retained_surplus + self.other_retained_surplus

    @property
    def net_financing_cost(self) -> Decimal:
        """Return mortgage cost minus net investment earnings."""
        return calculate_net_financing_cost(self.total_mortgage_cost, self.net_earnings)


class OverpaymentScenario(FrozenModel):
    """Recurring and one-off overpayments for one simulation."""

    name: NonEmptyName
    recurring_amount: Decimal = Field(default=ZERO, ge=ZERO)
    cash_outflow_target: Decimal = Field(default=ZERO, ge=ZERO)
    recurring_start_month: int | None = Field(default=None, ge=1)
    lump_sums: tuple[LumpSum, ...] = ()
    investments: tuple[DepositInvestment, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_investment(cls, value: object) -> object:
        """Accept the former singular key when loading saved scenario data.

        Args:
            value: Raw scenario input.
        """
        if not isinstance(value, dict) or "investment" not in value:
            return value
        if "investments" in value:
            raise ValueError("use either investments or the legacy investment key")

        scenario = cast(dict[object, object], value).copy()
        legacy = scenario.pop("investment")
        if legacy is None:
            legacy = ()
        elif isinstance(legacy, (dict, DepositInvestment)):
            legacy = (legacy,)
        scenario["investments"] = legacy
        return scenario

    @model_validator(mode="after")
    def validate_automatic_timing(self) -> Self:
        """Limit automatic timing to a single entry per scenario."""
        if sum(entry.mode == InvestmentMode.AUTOMATIC for entry in self.investments) > 1:
            raise ValueError("only one investment entry may use automatic timing")
        return self

    @model_validator(mode="after")
    def validate_recurring_payment(self) -> Self:
        """Require exactly one positive recurring strategy value with a start month."""
        if self.recurring_amount > ZERO and self.cash_outflow_target > ZERO:
            raise ValueError("recurring amount and cash-outflow target cannot both be positive")
        has_recurring_value = self.recurring_amount > ZERO or self.cash_outflow_target > ZERO
        if has_recurring_value and self.recurring_start_month is None:
            raise ValueError("recurring overpayment requires a start month")
        if not has_recurring_value and self.recurring_start_month is not None:
            raise ValueError("recurring start month requires a positive amount or cash-outflow target")
        return self


class SimulationRequest(FrozenModel):
    """One validated baseline and scenario comparison request."""

    terms: MortgageTerms
    scenarios: tuple[OverpaymentScenario, ...] = ()

    @model_validator(mode="after")
    def validate_scenarios(self) -> Self:
        """Validate scenario uniqueness and all payment months against the horizon."""
        names = [scenario.name for scenario in self.scenarios]
        if len(names) != len(set(names)):
            raise ValueError("scenario names must be unique")
        for scenario in self.scenarios:
            for investment in scenario.investments:
                last_opening = investment.start_month + investment.contribution_months - 1
                maturity = last_opening + (investment.term_count or 0) * investment.term_months
                if maturity > self.terms.analysis_horizon_months:
                    raise ValueError("investment start and maturity must be within the analysis horizon")
            if (
                scenario.recurring_start_month is not None
                and scenario.recurring_start_month > self.terms.analysis_horizon_months
            ):
                raise ValueError("recurring start month must be within the analysis horizon")
            if any(lump_sum.month > self.terms.analysis_horizon_months for lump_sum in scenario.lump_sums):
                raise ValueError("lump-sum month must be within the analysis horizon")
        return self


class MonthlyPayment(FrozenModel):
    """All calculated values for one mortgage payment month."""

    month: int
    payment_date: date
    opening_balance: Decimal
    scheduled_principal: Decimal
    recurring_overpayment: Decimal
    lump_sum: Decimal
    horizon_settlement: Decimal
    interest: Decimal
    subsidy: Decimal
    monthly_insurance: Decimal
    monthly_fixed_fees: Decimal
    annual_fixed_fee: Decimal
    fees: Decimal
    cash_outflow_without_fees: Decimal
    cash_outflow: Decimal
    closing_balance: Decimal


class SimulationSummary(FrozenModel):
    """Aggregated values for one scenario."""

    total_principal: Decimal
    principal_repaid_before_horizon_settlement: Decimal
    horizon_settlement: Decimal
    total_interest: Decimal
    total_subsidy: Decimal
    total_fees: Decimal
    total_cash_outflow: Decimal
    total_mortgage_cost: Decimal
    mortgage_cost_to_original_principal: Decimal
    mortgage_cost_to_principal_repaid: Decimal
    net_average_annual_interest_rate: Decimal
    ending_balance: Decimal
    payoff_month: int | None


class SimulationResult(FrozenModel):
    """Monthly schedule and summary for one named scenario."""

    scenario_name: str
    payments: tuple[MonthlyPayment, ...]
    summary: SimulationSummary
    investment: InvestmentSummary | None = None
    investment_candidates: tuple[InvestmentCandidate, ...] = ()
    investments: tuple[DepositOutcome, ...] = ()

    @property
    def investment_totals(self) -> InvestmentTotals | None:
        """Aggregate all realized deposit outcomes, including legacy results."""
        summaries = tuple(item.summary for item in self.investments)
        if not summaries:
            if self.investment is None:
                return None
            summaries = (self.investment,)
        return InvestmentTotals(
            gross_interest=sum((item.gross_interest for item in summaries), ZERO),
            tax=sum((item.tax for item in summaries), ZERO),
            net_earnings=sum((item.net_earnings for item in summaries), ZERO),
            applied_repayment=sum((item.applied_repayment for item in summaries), ZERO),
            retained_surplus=sum((item.retained_surplus for item in summaries), ZERO),
        )

    @property
    def net_investment_earnings(self) -> Decimal:
        """Return realized after-tax earnings from all deposits."""
        totals = self.investment_totals
        return totals.net_earnings if totals else ZERO

    @property
    def retained_investment_surplus(self) -> Decimal:
        """Return deposit proceeds retained outside the mortgage."""
        totals = self.investment_totals
        return totals.retained_surplus if totals else ZERO

    @property
    def net_financing_cost(self) -> Decimal:
        """Return mortgage cost minus net investment earnings, if present."""
        return calculate_net_financing_cost(self.summary.total_mortgage_cost, self.net_investment_earnings)


class ScenarioComparison(FrozenModel):
    """One scenario summary and its differences from the baseline."""

    scenario_name: str
    summary: SimulationSummary
    net_investment_earnings: Decimal = ZERO
    retained_surplus: Decimal = ZERO
    net_financing_cost_delta: Decimal = ZERO

    @property
    def net_financing_cost(self) -> Decimal:
        """Return mortgage cost minus net investment earnings."""
        return calculate_net_financing_cost(self.summary.total_mortgage_cost, self.net_investment_earnings)

    cash_outflow_delta: Decimal
    interest_delta: Decimal
    ending_balance_delta: Decimal
    mortgage_cost_delta: Decimal
    horizon_settlement_delta: Decimal
    subsidy_delta: Decimal
    net_average_annual_interest_rate_percentage_point_delta: Decimal
    mortgage_cost_savings_to_overpayment_ratio: Decimal | None


class ComparisonReport(FrozenModel):
    """Baseline-relative comparison of all simulation results."""

    scenarios: tuple[ScenarioComparison, ...]
