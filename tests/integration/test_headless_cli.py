"""Real executable and Just workflows across the headless stack."""

import csv
import json
import os
import subprocess
import sys
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mortgage_simulator.app.session_state import RESULTS_KEY, TERMS_KEY
from mortgage_simulator.application.models import RunReport
from mortgage_simulator.reporting.payment_schedules import schedule_csv
from mortgage_simulator.reporting.scenario_comparison import compare
from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import (
    DepositInvestment,
    InvestmentMode,
    LumpSum,
    OverpaymentScenario,
    SimulationResult,
)
from tests.factories import default_mortgage_terms

ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE = Path(sys.executable).with_name("mortgage-simulator")


class TestHeadlessCli:
    def test_when_dotenv_incomplete_expect_editable_profile_draft(self, tmp_path: Path) -> None:
        # Arrange
        source = tmp_path / "mortgage settings.env"
        source.write_text(
            "MS_MORTGAGE__PRINCIPAL=456789.12\n"
            "MS_MORTGAGE__ANNUAL_RATE_MONTHS_1_60=0.04\n"
            "MS_MORTGAGE__FEES__INSURANCE_END_MONTH=null\n"
            "MS_MORTGAGE__FEES__UNRELATED_SECRET=private\n"
            "MS_MORTGAGE__UNRELATED_SECRET=private\n"
            "UNRELATED_SECRET=private\n"
        )
        draft = tmp_path / "mortgage draft.json"
        environment = os.environ | {"MS_MORTGAGE__PRINCIPAL": "1", "MS_MORTGAGE__ANNUAL_RATE_MONTHS_61_120": "0.05"}

        # Act
        exported = _just("simulation-profile-draft", str(source), str(draft), env=environment)
        invalid = _just("simulation-profile-validate", str(draft))

        # Assert
        assert exported.returncode == 0, exported.stderr
        report = json.loads(exported.stdout)
        partial = json.loads(draft.read_text())
        assert partial["principal"] == "456789.12"
        assert partial["rate_periods"][0]["annual_rate"] == "0.04"
        assert "annual_rate" not in partial["rate_periods"][1]
        assert partial["fees"] == {"insurance_end_month": None}
        assert "private" not in draft.read_text()
        assert "rate_periods.1.annual_rate" in report["fields_needing_attention"]
        assert invalid.returncode != 0

        # Act
        complete = default_mortgage_terms(principal=Decimal(partial["principal"])).model_dump(mode="json")
        complete["rate_periods"][0].update(partial["rate_periods"][0])
        draft.write_text(json.dumps(complete))
        validated = _just("simulation-profile-validate", str(draft))
        request = _request_file(tmp_path, {}, _scenario("lump"))
        run = _just("simulate", str(request), str(tmp_path / "run"), str(draft))

        # Assert
        assert validated.returncode == 0, validated.stderr
        assert run.returncode == 0, run.stderr
        assert json.loads((tmp_path / "run" / "resolved-request.json").read_text())["terms"]["principal"] == "456789.12"

    def test_when_dotenv_uses_interpolation_expect_literal_draft_value_flagged(self, tmp_path: Path) -> None:
        # Arrange
        source = tmp_path / ".env"
        source.write_text("MS_MORTGAGE__PRINCIPAL=${MORTGAGE_TEST_PRINCIPAL}\nMS_MORTGAGE__FEES=invalid\n")
        draft = tmp_path / "draft.json"
        environment = os.environ | {"MORTGAGE_TEST_PRINCIPAL": "123456.78"}

        # Act
        exported = _cli("profile", "draft", "--env-file", str(source), "--output", str(draft), env=environment)

        # Assert
        assert exported.returncode == 0, exported.stderr
        assert {"principal", "fees"} <= set(json.loads(exported.stdout)["fields_needing_attention"])
        assert json.loads(draft.read_text())["principal"] == "${MORTGAGE_TEST_PRINCIPAL}"

    def test_when_scenarios_empty_expect_gui_baseline_and_replay(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("MS_SCENARIOS__CONFIG_PATH", str(tmp_path / "absent.json"))
        monkeypatch.setenv("MS_SCENARIOS__BASELINE_NAME", "Baseline")
        terms = default_mortgage_terms(analysis_horizon_months=12)
        request = tmp_path / "baseline.json"
        request.write_text(json.dumps({"terms": terms.model_dump(mode="json"), "scenarios": []}))
        output = tmp_path / "first"
        resolved_request = output / "resolved-request.json"
        gui = AppTest.from_file(ROOT / "src/mortgage_simulator/app/streamlit_app.py").run()
        gui.session_state[TERMS_KEY] = terms

        # Act
        gui.switch_page("app_pages/overpayment_scenarios.py").run()
        next(button for button in gui.button if button.label == "Run simulation").click().run()
        completed = _cli("run", "--request", str(request), "--output", str(output))

        # Assert
        assert not gui.exception
        assert not gui.error
        gui_results: tuple[SimulationResult, ...] = gui.session_state[RESULTS_KEY]
        assert completed.returncode == 0, completed.stderr
        report = RunReport.model_validate_json(completed.stdout)
        assert [result.scenario_name for result in report.results] == ["Baseline"]
        assert report.results[0].summary == gui_results[0].summary
        assert report.comparison == compare(gui_results)
        assert report.artifacts["mortgage_schedules"].read_text() == schedule_csv(gui_results)
        assert json.loads(resolved_request.read_text())["scenarios"] == []

        # Act
        replay = _cli("run", "--request", str(resolved_request), "--output", str(tmp_path / "replay"))

        # Assert
        assert replay.returncode == 0, replay.stderr
        replayed_report = RunReport.model_validate_json(replay.stdout)
        assert replayed_report.results == report.results
        assert replayed_report.comparison == report.comparison

    def test_when_mixed_investments_expect_gui_cli_and_replay_parity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("MS_SCENARIOS__BASELINE_NAME", "Baseline")
        terms = default_mortgage_terms(analysis_horizon_months=36)
        scenarios = [
            {
                "name": "Mixed investments",
                "recurring_amount": "1000",
                "recurring_start_month": 1,
                "investment": [
                    {
                        "initial_amount": "100000",
                        "start_month": 1,
                        "annual_rate": "0.05",
                        "term_months": 12,
                        "mode": "automatic",
                    },
                    {
                        "initial_amount": "1000",
                        "start_month": 1,
                        "annual_rate": "0.10",
                        "term_months": 12,
                        "term_count": 2,
                        "contribution_months": 12,
                    },
                ],
            }
        ]
        settings_file = tmp_path / "scenarios.json"
        settings_file.write_text(json.dumps({"scenarios": scenarios}))
        monkeypatch.setenv("MS_SCENARIOS__CONFIG_PATH", str(settings_file))
        request = tmp_path / "request.json"
        request.write_text(json.dumps({"terms": terms.model_dump(mode="json"), "scenarios": scenarios}))
        output = tmp_path / "first"

        # Act
        gui = AppTest.from_file(ROOT / "src/mortgage_simulator/app/streamlit_app.py").run()
        gui.session_state[TERMS_KEY] = terms
        gui.switch_page("app_pages/overpayment_scenarios.py").run()
        next(button for button in gui.button if button.label == "Run simulation").click().run()
        completed = _cli("run", "--request", str(request), "--output", str(output))

        # Assert
        assert not gui.error
        assert not gui.exception
        assert completed.returncode == 0, completed.stderr
        report = RunReport.model_validate_json(completed.stdout)
        gui_results: tuple[SimulationResult, ...] = gui.session_state[RESULTS_KEY]
        gui_mixed = gui_results[1]
        cli_mixed = report.results[1]
        assert cli_mixed.summary == gui_mixed.summary
        assert cli_mixed.investments == gui_mixed.investments
        assert cli_mixed.investment_totals == gui_mixed.investment_totals
        assert cli_mixed.investment_candidates == gui_mixed.investment_candidates
        assert cli_mixed.net_financing_cost == gui_mixed.net_financing_cost
        assert report.comparison == compare(gui_results)
        with report.artifacts["mortgage_schedules"].open() as stream:
            cli_schedule = list(csv.DictReader(stream))
        gui_schedule = list(csv.DictReader(StringIO(schedule_csv(gui_results))))
        for cli_row, gui_row in zip(cli_schedule, gui_schedule, strict=True):
            assert cli_row["scenario"] == gui_row["scenario"]
            assert cli_row["payment_date"] == gui_row["payment_date"]
            for column in cli_row.keys() - {"scenario", "payment_date"}:
                assert Decimal(cli_row[column]) == Decimal(gui_row[column])

        ledger_csv = report.artifacts["investment_ledger"]
        with ledger_csv.open() as stream:
            rows = list(csv.DictReader(stream))
        series_rows = [row for row in rows if row["investment_index"] == "2"]
        assert sorted(int(row["maturity_month"]) for row in series_rows) == list(range(13, 37))
        assert sorted({int(row["opening_month"]) for row in series_rows}) == list(range(1, 13))
        assert Decimal(series_rows[0]["opening_balance"]) == Decimal("1000")

        # Act
        resolved_request = output / "resolved-request.json"
        replay = _cli("run", "--request", str(resolved_request), "--output", str(tmp_path / "replay"))

        # Assert
        assert replay.returncode == 0, replay.stderr
        stored_investments = json.loads(resolved_request.read_text())["scenarios"][0]["investment"]
        assert len(stored_investments) == 2
        replayed_report = RunReport.model_validate_json(replay.stdout)
        assert replayed_report.results == report.results
        assert replayed_report.comparison == report.comparison
        assert replayed_report.artifacts["investment_ledger"].read_text() == ledger_csv.read_text()
        deposit_csv = report.artifacts["investment_deposits"]
        assert replayed_report.artifacts["investment_deposits"].read_text() == deposit_csv.read_text()

    def test_when_request_uses_legacy_investment_object_expect_resolved_list(self, tmp_path: Path) -> None:
        # Arrange
        terms = default_mortgage_terms(analysis_horizon_months=12)
        request = tmp_path / "legacy.json"
        output = tmp_path / "first"
        legacy_deposit = {
            "initial_amount": "1000",
            "start_month": 1,
            "annual_rate": "0.10",
            "term_months": 6,
            "term_count": 1,
        }
        request.write_text(
            json.dumps(
                {
                    "terms": terms.model_dump(mode="json"),
                    "scenarios": [{"name": "Legacy deposit", "investment": legacy_deposit}],
                }
            )
        )

        # Act
        completed = _cli("run", "--request", str(request), "--output", str(output))

        # Assert
        assert completed.returncode == 0, completed.stderr
        resolved = json.loads((output / "resolved-request.json").read_text())
        investments = resolved["scenarios"][0]["investment"]
        assert len(investments) == 1
        assert {field: investments[0][field] for field in legacy_deposit} == legacy_deposit
        report = RunReport.model_validate_json(completed.stdout)
        outcome = report.results[1].investment
        assert outcome is not None
        assert outcome.applied_repayment == Decimal("1040.50")

    @pytest.mark.parametrize("strategy", ["fixed", "target", "lump", "manual", "automatic"])
    def test_when_supported_strategy_expect_direct_engine_parity(self, tmp_path: Path, strategy: str) -> None:
        # Arrange
        terms = default_mortgage_terms(analysis_horizon_months=12)
        scenario = _scenario(strategy)
        request = _request_file(tmp_path, terms.model_dump(mode="json"), scenario)
        output = tmp_path / "results"
        # Act
        completed = _cli("run", "--request", str(request), "--output", str(output))
        # Assert
        assert completed.returncode == 0, completed.stderr
        actual = json.loads(completed.stdout)
        expected = simulate(terms, scenario)
        assert actual["results"][1]["summary"] == expected.summary.model_dump(mode="json")
        assert actual["results"][1]["net_financing_cost"] == str(expected.net_financing_cost)
        assert actual["comparison"]["scenarios"][1]["net_financing_cost_delta"] == str(
            expected.net_financing_cost - simulate(terms, OverpaymentScenario(name="Baseline")).net_financing_cost
        )
        assert actual["results"][1]["investment"] == (
            expected.investment.model_dump(mode="json") if expected.investment else None
        )
        assert json.loads((output / "results.json").read_text()) == actual
        assert (output / "mortgage-schedules.csv").read_text().splitlines()[1].startswith("Baseline,1,2024-01-01,")
        assert (output / "investment-ledger.csv").exists() == bool(expected.investment and expected.investment.terms)
        assert (output / "investment-candidates.csv").exists() == bool(expected.investment_candidates)
        if expected.investment_candidates:
            with (output / "investment-candidates.csv").open() as stream:
                candidates = list(csv.DictReader(stream))
            assert [row["net_financing_cost"] for row in candidates] == [
                str(candidate.net_financing_cost) for candidate in expected.investment_candidates
            ]

    def test_when_just_profile_run_replay_expect_environment_independence(self, tmp_path: Path) -> None:
        # Arrange
        profile = tmp_path / "mortgage profile.json"
        request = _request_file(tmp_path, {"analysis_horizon_months": 12}, _scenario("fixed"))
        output = tmp_path / "first run"
        replay_output = tmp_path / "replay run"
        environment = os.environ | {"MS_MORTGAGE__PRINCIPAL": "456789.12"}
        # Act
        exported = _just("simulation-profile-export", str(profile), env=environment)
        first = _just("simulate", str(request), str(output), str(profile))
        replayed = _just(
            "simulate",
            str(output / "resolved-request.json"),
            str(replay_output),
            env=environment | {"MS_MORTGAGE__PRINCIPAL": "1"},
        )
        schema = _just("simulation-schema", "request")
        # Assert
        assert exported.returncode == 0, exported.stderr
        assert first.returncode == 0, first.stderr
        assert replayed.returncode == 0, replayed.stderr
        assert schema.returncode == 0, schema.stderr
        assert json.loads(profile.read_text())["principal"] == "456789.12"
        assert json.loads(first.stdout)["results"] == json.loads(replayed.stdout)["results"]
        assert "scenarios" in json.loads(schema.stdout)["properties"]

    @pytest.mark.parametrize("contents", ["{", '{"scenarios": [{"name":"Baseline"}]}'])
    def test_when_invalid_request_expect_usage_error_without_artifacts(self, tmp_path: Path, contents: str) -> None:
        # Arrange
        request = tmp_path / "invalid.json"
        request.write_text(contents)
        output = tmp_path / "results"
        # Act
        completed = _cli("run", "--request", str(request), "--output", str(output))
        # Assert
        assert completed.returncode == 2
        assert completed.stdout == ""
        assert completed.stderr
        assert not output.exists()

    def test_when_existing_destination_expect_just_failure_without_overwrite(self, tmp_path: Path) -> None:
        # Arrange
        output = tmp_path / "existing"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_text("keep")
        # Act
        completed = _just("simulate", str(tmp_path / "absent.json"), str(output))
        # Assert
        assert completed.returncode != 0
        assert completed.stdout == ""
        assert "already exists" in completed.stderr
        assert sentinel.read_text() == "keep"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"fees": {"monthly_fixed_fee": "1"}},
            {"analysis_horizon_months": 121},
            {"rate_periods": [{"start_month": 2, "end_month": 120, "annual_rate": "0.05"}]},
        ],
    )
    def test_when_invalid_resolved_terms_expect_no_artifacts(
        self, tmp_path: Path, overrides: dict[str, object]
    ) -> None:
        # Arrange
        profile = tmp_path / "profile.json"
        profile.write_text(default_mortgage_terms().model_dump_json())
        request = _request_file(tmp_path, overrides, _scenario("fixed"))
        output = tmp_path / "results"
        # Act
        completed = _cli("run", "--profile", str(profile), "--request", str(request), "--output", str(output))
        # Assert
        assert completed.returncode == 2
        assert completed.stdout == ""
        assert not output.exists()

    def test_when_output_parent_missing_expect_filesystem_failure_without_success(self, tmp_path: Path) -> None:
        # Arrange
        request = _request_file(tmp_path, default_mortgage_terms().model_dump(mode="json"), _scenario("fixed"))
        output = tmp_path / "missing" / "results"
        # Act
        completed = _cli("run", "--request", str(request), "--output", str(output))
        # Assert
        assert completed.returncode == 1
        assert completed.stdout == ""
        assert completed.stderr
        assert not output.exists()

    def test_when_missing_input_expect_filesystem_error(self, tmp_path: Path) -> None:
        # Arrange / Act
        completed = _cli("run", "--request", str(tmp_path / "absent"), "--output", str(tmp_path / "results"))
        # Assert
        assert completed.returncode == 1
        assert completed.stdout == ""
        assert not (tmp_path / "results").exists()

    def test_when_streamlit_import_forbidden_expect_all_commands_work(self, tmp_path: Path) -> None:
        # Arrange
        guard = tmp_path / "sitecustomize.py"
        guard.write_text(
            "import sys\n"
            "class Guard:\n"
            " def find_spec(self, fullname, path=None, target=None):\n"
            '  if fullname == "streamlit" or fullname.startswith("streamlit."):\n'
            '   raise AssertionError("Streamlit forbidden")\n'
            "sys.meta_path.insert(0, Guard())\n"
        )
        environment = os.environ | {"PYTHONPATH": str(tmp_path)}
        profile = tmp_path / "profile.json"
        request = _request_file(tmp_path, {}, _scenario("fixed"))
        # Act
        commands = [
            _cli("--help", env=environment),
            _cli("schema", "profile", env=environment),
            _cli("schema", "request", env=environment),
            _cli("profile", "export", "--output", str(profile), env=environment),
            _cli(
                "run",
                "--profile",
                str(profile),
                "--request",
                str(request),
                "--output",
                str(tmp_path / "results"),
                env=environment,
            ),
        ]
        # Assert
        for completed in commands:
            assert completed.returncode == 0, completed.stderr


def _scenario(strategy: str) -> OverpaymentScenario:
    if strategy == "fixed":
        return OverpaymentScenario(name="Extra", recurring_amount=Decimal("1234.56"), recurring_start_month=1)
    if strategy == "target":
        return OverpaymentScenario(name="Target", cash_outflow_target=Decimal("6000"), recurring_start_month=1)
    if strategy == "lump":
        return OverpaymentScenario(name="Lump", lump_sums=(LumpSum(month=3, amount=Decimal("12000")),))
    mode = InvestmentMode(strategy)
    return OverpaymentScenario(
        name=strategy,
        investment=DepositInvestment(
            initial_amount=Decimal("12000"),
            start_month=1,
            annual_rate=Decimal("0.05"),
            term_months=3,
            mode=mode,
            term_count=2 if mode == InvestmentMode.MANUAL else None,
        ),
    )


def _request_file(directory: Path, terms: dict[str, object], scenario: OverpaymentScenario) -> Path:
    request = directory / "comparison request.json"
    request.write_text(json.dumps({"terms": terms, "scenarios": [scenario.model_dump(mode="json")]}))
    return request


def _cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(EXECUTABLE), *args], cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)


def _just(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["just", *args], cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
