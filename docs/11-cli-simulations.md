# Headless simulation workflow

Run comparisons through Just without starting Streamlit. An agent can use the repository's
[simulation skill](../.agents/skills/run-mortgage-simulation/SKILL.md) to translate a question into explicit inputs.
The CLI uses the same [financial model](02-design.md) and reporting functions as the UI.

## Prepare a profile

Run commands from the repository root after `just sync`. Create local working directories:

```bash
mkdir -p data/config data/requests data/runs
just simulation-profile-export data/config/mortgage.json
```

Profile export freezes the current application settings into complete mortgage terms. Review those terms before using
it for a real comparison: unset settings produce the application's synthetic example profile. Settings and environment
precedence are documented in [local configuration](08-local-scenario-configuration.md). Existing profile files are not
overwritten. To export another profile, choose another destination.

A profile is a JSON representation of `MortgageTerms`, not the application's separate UI scenario-default file.
Profiles, requests, and results under `data/` are Git-ignored. Select a profile explicitly; if none is available or
several could apply, clarify which mortgage to model rather than choosing synthetic or unrelated terms.

## Describe strategies

Inspect the authoritative schemas rather than guessing field names:

```bash
just simulation-schema profile
just simulation-schema request
```

The profile schema defines mortgage terms; the request schema defines custom scenarios and accepts a `terms` object
containing either partial overrides or complete terms. Both derive from the code's Pydantic contracts. Existing domain
validation applies, including cross-field and horizon rules; unknown input fields are rejected.

For example, save this synthetic comparison request as `data/requests/comparison.json`:

```json
{
  "terms": {},
  "scenarios": [
    {"name": "Monthly extra", "recurring_amount": "2000", "recurring_start_month": 1},
    {"name": "One-off repayment", "lump_sums": [{"month": 12, "amount": "24000"}]}
  ]
}
```

These are illustrative strategy amounts, not application defaults. Monetary amounts and rates can be decimal strings;
rates are fractions, dates are ISO dates, and payment months are indexed from the first mortgage payment. The
[deposit guide](09-invest-before-overpaying.md) explains investment inputs and manual versus automatic timing.
Automatic deposit timing minimizes Net financing cost using the shared engine; the CLI does not introduce a general
strategy search. [Understanding the metrics](10-understanding-metrics.md) explains this objective and its interpretation.

At least one custom scenario is required. A no-overpayment baseline is added automatically; its reserved name is
defined by `BASELINE_NAME` in [application contracts](../src/mortgage_simulator/application/models.py).
Custom names must be unique. Ask about missing material assumptions instead of silently guessing them.

## Run and replay

```bash
just simulate data/requests/comparison.json data/runs/comparison-001 data/config/mortgage.json
just simulate data/runs/comparison-001/resolved-request.json data/runs/comparison-002
```

Arguments are request, new output directory, and optional profile, in that order. Quote paths containing spaces.
Parent directories must exist; existing output directories are rejected. Request `terms` override the profile by
recursively merging objects and replacing arrays in full. For example, overriding `fees.monthly_fixed_fees` preserves
other fee settings, while supplying `rate_periods` replaces the entire rate schedule. Invalid resolved terms fail
before simulation. Without a profile, all required mortgage terms must be present.

Runs never implicitly load `.env`, environment overrides, or the UI's scenario file. The resolved request contains
complete effective terms and custom scenarios, including scenario defaults; the automatic baseline is re-created on
replay. Changing environment settings after a run does not change replayed results.

## Read results

A successful command prints one JSON report to standard output and writes:

| Artifact | Content |
| --- | --- |
| `resolved-request.json` | Effective terms and custom scenarios for replay. |
| `results.json` | Scenario summaries, baseline-relative comparisons, investment outcomes and candidates, artifact paths. |
| `mortgage-schedules.csv` | All baseline and custom monthly payment records, including exact dates. |
| `investment-ledger.csv` | Credited maturity rows, when any exist, tagged by scenario. |
| `investment-candidates.csv` | Available timing candidates, when any exist, tagged by scenario and ranked by the engine. |

JSON uses decimal strings and ISO dates. The report omits monthly mortgage rows to keep the response compact; use the
CSV for detailed inspection. Investment CSVs preserve decimal strings, while the UI separately formats display values.
Artifact paths follow the supplied output path and resolve relative to the repository root when relative.

Lead with Net financing cost and its baseline delta, then explain mortgage cost, cash outflow, payoff timing, and
remaining debt. Net financing cost is taken from the shared model, including the deposit earnings adjustment; candidate
CSV exports include the same metric used by the automatic timing objective. Check the selected horizon
and whether terminal principal settlement is enabled; distinguish scheduled payoff from settlement at the horizon.
Report investment earnings, tax, applied repayment, and retained surplus separately from mortgage cost. Compare equal
funding assumptions when the user's question calls for them. Link the resolved request and relevant result artifacts.
For metric definitions, use [Understanding the metrics](10-understanding-metrics.md). For calculation assumptions and
limitations, refer to [the model design](02-design.md) and
[deposit interpretation](09-invest-before-overpaying.md).

## Failures and architecture

Diagnostics go to standard error. The executable exits with `2` for invalid input or usage and `1` for runtime or
filesystem errors. Just propagates failures as a nonzero exit status. No success JSON is printed on failure.
Validation and calculations complete before export starts; an export failure can leave an incomplete output directory,
which must not be treated as a successful run. Use a fresh directory when retrying.

The entrypoint is a thin Typer adapter; ordinary application services own resolution and execution. Just only forwards
arguments through `uv run`. Neither the CLI nor shared services imports or launches Streamlit. See
[ADR 0011](adr/0011-headless-simulation-interface.md) for responsibility boundaries and alternatives.
