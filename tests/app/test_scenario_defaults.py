"""Tests for optional local scenario defaults."""

from decimal import Decimal
from pathlib import Path

import pytest

import mortgage_simulator.app.scenario_defaults as config
from mortgage_simulator.settings import AppSettings, ScenarioConfig
from mortgage_simulator.simulation.models import LumpSum, OverpaymentScenario


class TestLoadLocalScenarios:
    """Tests for optional local overpayment-scenario defaults."""

    def test_config_when_file_is_missing_expect_empty_defaults(self, tmp_path: Path) -> None:
        """Treat an absent local scenario file as supported configuration."""
        # Arrange
        config_path = tmp_path / "data/config/scenarios.json"
        settings = _settings(env_file=None, scenario_config_path=config_path)

        # Act
        scenarios = config.load_local_scenarios(settings, settings.to_mortgage_terms())

        # Assert
        assert scenarios == ()

    def test_config_when_valid_expect_ordered_domain_scenarios(self, tmp_path: Path) -> None:
        """Parse nested recurring strategies and lump sums in input order."""
        # Arrange
        config_path = tmp_path / "data/config/scenarios.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            """
{
  "scenarios": [
    {
      "name": "Fixed plan",
      "recurring_amount": 1500,
      "recurring_start_month": 13,
      "lump_sums": [
        {"month": 24, "amount": 10000},
        {"month": 24, "amount": 5000}
      ]
    },
    {
      "name": "Target plan",
      "cash_outflow_target": 5000,
      "recurring_start_month": 1
    }
  ]
}
""",
            encoding="utf-8",
        )
        settings = _settings(env_file=None, scenario_config_path=config_path)

        # Act
        scenarios = config.load_local_scenarios(settings, settings.to_mortgage_terms())

        # Assert
        assert scenarios == (
            OverpaymentScenario(
                name="Fixed plan",
                recurring_amount=Decimal("1500"),
                recurring_start_month=13,
                lump_sums=(
                    LumpSum(month=24, amount=Decimal("10000")),
                    LumpSum(month=24, amount=Decimal("5000")),
                ),
            ),
            OverpaymentScenario(
                name="Target plan",
                cash_outflow_target=Decimal("5000"),
                recurring_start_month=1,
            ),
        )

    @pytest.mark.parametrize(
        ("document", "error_match"),
        [
            ("not-json", "Invalid JSON"),
            ("{}", "Field required"),
            ('{"scenarios":[{"name":"Plan","recurring_amunt":1000}]}', "recurring_amunt"),
            ('{"scenarios":[{"name":"Baseline"}]}', "scenario names must be unique"),
            ('{"scenarios":[{"name":"Plan"},{"name":"Plan"}]}', "scenario names must be unique"),
            ('{"scenarios":[{"name":"Plan","recurring_amount":-1}]}', "greater than or equal to 0"),
            (
                '{"scenarios":[{"name":"Plan","recurring_amount":1000,"cash_outflow_target":5000,'
                '"recurring_start_month":1}]}',
                "recurring amount and cash-outflow target cannot both be positive",
            ),
            (
                '{"scenarios":[{"name":"Plan","recurring_amount":1000,"recurring_start_month":121}]}',
                "recurring start month must be within the analysis horizon",
            ),
        ],
    )
    def test_config_when_invalid_expect_path_and_validation_error(
        self,
        tmp_path: Path,
        document: str,
        error_match: str,
    ) -> None:
        """Fail startup for malformed or incompatible local scenario defaults."""
        # Arrange
        config_path = tmp_path / "data/config/scenarios.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(document, encoding="utf-8")
        settings = _settings(env_file=None, scenario_config_path=config_path)

        # Act / Assert
        with pytest.raises(ValueError, match=error_match) as error:
            config.load_local_scenarios(settings, settings.to_mortgage_terms())
        assert str(config_path) in str(error.value)

    def test_config_when_path_is_unreadable_expect_file_error(self, tmp_path: Path) -> None:
        """Propagate file access failures instead of substituting empty defaults."""
        # Arrange
        config_path = tmp_path / "data/config/scenarios.json"
        config_path.mkdir(parents=True)
        settings = _settings(env_file=None, scenario_config_path=config_path)

        # Act / Assert
        with pytest.raises(IsADirectoryError):
            config.load_local_scenarios(settings, settings.to_mortgage_terms())


def _settings(
    *,
    env_file: Path | None,
    scenario_config_path: Path | None = None,
) -> AppSettings:
    if scenario_config_path is not None:
        return AppSettings(  # type: ignore[call-arg]  # Pydantic's generated signature omits runtime settings keywords.
            _env_file=env_file,
            scenarios=ScenarioConfig(config_path=scenario_config_path),
        )
    return AppSettings(  # type: ignore[call-arg]  # Pydantic's generated signature omits runtime settings keywords.
        _env_file=env_file
    )
