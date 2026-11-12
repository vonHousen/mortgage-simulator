# 0005. Use local JSON for scenario defaults

## Status

Superseded in part by ADR 0008

[ADR 0008](0008-centralize-environment-configuration.md) replaces the settings path and environment-variable
convention described below. The decision to load session defaults from optional local JSON remains current.

## Context

ADR 0003 places shared application defaults under environment-backed `pydantic-settings` configuration, and ADR 0004
keeps the fixed UI rate periods scalar. This representation covers every mortgage assumption exposed by the setup UI
and the baseline name.

Overpayment scenarios are different: they form a dynamic, ordered collection, each scenario selects one recurring
strategy and may contain an ordered collection of lump sums. Re-entering the same local scenarios for every Streamlit
session is inconvenient, while representing the collection as environment variables would require complex encoded
values and weaken the scalar environment contract.

## Decision

Load optional scenario defaults from the Git-ignored path selected by `AppSettings.scenario_config_path` when the
Streamlit application starts. Configure the path through native `pydantic-settings` sources using
`MORTGAGE_SIMULATOR_SCENARIO_CONFIG_PATH`; retain `data/config/scenarios.json` as the code fallback. Use a
domain-oriented JSON object with a `scenarios` array of validated `OverpaymentScenario` values and nested `LumpSum`
values. The application adds the baseline separately.

Validate the complete collection against the environment-backed baseline name and startup mortgage horizon. Reject
malformed JSON, unknown fields, duplicate or baseline-colliding names, and invalid domain values. A missing file means
no scenario defaults; any invalid or unreadable existing file prevents startup.

Convert valid scenarios to the existing editor rows only when a new session initializes. UI edits remain session-local
and are never written back to the JSON file. Mortgage defaults and the baseline name retain the source precedence from
ADR 0003 and are not accepted in this file.

## Consequences

- Developers can keep repeatable personal scenarios without committing financial inputs.
- Developers can select among multiple local files without renaming or copying the active profile.
- JSON represents nested, ordered scenario data without exposing UI labels as a persistence contract.
- Environment and dotenv configuration remains scalar and continues to own shared mortgage defaults.
- Invalid local configuration fails visibly instead of silently starting with incomplete scenarios.
- Changes made in the UI must be copied to the local file manually when they should become future-session defaults.
