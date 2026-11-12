# Local scenario configuration

## Purpose

The Streamlit application can seed recurring overpayments and lump sums from an optional, untracked JSON file. Loaded
values initialize a new browser session and remain editable; the application never writes UI changes back to disk.

Mortgage assumptions and the baseline name remain environment-backed application settings. Scenario JSON does not
override them.

## Scenario file

The selected file contains a top-level `scenarios` array. Each item uses the fields defined by
[`OverpaymentScenario`](../src/mortgage_simulator/simulation/models.py), including its nested `LumpSum` values. The
top-level document and loading behavior are authoritative in
[`scenario_defaults.py`](../src/mortgage_simulator/app/scenario_defaults.py).

The default path and its environment override are defined in
[`settings.py`](../src/mortgage_simulator/settings.py). Relative paths resolve from the process working directory, so
use the documented commands from the repository root. The entire `data/` directory is Git-ignored and can hold
multiple local profiles.

Scenario files are private only while they remain on a private machine. A hosted application displays their scenario
names, amounts, and timing to its users, so do not deploy a personal scenario file to an instance that untrusted users
can access.

A missing selected file is supported and produces empty scenario editors. A malformed, unreadable, or invalid existing
file prevents startup. Scenario names and payment months are validated together with the active mortgage horizon, and
the baseline is added automatically.

## Environment-backed defaults

[`AppSettings`](../src/mortgage_simulator/settings.py) is the authoritative source for configuration groups, field
names, environment mapping, fallbacks, parsing, and source precedence. Settings use the `MS_` prefix and `__` between
nested field names. Previous `MORTGAGE_SIMULATOR_...` keys are rejected with migration guidance.

The committed fallbacks form a synthetic, non-personal example profile. Values supplied through a deployment `.env`
or process environment initialize visible mortgage inputs and affect visible results; treat them as user-visible
configuration rather than a place to store private financial assumptions.

Both fixed-period annual rates must be configured together. Percentage settings use decimal fractions, and the
literal `null` unsets optional values. Dynamic scenarios and their lump sums remain in the selected JSON file rather
than being encoded as environment values.

The chart-focus setting initializes a shared session toggle used on Results and Comparison; it does not lock the
user's selection. Focused charts reduce the visual effect of unusually large payments while retaining exact values in
tooltips, calculations, reports, tables, totals, and CSV exports. The current projection rules live in
[`mortgage_charts.py`](../src/mortgage_simulator/reporting/mortgage_charts.py).
