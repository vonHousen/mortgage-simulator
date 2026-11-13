# Mortgage Simulator documentation

This directory contains the product context, implemented design, financial-model rationale, validation guidance, and
architecture decisions for Mortgage Simulator. Start with the [root README](../README.md) to run or develop the app.

## Start here

| Document | Purpose |
| --- | --- |
| [Project brief](01-project-brief.md) | Explains the problem, intended audience, product direction, and principles. |
| [V1 design](02-design.md) | Defines the implemented architecture, calculation behavior, interfaces, and UI workflow. |

## Model and evidence

| Document | Purpose |
| --- | --- |
| [Reference workbook findings](03-workbook-findings.md) | Summarizes the workbook behaviors translated into the simulator and the intentional divergences. |
| [Calendar-day mortgage interest](05-calendar-day-mortgage-interest.md) | Explains the calendar-day interest convention and schedule boundaries. |
| [Monthly-insurance research](07-monthly-insurance-calculation-research.md) | Summarizes the compared insurance strategies, selected approximation, and limitations. |

Some numbered documents have a private companion covering the same subject. The tracked document is the maintained,
publication-safe summary; its Git-ignored `docs/private/` companion preserves exact source values and provenance for
maintainers who possess the corresponding local artifacts. Private documents are not required to run the application.

## Validation

| Document | Local artifact | Private manifest | Purpose |
| --- | --- | --- | --- |
| [Excel regression testing](04-regression-testing.md) | Local reference workbook | `data/regression/excel.json` | Checks equal-month parity with the reference workbook. |
| [Calendar regression testing](06-calendar-regression-testing.md) | Reviewed payment schedule | `data/regression/calendar.json` | Checks calendar-day calculations against the reviewed schedule. |
| [Monthly-insurance research](07-monthly-insurance-calculation-research.md) | Reviewed charge series | `data/regression/insurance.json` | Checks all supported insurance strategies against the reviewed charges. |

The artifacts and manifests are private, Git-ignored inputs. GitHub Actions runs `just ci` without them; maintainers
run `just e2e-regression-tests` locally with all three artifact-manifest pairs before merges and important commits.

## Configuration

[Local scenario configuration](08-local-scenario-configuration.md) explains optional scenario JSON, environment-backed
defaults, source precedence, and validation. Authoritative setting names and defaults live in
[`settings.py`](../src/mortgage_simulator/settings.py); domain validation lives in
[`simulation/models.py`](../src/mortgage_simulator/simulation/models.py).

## Architecture decisions

| ADR | Status | Decision |
| --- | --- | --- |
| [0001](adr/0001-stabilize-payment-composition-encoding.md) | Accepted | Stabilize payment-composition stack order and theme-based color mapping. |
| [0002](adr/0002-use-payment-date-interest-periods.md) | Accepted | Use payment dates to define calendar-day interest periods. |
| [0003](adr/0003-use-environment-backed-application-defaults.md) | Superseded by 0008 | Layer deployment and local defaults over reusable code fallbacks. |
| [0004](adr/0004-use-scalar-settings-for-fixed-rate-periods.md) | Superseded in part by 0008 | Configure the two UI rate periods with paired scalar settings. |
| [0005](adr/0005-use-local-json-for-scenario-defaults.md) | Superseded in part by 0008 | Seed editable scenarios from optional local JSON. |
| [0006](adr/0006-organize-source-by-responsibility.md) | Accepted | Organize the package around simulation, reporting, reference-data, and app boundaries. |
| [0007](adr/0007-adopt-ty-alongside-mypy.md) | Superseded in part by 0009 | Run ty alongside strict mypy checking. |
| [0008](adr/0008-centralize-environment-configuration.md) | Accepted | Centralize environment configuration under a grouped settings model. |
| [0009](adr/0009-share-pre-commit-checks-with-ci.md) | Accepted | Share pre-commit checks with local and hosted CI; run only ty before commits and both type checkers in CI. |
