# Mortgage Simulator

Mortgage Simulator is a decision-support app for comparing how mortgage overpayment strategies affect cash flow,
mortgage cost, payoff timing, and remaining principal.

## What it does

The Streamlit workflow lets you:

- configure shared mortgage terms, rates, subsidy behavior, fees, and the analysis horizon;
- compare a no-overpayment baseline with fixed overpayments, constant-cash-outflow strategies, and lump sums;
- inspect scenario totals, baseline-relative differences, payoff timing, charts, and monthly schedules;
- download all calculated schedules as a combined CSV.

The model uses equal-principal payments and supports an analysis horizon of up to 120 months. It started as a typed,
testable translation of a Polish subsidized-mortgage workbook, but it does not verify current BK2% rules, eligibility,
or the terms of a specific bank contract. Results are estimates for scenario exploration, not financial or legal
advice.

## Run the app

Requirements:

- [uv](https://docs.astral.sh/uv/)
- [Just](https://just.systems/)

Python is installed and selected by uv from `.python-version`. From the repository root, run:

```bash
just run
```

The normal application does not require a `.env` file or anything under the Git-ignored `data/` directory. Its
committed fallbacks are a synthetic, non-personal example profile rather than the terms of a real mortgage. Optional
environment defaults and reusable local scenarios are documented in
[Local scenario configuration](docs/08-local-scenario-configuration.md).

Treat deployment `.env` and scenario files as user-visible configuration: a hosted instance exposes the mortgage
assumptions and scenarios loaded from them through its interface and generated results. Do not deploy private values
to an instance that untrusted users can access.

## Development

Development also requires [lychee](https://github.com/lycheeverse/lychee), available on macOS with
`brew install lychee`. Install it using your platform's package manager before running the shared checks.

Install the locked development environment, enable commit hooks, and run the same checks as GitHub Actions:

```bash
just sync
just hooks-install
just ci
```

Git commits run the shared pre-commit bundle on staged files. `just pre-commit` runs that bundle on all tracked
files; `just ci` runs it locally (including lychee), followed by mypy and pytest. The bundle validates the uv lockfile,
runs Ruff lint and formatting plus ty, validates YAML/TOML, checks for conflict markers and private keys, and cleans
up whitespace and final newlines. Lychee checks local documentation links offline; external websites are not checked.

Ruff applies safe lint fixes and formatting automatically. Whitespace hooks also apply fixes; when hooks modify
files, the run fails so you can review and stage the changes before retrying. This behavior is the same in CI.
`just lint` also applies safe fixes. Use `just pre-commit lychee` to run only the link checker, or `just typecheck`
to run both mypy and ty. All Python checks use the versions in `uv.lock`; uv, Just, and lychee are external tools.
The shared bundle replaces the former `just format-check` command.

Use `just` to list all available recipes. Before merges and important commits, maintainers with the reviewed local
reference artifacts and matching private manifests must also run:

```bash
just e2e-regression-tests
```

That command runs the Excel, calendar, and monthly-insurance regression suites. Their source artifacts and manifests
live under the Git-ignored `data/` directory and are not distributed with the repository; missing inputs cause the
corresponding recipe to fail explicitly. See the [regression documentation](docs/README.md#validation) for the public
verification boundary and local paths.

### Code organization

The Python package is organized by responsibility:

```text
src/mortgage_simulator/
├── settings.py                         # Environment-backed application defaults
├── reference_data/
│   ├── excel_workbook_loader.py        # Development-only Excel reference adapter
│   └── regression_manifest_loader.py   # Development-only private manifest schemas
├── simulation/
│   ├── models.py                       # Validated inputs and immutable simulation results
│   ├── engine.py                       # Mortgage schedule calculation
│   └── monthly_insurance.py            # Selectable monthly-insurance calculations
├── reporting/
│   ├── scenario_comparison.py          # Baseline-relative summaries and comparison frames
│   ├── payment_schedules.py            # Schedule frames and CSV serialization
│   └── mortgage_charts.py              # Altair chart construction
└── app/
    ├── streamlit_app.py                # Streamlit entrypoint and navigation
    ├── scenario_defaults.py            # Optional local JSON scenario configuration
    ├── session_state.py                # Typed per-session application state
    ├── simulation_inputs.py            # UI input conversion and validation
    ├── app_pages/                      # Direct Streamlit page scripts
    └── presentation/                   # Shared result metrics and tables
```

Dependencies flow from `simulation` to `reporting` to `app`. The simulation package remains independent of the UI,
reporting tools, environment configuration, and local reference files. The maintained architectural boundaries and
public calculation interfaces are described in the [V1 design](docs/02-design.md) and
[source-organization ADR](docs/adr/0006-organize-source-by-responsibility.md).

## Documentation

Use the [documentation index](docs/README.md) to find the project brief, design, model research, regression guidance,
configuration reference, and architecture decisions.

## License

Mortgage Simulator is available under the [MIT License](LICENSE).
