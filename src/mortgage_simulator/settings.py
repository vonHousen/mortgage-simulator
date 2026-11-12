"""Environment-backed application configuration and domain conversion."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict

from mortgage_simulator.simulation.models import (
    FeeTerms,
    InsuranceCalculationMethod,
    InterestCalculationMethod,
    MortgageTerms,
    NonEmptyName,
    RatePeriod,
    SubsidyTerms,
)

FIRST_RATE_KEY = "annual_rate_months_1_60"
SECOND_RATE_KEY = "annual_rate_months_61_120"
FIRST_RATE_ENV_NAME = "MS_MORTGAGE__ANNUAL_RATE_MONTHS_1_60"
SECOND_RATE_ENV_NAME = "MS_MORTGAGE__ANNUAL_RATE_MONTHS_61_120"
LEGACY_ENV_PREFIX = "mortgage_simulator_"
DEFAULT_SCENARIO_CONFIG_PATH = Path("data/config/scenarios.json")


class _FrozenConfig(BaseModel):
    """Base model for immutable configuration groups."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class SubsidyConfig(_FrozenConfig):
    """Environment-configurable mortgage subsidy assumptions."""

    enabled: bool = True
    """Whether the mortgage subsidy reduces monthly interest."""

    coefficient: Decimal = Field(default=Decimal("0.05"), ge=0)
    """Annual subsidy coefficient used to calculate the subsidy amount."""

    reference_rate: Decimal = Field(default=Decimal("0.02"), ge=0)
    """Annual reference rate deducted from the subsidy coefficient."""


class FeeConfig(_FrozenConfig):
    """Environment-configurable fixed and balance-based mortgage costs."""

    annual_fixed_fee: Decimal = Field(default=Decimal("0"), ge=0)
    """Fixed fee charged once per mortgage year."""

    monthly_insurance_rate: Decimal = Field(default=Decimal("0"), ge=0)
    """Monthly insurance rate applied to the configured balance basis."""

    insurance_calculation_method: InsuranceCalculationMethod = InsuranceCalculationMethod.TWO_INTERVAL_WEIGHTED
    """Balance-selection method used for monthly insurance."""

    monthly_fixed_fees: Decimal = Field(default=Decimal("0"), ge=0)
    """Total fixed fees charged every payment month."""

    insurance_end_month: int | None = Field(default=None, ge=0)
    """Last payment month with insurance, or ``None`` for the full horizon."""


class MortgageConfig(_FrozenConfig):
    """Environment-configurable assumptions shared by every simulation."""

    first_payment_date: date = date(2024, 1, 1)
    """Date of the first payment in the simulation."""

    interest_calculation_method: InterestCalculationMethod = InterestCalculationMethod.CALENDAR_DAYS
    """Method used to convert annual rates into monthly interest."""

    principal: Decimal = Field(default=Decimal("500000"), gt=0)
    """Original mortgage principal."""

    contractual_term_months: int = Field(default=360, gt=0)
    """Contractual mortgage duration in months."""

    analysis_horizon_months: int = Field(default=120, gt=0, le=120)
    """Number of payment months included in the analysis."""

    settle_remaining_principal_at_horizon: bool = True
    """Whether the final analyzed month repays the remaining principal."""

    annual_rate_months_1_60: Decimal = Field(default=Decimal("0.07"), ge=0)
    """Annual interest rate applied during payment months 1 through 60."""

    annual_rate_months_61_120: Decimal = Field(default=Decimal("0.08"), ge=0)
    """Annual interest rate applied during payment months 61 through 120."""

    subsidy: SubsidyConfig = Field(default_factory=SubsidyConfig)
    """Subsidy configuration."""

    fees: FeeConfig = Field(default_factory=FeeConfig)
    """Fee configuration."""

    @model_validator(mode="before")
    @classmethod
    def validate_fixed_rate_overrides(cls, values: Any) -> Any:
        """Require both fixed-period rates whenever either is explicitly supplied."""
        if not isinstance(values, dict):
            return values
        has_first_rate = FIRST_RATE_KEY in values
        has_second_rate = SECOND_RATE_KEY in values
        if has_first_rate != has_second_rate:
            raise ValueError(
                "both fixed-period annual rates must be configured together: "
                f"{FIRST_RATE_ENV_NAME} and {SECOND_RATE_ENV_NAME}"
            )
        return values


