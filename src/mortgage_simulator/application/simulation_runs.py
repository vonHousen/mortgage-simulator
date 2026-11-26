"""Resolve, execute, and export reproducible headless comparisons."""

import json
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import ValidationError

from mortgage_simulator.application.models import BASELINE_NAME, ComparisonInput, RunReport, ScenarioOutcome
from mortgage_simulator.reporting.investment_schedules import investment_candidates_frame, investment_ledger_frame
from mortgage_simulator.reporting.payment_schedules import schedule_csv
from mortgage_simulator.reporting.scenario_comparison import compare
from mortgage_simulator.settings import AppSettings, mortgage_terms_draft
from mortgage_simulator.simulation.engine import simulate
from mortgage_simulator.simulation.models import MortgageTerms, OverpaymentScenario, SimulationRequest, SimulationResult


def export_profile(output: Path) -> Path:
    """Freeze current application settings as complete mortgage terms.

    Args:
        output: New JSON profile destination; parent directories must exist.

    Returns:
        Profile path after successful export.
    """
    terms = AppSettings().to_mortgage_terms()
    with output.open("x", encoding="utf-8") as destination:
        destination.write(terms.model_dump_json(indent=2) + "\n")
    return output


def draft_profile(env_file: Path, output: Path) -> list[str]:
    """Save explicitly supplied terms and report missing or invalid fields.

    Args:
        env_file: Dotenv file with the starting mortgage settings.
        output: New JSON draft path.

    Returns:
        Dotted field paths needing review, or ``terms`` for a cross-field error.
    """
    draft = mortgage_terms_draft(env_file)
    fields_needing_attention = []
    try:
        MortgageTerms.model_validate(draft, extra="forbid")
    except ValidationError as error:
        fields_needing_attention = [
            ".".join(map(str, issue["loc"])) or "terms" for issue in error.errors(include_input=False)
        ]
    with output.open("x", encoding="utf-8") as destination:
        destination.write(json.dumps(draft, indent=2) + "\n")
    return fields_needing_attention


def validate_profile(profile: Path) -> MortgageTerms:
    """Load complete mortgage terms from a JSON profile.

    Args:
        profile: Existing JSON profile or edited draft.

    Returns:
        Validated mortgage terms.
    """
    return MortgageTerms.model_validate_json(profile.read_text(encoding="utf-8"), extra="forbid")


def input_schema(kind: str) -> dict[str, Any]:
    """Return an authoritative JSON input schema.

    Args:
        kind: Either ``profile`` or ``request``.

    Returns:
        Generated Pydantic JSON schema.
    """
    if kind == "profile":
        return MortgageTerms.model_json_schema()
    if kind == "request":
        return ComparisonInput.model_json_schema()
    raise ValueError("schema kind must be profile or request")


def resolve_request(request: Path, profile: Path | None = None) -> SimulationRequest:
    """Merge explicit terms with an optional profile and validate all scenarios.

    Args:
        request: Comparison JSON containing overrides and custom scenarios.
        profile: Complete mortgage terms; omitted for a self-contained request.

    Returns:
        Validated effective terms and custom scenarios, excluding the baseline.
    """
    supplied = ComparisonInput.model_validate_json(request.read_text(encoding="utf-8"), extra="forbid")
    if any(scenario.name == BASELINE_NAME for scenario in supplied.scenarios):
        raise ValueError(f"scenario name {BASELINE_NAME!r} is reserved for the automatic baseline")
    base = validate_profile(profile).model_dump(mode="json") if profile is not None else {}
    terms = MortgageTerms.model_validate(_merge_objects(base, supplied.terms), extra="forbid")
    return SimulationRequest(terms=terms, scenarios=supplied.scenarios)


def run_comparison(request: Path, output: Path, profile: Path | None = None) -> RunReport:
    """Run a complete baseline comparison and export detailed artifacts.

    Args:
        request: Comparison JSON or a previous resolved request.
        output: New output directory, with an existing parent directory.
        profile: Optional saved terms supplying fields absent from the request.

    Returns:
        Summaries, comparisons, and artifact paths after every export succeeds.
    """
    if output.exists():
        raise FileExistsError(f"output directory already exists: {output}")
    resolved = resolve_request(request, profile)
    scenarios = (OverpaymentScenario(name=BASELINE_NAME), *resolved.scenarios)
    results = tuple(simulate(resolved.terms, scenario) for scenario in scenarios)
    exports = _csv_exports(results)
    artifacts = {
        "resolved_request": output / "resolved-request.json",
        "results": output / "results.json",
        **{name.removesuffix(".csv").replace("-", "_"): output / name for name in exports},
    }
    report = RunReport(
        results=tuple(
            ScenarioOutcome.model_validate(
                result.model_dump(exclude={"payments"}) | {"net_financing_cost": result.net_financing_cost}
            )
            for result in results
        ),
        comparison=compare(results),
        artifacts=artifacts,
    )
    output.mkdir()
    artifacts["resolved_request"].write_text(resolved.model_dump_json(indent=2) + "\n", encoding="utf-8")
    for name, contents in exports.items():
        (output / name).write_text(contents, encoding="utf-8")
    artifacts["results"].write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return report


def _merge_objects(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = base.copy()
    for key, value in overrides.items():
        previous = merged.get(key)
        merged[key] = (
            _merge_objects(previous, value) if isinstance(previous, dict) and isinstance(value, dict) else value
        )
    return merged


def _csv_exports(results: tuple[SimulationResult, ...]) -> dict[str, str]:
    exports = {"mortgage-schedules.csv": schedule_csv(results)}
    for filename, projection in (
        ("investment-ledger.csv", investment_ledger_frame),
        ("investment-candidates.csv", investment_candidates_frame),
    ):
        frames = [frame for result in results if not (frame := projection(result)).is_empty()]
        if frames:
            exports[filename] = pl.concat(frames).write_csv()
    return exports
