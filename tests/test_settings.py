"""Tests for application settings."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from mortgage_simulator.settings import AppSettings
from mortgage_simulator.simulation.models import RatePeriod


class TestAppSettings:
    """Tests for application fallbacks and environment overrides."""

    def test_settings_when_dotenv_disabled_expect_documented_fallbacks(self) -> None:
        """Expose every application fallback through explicit configuration groups."""
        # Arrange / Act
        settings = _settings(env_file=None)

        # Assert
        assert settings.scenarios.baseline_name == "Baseline"
        assert settings.scenarios.config_path == Path("data/config/scenarios.json")
        assert settings.charts.focus_on_typical_payments is False
        assert settings.mortgage.first_payment_date == date(2024, 1, 1)
        assert settings.mortgage.principal == Decimal("500000")
        assert settings.mortgage.annual_rate_months_1_60 == Decimal("0.07")
        assert settings.mortgage.annual_rate_months_61_120 == Decimal("0.06")
        assert settings.mortgage.subsidy.enabled is True
        assert settings.mortgage.subsidy.coefficient_months_1_60 == Decimal("0.07")
        assert settings.mortgage.subsidy.reference_rate == Decimal("0.02")
        assert settings.mortgage.fees.annual_fixed_fee == Decimal("0")
        assert settings.mortgage.fees.monthly_insurance_rate == Decimal("0")
        assert settings.mortgage.fees.model_dump()["insurance_calculation_method"] == "two_interval_weighted"
        assert settings.mortgage.fees.monthly_fixed_fees == Decimal("0")
        assert settings.mortgage.fees.insurance_end_month is None

    def test_settings_when_dotenv_exists_expect_nested_file_values(self, tmp_path: Path) -> None:
        """Load grouped values from an explicit dotenv file."""
        # Arrange
        env_file = tmp_path / ".env"
        env_file.write_text(
            "MS_SCENARIOS__BASELINE_NAME=Configured baseline\n"
            "MS_SCENARIOS__CONFIG_PATH=data/config/dotenv-scenarios.json\n"
            "MS_MORTGAGE__PRINCIPAL=450000\n"
            "MS_CHARTS__FOCUS_ON_TYPICAL_PAYMENTS=true\n",
            encoding="utf-8",
        )

        # Act
        settings = _settings(env_file=env_file)

        # Assert
        assert settings.scenarios.baseline_name == "Configured baseline"
        assert settings.scenarios.config_path == Path("data/config/dotenv-scenarios.json")
        assert settings.mortgage.principal == Decimal("450000")
        assert settings.charts.focus_on_typical_payments is True

    def test_settings_when_process_environment_and_dotenv_exist_expect_environment_precedence(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Prefer process-environment values over dotenv values."""
        # Arrange
        env_file = tmp_path / ".env"
        env_file.write_text("MS_SCENARIOS__BASELINE_NAME=Dotenv baseline\n", encoding="utf-8")
        monkeypatch.setenv("MS_SCENARIOS__BASELINE_NAME", "Environment baseline")

        # Act
        settings = _settings(env_file=env_file)

        # Assert
        assert settings.scenarios.baseline_name == "Environment baseline"

    def test_settings_when_complete_dotenv_exists_expect_domain_terms_conversion(self, tmp_path: Path) -> None:
        """Convert every configurable mortgage assumption into required domain terms."""
        # Arrange
        env_file = tmp_path / ".env"
        env_file.write_text(
            "MS_MORTGAGE__FIRST_PAYMENT_DATE=2025-04-18\n"
            "MS_MORTGAGE__INTEREST_CALCULATION_METHOD=equal_months\n"
            "MS_MORTGAGE__PRINCIPAL=450000\n"
            "MS_MORTGAGE__CONTRACTUAL_TERM_MONTHS=240\n"
            "MS_MORTGAGE__ANALYSIS_HORIZON_MONTHS=120\n"
            "MS_MORTGAGE__SETTLE_REMAINING_PRINCIPAL_AT_HORIZON=false\n"
            "MS_MORTGAGE__ANNUAL_RATE_MONTHS_1_60=0.06\n"
            "MS_MORTGAGE__ANNUAL_RATE_MONTHS_61_120=0.09\n"
            "MS_MORTGAGE__SUBSIDY__ENABLED=false\n"
            "MS_MORTGAGE__SUBSIDY__COEFFICIENT_MONTHS_1_60=0.08\n"
            "MS_MORTGAGE__SUBSIDY__REFERENCE_RATE=0.03\n"
            "MS_MORTGAGE__FEES__ANNUAL_FIXED_FEE=650\n"
            "MS_MORTGAGE__FEES__MONTHLY_INSURANCE_RATE=0.0005\n"
            "MS_MORTGAGE__FEES__INSURANCE_CALCULATION_METHOD=midpoint_balance\n"
            "MS_MORTGAGE__FEES__MONTHLY_FIXED_FEES=12\n"
            "MS_MORTGAGE__FEES__INSURANCE_END_MONTH=48\n",
            encoding="utf-8",
        )

        # Act
        terms = _settings(env_file=env_file).to_mortgage_terms()

        # Assert
        assert terms.first_payment_date == date(2025, 4, 18)
        assert terms.model_dump()["interest_calculation_method"] == "equal_months"
        assert terms.principal == Decimal("450000")
        assert terms.contractual_term_months == 240
        assert terms.analysis_horizon_months == 120
        assert terms.settle_remaining_principal_at_horizon is False
        assert terms.rate_periods == (
            RatePeriod(start_month=1, end_month=60, annual_rate=Decimal("0.06")),
            RatePeriod(start_month=61, end_month=120, annual_rate=Decimal("0.09")),
        )
        assert terms.subsidy.enabled is False
        assert terms.subsidy.coefficient == Decimal("0.08")
        assert terms.subsidy.reference_rate == Decimal("0.03")
        assert terms.fees.annual_fixed_fee == Decimal("650")
        assert terms.fees.monthly_insurance_rate == Decimal("0.0005")
        assert terms.fees.model_dump()["insurance_calculation_method"] == "midpoint_balance"
        assert terms.fees.monthly_fixed_fees == Decimal("12")
        assert terms.fees.insurance_end_month == 48

    def test_settings_when_process_rate_overrides_dotenv_expect_native_precedence(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Apply source precedence to each scalar rate before conversion."""
        # Arrange
        env_file = tmp_path / ".env"
        env_file.write_text(
            "MS_MORTGAGE__ANNUAL_RATE_MONTHS_1_60=0.06\nMS_MORTGAGE__ANNUAL_RATE_MONTHS_61_120=0.09\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("MS_MORTGAGE__ANNUAL_RATE_MONTHS_1_60", "0.065")

        # Act
        terms = _settings(env_file=env_file).to_mortgage_terms()

        # Assert
        assert terms.rate_periods[0].annual_rate == Decimal("0.065")
        assert terms.rate_periods[1].annual_rate == Decimal("0.09")

    def test_settings_when_only_one_scalar_rate_exists_expect_validation_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Require explicit fixed-period rates to be configured together."""
        # Arrange
        monkeypatch.setenv("MS_MORTGAGE__ANNUAL_RATE_MONTHS_1_60", "0.06")

        # Act / Assert
        with pytest.raises(ValidationError, match="both fixed-period annual rates"):
            _settings(env_file=None)

    @pytest.mark.parametrize(
        "legacy_key",
        [
            "MORTGAGE_SIMULATOR_BASELINE_NAME",
            "MORTGAGE_SIMULATOR_MORTGAGE_TERMS__PRINCIPAL",
            "MORTGAGE_SIMULATOR_MORTGAGE_TERMS__RATE_PERIODS",
        ],
    )
    def test_settings_when_legacy_environment_key_exists_expect_migration_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        legacy_key: str,
    ) -> None:
        """Reject every key under the previous environment prefix."""
        # Arrange
        monkeypatch.setenv(legacy_key, "1")

        # Act / Assert
        with pytest.raises(ValueError, match=r"replace MORTGAGE_SIMULATOR_.* with MS_"):
            _settings(env_file=None)

    def test_settings_when_legacy_dotenv_key_exists_expect_migration_error(self, tmp_path: Path) -> None:
        """Reject previous-prefix keys read from dotenv files."""
        # Arrange
        env_file = tmp_path / ".env"
        env_file.write_text("MORTGAGE_SIMULATOR_BASELINE_NAME=Old baseline\n", encoding="utf-8")

        # Act / Assert
        with pytest.raises(ValueError, match=r"replace MORTGAGE_SIMULATOR_.* with MS_"):
            _settings(env_file=env_file)

    def test_settings_when_legacy_constructor_field_exists_expect_migration_error(self) -> None:
        """Reject the previous flat constructor interface with migration guidance."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="scenarios"):
            AppSettings.model_validate({"baseline_name": "Old baseline"})

    def test_settings_when_unknown_constructor_field_exists_expect_validation_error(self) -> None:
        """Reject misspelled or unsupported constructor fields."""
        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            AppSettings.model_validate({"unsupported": True})

    def test_settings_when_null_scalar_exists_expect_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Parse the configured null token as None."""
        # Arrange
        monkeypatch.setenv("MS_MORTGAGE__FEES__INSURANCE_END_MONTH", "null")

        # Act
        settings = _settings(env_file=None)

        # Assert
        assert settings.mortgage.fees.insurance_end_month is None

    def test_settings_when_default_dotenv_is_absent_expect_fallbacks(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Start normally when the configured default dotenv file is absent."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        # Act
        settings = AppSettings()

        # Assert
        assert settings.mortgage.principal == Decimal("500000")


def _settings(*, env_file: Path | None) -> AppSettings:
    return AppSettings(  # type: ignore[call-arg]  # Pydantic's generated signature omits runtime settings keywords.
        _env_file=env_file
    )