class ScenarioConfig(_FrozenConfig):
    """Environment-configurable scenario defaults."""

    baseline_name: NonEmptyName = Field(default="Baseline")
    """Name assigned to the simulation without overpayments."""

    config_path: Path = DEFAULT_SCENARIO_CONFIG_PATH
    """Path to the optional local JSON file containing scenario defaults."""


class ChartConfig(_FrozenConfig):
    """Environment-configurable chart presentation defaults."""

    focus_on_typical_payments: bool = False
    """Whether Results payment charts and Comparison cash outflow initially exclude extreme payments."""


class _LegacyKeyRejectingSource(PydanticBaseSettingsSource):
    """Reject previous-prefix keys exposed by an environment settings source."""

    def __init__(self, source: EnvSettingsSource) -> None:
        super().__init__(source.settings_cls)
        self._source = source

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return self._source.get_field_value(field, field_name)

    def __call__(self) -> dict[str, Any]:
        legacy_keys = sorted(key for key in self._source.env_vars if key.startswith(LEGACY_ENV_PREFIX))
        if legacy_keys:
            formatted_keys = ", ".join(key.upper() for key in legacy_keys)
            raise ValueError(
                f"replace {formatted_keys} with MS_ configuration keys; see the configuration documentation"
            )
        return self._source()


class AppSettings(BaseSettings):
    """Root environment-aware application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MS_",
        env_nested_delimiter="__",
        env_parse_none_str="null",
        nested_model_default_partial_update=True,
        extra="forbid",
    )

    mortgage: MortgageConfig = Field(default_factory=MortgageConfig)
    """Mortgage assumptions and their application defaults."""

    scenarios: ScenarioConfig = Field(default_factory=ScenarioConfig)
    """Baseline identity and optional scenario-file configuration."""

    charts: ChartConfig = Field(default_factory=ChartConfig)
    """Chart presentation defaults."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Reject legacy environment keys while preserving native source precedence."""
        if not isinstance(env_settings, EnvSettingsSource) or not isinstance(dotenv_settings, EnvSettingsSource):
            raise TypeError("environment settings sources must expose their parsed keys")
        return (
            init_settings,
            _LegacyKeyRejectingSource(env_settings),
            _LegacyKeyRejectingSource(dotenv_settings),
            file_secret_settings,
        )

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_constructor_fields(cls, values: Any) -> Any:
        """Reject the previous flat constructor interface with migration guidance."""
        if not isinstance(values, dict):
            return values
        replacements = {
            "baseline_name": "scenarios.baseline_name",
            "scenario_config_path": "scenarios.config_path",
            "focus_on_typical_payments": "charts.focus_on_typical_payments",
            "mortgage_terms": "mortgage",
        }
        legacy_fields = sorted(field for field in replacements if field in values)
        if legacy_fields:
            mappings = ", ".join(f"{field} -> {replacements[field]}" for field in legacy_fields)
            raise ValueError(f"legacy settings fields are no longer supported; use {mappings}")
        return values

    def to_mortgage_terms(self) -> MortgageTerms:
        """Convert environment configuration into validated domain terms.

        Returns:
            Complete mortgage terms accepted by the simulation domain.
        """
        mortgage = self.mortgage
        return MortgageTerms(
            first_payment_date=mortgage.first_payment_date,
            interest_calculation_method=mortgage.interest_calculation_method,
            principal=mortgage.principal,
            contractual_term_months=mortgage.contractual_term_months,
            analysis_horizon_months=mortgage.analysis_horizon_months,
            settle_remaining_principal_at_horizon=mortgage.settle_remaining_principal_at_horizon,
            rate_periods=(
                RatePeriod(start_month=1, end_month=60, annual_rate=mortgage.annual_rate_months_1_60),
                RatePeriod(start_month=61, end_month=120, annual_rate=mortgage.annual_rate_months_61_120),
            ),
            subsidy=SubsidyTerms(
                enabled=mortgage.subsidy.enabled,
                coefficient=mortgage.subsidy.coefficient,
                reference_rate=mortgage.subsidy.reference_rate,
            ),
            fees=FeeTerms(
                annual_fixed_fee=mortgage.fees.annual_fixed_fee,
                monthly_insurance_rate=mortgage.fees.monthly_insurance_rate,
                insurance_calculation_method=mortgage.fees.insurance_calculation_method,
                monthly_fixed_fees=mortgage.fees.monthly_fixed_fees,
                insurance_end_month=mortgage.fees.insurance_end_month,
            ),
        )
