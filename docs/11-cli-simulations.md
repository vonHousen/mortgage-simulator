# Headless simulation workflow

Run comparisons through Just without starting Streamlit. An agent can use the repository's
[simulation skill](../.agents/skills/run-mortgage-simulation/SKILL.md) to translate a question into explicit inputs.
The CLI uses the same [financial model](02-design.md) and reporting functions as the UI.

## Start here for CLI QA

Run `just sync` from the checkout containing the CLI. Choose the mortgage terms based on what you are checking:

| QA task | Terms to use |
| --- | --- |
| Check a strategy on “my mortgage” | Pass the approved profile at `data/config/my-mortgage.json` in the main checkout, or an alternate profile the user explicitly selected. If the profile is missing or invalid, pause and ask about [setup or correction](#set-up-my-mortgage-from-env). |
| Smoke-test the CLI or a feature | Use a synthetic profile or put complete synthetic `terms` in the request. Personal setup is optional for synthetic checks. |
| Replay an earlier run | Use its `resolved-request.json` by itself. It already contains the complete terms and scenarios. |

For a smoke test, use `"scenarios": []` to check the baseline, then add a named scenario to check the behavior
under test. Run and replay into separate output directories. Verify the resolved terms, the scenario results and
baseline comparisons in `results.json`, and the relevant rows in `mortgage-schedules.csv`. Compare the result
values on replay because the artifact paths will differ. Keep local profiles, requests, and output under ignored `data/`.

## Prepare a profile

### Set up “my mortgage” from `.env`

Run the recipes from the checkout with the CLI. Locate the main checkout with
`git rev-parse --path-format=absolute --git-common-dir`; for a standard checkout, the main checkout is the parent of
the returned `.git` directory. Use the main checkout’s `.env` and reserve its ignored `data/config/my-mortgage.json`
as the approved profile. If the location cannot be resolved or the source is missing, ask for the intended file.

Create the ignored `data/config` directory in the main checkout, then use a fresh draft filename there. For example,
with `main_checkout` set to the absolute main checkout path:

```bash
just simulation-profile-draft "$main_checkout/.env" "$main_checkout/data/config/mortgage-draft.json"
just simulation-profile-validate "$main_checkout/data/config/mortgage-draft.json"
```

The draft reads literal mortgage assignments from the supplied file. Its JSON output reports
`fields_needing_attention` as dotted paths with zero-based array indexes. Ask about missing or invalid terms
and edit the draft with the answers. Use `just simulation-schema profile` for field types and
`simulation-profile-validate` for cross-field diagnostics. Review the resulting terms with the user. After the user
approves the validated draft, rename it to `my-mortgage.json` in the same directory. Refresh follows the same workflow,
with the existing file serving comparisons until the replacement is approved.

For “my mortgage,” use the approved absolute path from any linked worktree. Ask for setup or correction if the
file cannot be loaded and validated. Honor an explicitly requested alternate profile.

### Export the current application settings

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

The `scenarios` array is required. Use `"scenarios": []` to run only the automatically added no-overpayment baseline.
Its reserved name is defined by `BASELINE_NAME` in
[application contracts](../src/mortgage_simulator/application/models.py). Custom names must be unique.
Ask about missing material assumptions instead of silently guessing them.

For “invest X or pay it now?”, compare an immediate lump sum with an investment starting with the same amount
on the same payment date. Ask for missing assumptions such as the deposit rate and term. If the saved schedule
starts in the past, ask whether to use its modeled balance or wait for current terms. With permission, use the
first eligible installment on or after today and use its month index for both scenarios. Confirm the date and
read the modeled opening balance from the baseline row in `mortgage-schedules.csv`. If the installment's
eligibility is unclear or the baseline has no row for that date, clarify before reporting a comparison. Report the
balance source, payment date, and difference in Net financing cost between the two strategies.

## Example: mix up-front and monthly deposits

Save this request as `data/requests/mixed-deposits.json`. Use a saved mortgage profile with an analysis horizon of
at least 36 months. All amounts and rates are illustrative. This request matches the
[Streamlit example](09-invest-before-overpaying.md#example-up-front-and-monthly-deposits-together).

```json
{
  "scenarios": [
    {
      "name": "Up-front and monthly deposits",
      "recurring_amount": "1000",
      "recurring_start_month": 1,
      "investments": [
        {
          "initial_amount": "100000",
          "start_month": 1,
          "annual_rate": "0.06",
          "term_months": 3,
          "mode": "manual",
          "term_count": 1
        },
        {
          "initial_amount": "1000",
          "start_month": 1,
          "annual_rate": "0.10",
          "contribution_months": 12,
          "term_months": 12,
          "mode": "manual",
          "term_count": 2
        }
      ]
    }
  ]
}
```

```bash
mkdir -p data/runs
just simulate data/requests/mixed-deposits.json data/runs/mixed-deposits-001 data/config/my-mortgage.json
just simulate data/runs/mixed-deposits-001/resolved-request.json data/runs/mixed-deposits-002
```

Month 1 is the first mortgage payment month. The up-front deposit is due to pay out in month 4. The second entry
opens a fresh deposit per month for 12 months. Each of those deposits has two 12-month terms, so the first payout
is planned for month 25 and the last for month 36. After mortgage payoff, no new monthly deposits or renewals
start. Deposits in progress finish their terms and return unused proceeds as retained surplus.

Check `investment-deposits.csv` for capital, applied repayments, and retained surplus for each deposit. Its
`opening_month` is the planned opening month. Immediate repayment or earlier payoff can leave a single deposit
with no credited terms.
Use `investment-ledger.csv` to see each credited maturity, including renewals, and `mortgage-schedules.csv`
to see how the payouts and recurring overpayments affected the mortgage.

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
| `investment-ledger.csv` | Credited maturity rows, when any exist, tagged by scenario, entry, and opening month. |
| `investment-deposits.csv` | Individual deposit outcomes, including capital, earnings, repayment, and surplus. |
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
