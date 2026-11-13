"""Headless request resolution and execution."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from mortgage_simulator.application.simulation_runs import resolve_request, run_comparison
from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import OverpaymentScenario
from tests.factories import default_mortgage_terms


class TestResolveRequest:
    def test_when_nested_overrides_expect_retained_siblings_and_replaced_arrays(self, tmp_path: Path) -> None:
        # Arrange
        profile = tmp_path / "profile.json"
        profile.write_text(default_mortgage_terms().model_dump_json())
        request = tmp_path / "request.json"
        rates = [{"start_month": 1, "end_month": 120, "annual_rate": "0.065"}]
        request.write_text(
            json.dumps(
                {
                    "terms": {"fees": {"monthly_fixed_fees": "12.34"}, "rate_periods": rates},
                    "scenarios": [{"name": "Extra", "recurring_amount": "100", "recurring_start_month": 1}],
                }
            )
        )
        # Act
        resolved = resolve_request(request, profile)
        # Assert
        assert resolved.terms.fees.monthly_fixed_fees == Decimal("12.34")
        assert (
            resolved.terms.fees.insurance_calculation_method
            == default_mortgage_terms().fees.insurance_calculation_method
        )
        assert len(resolved.terms.rate_periods) == 1
        assert resolved.terms.rate_periods[0].annual_rate == Decimal("0.065")
        assert [scenario.name for scenario in resolved.scenarios] == ["Extra"]

    @pytest.mark.parametrize("scenarios", [[], [{"name": "Baseline"}], [{"name": "Same"}, {"name": "Same"}]])
    def test_when_invalid_scenarios_expect_validation_error(
        self, tmp_path: Path, scenarios: list[dict[str, str]]
    ) -> None:
        # Arrange
        request = tmp_path / "request.json"
        request.write_text(
            json.dumps({"terms": default_mortgage_terms().model_dump(mode="json"), "scenarios": scenarios})
        )
        # Act / Assert
        with pytest.raises(ValueError):
            resolve_request(request)


class TestRunComparison:
    def test_when_run_and_replay_expect_exact_summaries_and_baseline(self, tmp_path: Path) -> None:
        # Arrange
        request = tmp_path / "request.json"
        terms = default_mortgage_terms()
        scenario = OverpaymentScenario(name="Extra", recurring_amount=Decimal("1234.56"), recurring_start_month=1)
        request.write_text(
            json.dumps({"terms": terms.model_dump(mode="json"), "scenarios": [scenario.model_dump(mode="json")]})
        )
        output = tmp_path / "first"
        # Act
        report = run_comparison(request, output)
        replay = run_comparison(output / "resolved-request.json", tmp_path / "replay")
        # Assert
        assert [item.scenario_name for item in report.results] == ["Baseline", "Extra"]
        assert report.results[1].summary == simulate(terms, scenario).summary
        assert replay.results == report.results
        assert replay.comparison == report.comparison
        assert (output / "mortgage-schedules.csv").is_file()
        assert json.loads((output / "results.json").read_text())["results"][1]["summary"]["total_interest"] == str(
            report.results[1].summary.total_interest
        )

    def test_when_output_exists_expect_no_overwrite(self, tmp_path: Path) -> None:
        # Arrange
        output = tmp_path / "existing"
        output.mkdir()
        # Act / Assert
        with pytest.raises(FileExistsError):
            run_comparison(tmp_path / "missing.json", output)
