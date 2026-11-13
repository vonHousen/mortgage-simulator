# Mortgage Simulator — V1 Design

## Design intent

V1 reproduces the intentional behavior of a local reference workbook while moving the calculations into typed,
testable Python. The application compares a baseline with user-defined overpayment scenarios over a configurable
analysis horizon.

Detailed spreadsheet observations belong in [03-workbook-findings.md](03-workbook-findings.md). The parity process belongs in [04-regression-testing.md](04-regression-testing.md).

## Architecture

The package uses a one-way dependency flow:

```text
settings ─┐
          ├─> simulation ─> reporting ─> Streamlit app
scenario ─┘                         │
                                   └─> charts and CSV serialization
local workbook ─> reference-data adapter ─> regression tests
```

### Configuration

The package-root [`settings.py`](../src/mortgage_simulator/settings.py) is the single source of truth for application
configuration, including its groups, environment mapping, fallbacks, parsing, and source precedence. At startup,
`AppSettings.to_mortgage_terms()` converts configuration once into required, configuration-independent domain inputs.
The domain models in [`simulation/models.py`](../src/mortgage_simulator/simulation/models.py) own validation but no
application fallback values.

[`scenario_defaults.py`](../src/mortgage_simulator/app/scenario_defaults.py) separately loads optional, Git-ignored
JSON defaults into new sessions. Missing selected configuration is supported, while invalid existing configuration
prevents startup. Scenario JSON never overrides mortgage settings or the baseline name.

### Logic

[`simulation/engine.py`](../src/mortgage_simulator/simulation/engine.py) coordinates scenario evaluation. The shared mortgage calculator in
[`simulation/mortgage/schedule.py`](../src/mortgage_simulator/simulation/mortgage/schedule.py) operates on
`Decimal` values. The `simulation` package must not import Streamlit, Polars, Altair, openpyxl, or environment
configuration. It produces immutable typed monthly records and summaries.

### Data

[`reference_data/excel_workbook_loader.py`](../src/mortgage_simulator/reference_data/excel_workbook_loader.py) owns the
optional local workbook adapter. The workbook is a development reference, not a runtime dependency. Application
calculations must continue to work when `data/` is absent.

### Reporting

[`reporting/scenario_comparison.py`](../src/mortgage_simulator/reporting/scenario_comparison.py) calculates comparisons
and prepares their Polars projection.
[`reporting/payment_schedules.py`](../src/mortgage_simulator/reporting/payment_schedules.py) converts typed schedules
to Polars DataFrames and serializes CSV. Polars is not used inside the financial engine.

### Visualization

[`reporting/mortgage_charts.py`](../src/mortgage_simulator/reporting/mortgage_charts.py) creates chart-ready projections
from reporting output. It may provide Polars or Arrow-compatible data to Streamlit and Altair, but it must not
recalculate financial values or introduce pandas.

### Application

[`app/streamlit_app.py`](../src/mortgage_simulator/app/streamlit_app.py) is the Streamlit entrypoint. It orchestrates
input, validation, simulation, reporting, and rendering through direct scripts in `app/app_pages/`. UI code must not
duplicate domain formulas.

## Public interfaces

The calculation boundary is `simulate`, defined in
[`simulation/engine.py`](../src/mortgage_simulator/simulation/engine.py).

The baseline uses an `OverpaymentScenario` with no recurring payments, lump sums, or investment. Calling the same function for every scenario prevents separate baseline and overpayment code paths.

The reporting boundary is `compare`, defined in
[`reporting/scenario_comparison.py`](../src/mortgage_simulator/reporting/scenario_comparison.py).

Core input types:

- `MortgageTerms`: first payment date, principal, contractual term, analysis horizon, horizon-settlement option, rate periods, subsidy terms, and fee terms.
- `SubsidyTerms`: subsidy enablement, required first-period `coefficient`, required `second_coefficient`, and shared
  subsidized reference rate.
- `OverpaymentScenario`: unique name, either an optional fixed recurring amount or cash-outflow target with a start
  month, zero or more lump sums, and an optional `DepositInvestment`.
- `LumpSum`: payment month and amount.

`DepositInvestment` describes capital, start month, annual gross rate, term length, and manual or automatic timing.
Automatic investment timing uses exhaustive search over all full-term maturities inside the horizon, including
immediate overpayment, minimizing Net financing cost with completion-month and term-count tie-breaks.
The investment package evaluates deposit-funded balloon repayments through the same mortgage calculator; the mortgage
package contains no deposit calculations. Net financing cost equals Total mortgage cost minus Net investment earnings;
see [Understanding the metrics](10-understanding-metrics.md) and [ADR 0010](adr/0010-use-net-financing-cost-for-investment-timing.md).
See [the investment guide](09-invest-before-overpaying.md) for configuration and timing behavior.

Core result types:

- `MonthlyPayment`: month, exact payment date, opening balance, scheduled principal, recurring overpayment, lump sum, horizon settlement, interest, subsidy, monthly insurance, monthly fixed fees, annual fixed fee, aggregate fees, total cash outflow, and closing balance.
- `SimulationSummary`: totals, principal repaid before settlement, horizon settlement, ending balance, and optional payoff month.
- `SimulationResult`: scenario identity, ordered payments, summary, optional investment summary and candidates, and derived Net financing cost.
- `DepositTerm`, `InvestmentSummary`, and `InvestmentCandidate`: maturity ledger, earnings and funds disposition, and timing alternatives.
- `ComparisonReport`: all scenario summaries and deltas from the baseline.

The validated inputs and result records live in `simulation/models.py`; `simulate` lives in `simulation/engine.py`;
and `compare` lives in `reporting/scenario_comparison.py`. These public boundaries remain stable even when supporting
modules are reorganized.

## Calculation behavior

### Defaults

The code fallbacks provide a reusable profile; environment-specific assumptions belong in an untracked `.env` file
or the deployment environment. Authoritative fallback values and environment mapping live in
[`settings.py`](../src/mortgage_simulator/settings.py), while validation constraints live in
[`simulation/models.py`](../src/mortgage_simulator/simulation/models.py). They are not duplicated here.

### Monthly order

For month `m`:

1. Select the applicable annual mortgage rate from the month.
2. Calculate interest from the opening balance.
3. Calculate subsidy from the opening balance.
4. Calculate balance-based and fixed fees.
5. Determine scheduled principal, recurring overpayment, and lump sums for the month.
6. Apply principal in this order: scheduled principal, recurring overpayment, then lump sums in their input order.
7. Cap each component against the balance left for that month, so later components may be partially or entirely unused.
8. In the final horizon month, when horizon settlement is enabled, apply the exact remaining balance as a distinct terminal principal payment.
9. Calculate cash outflow and closing balance.
10. Stop after payoff or the configured analysis horizon, whichever occurs first.

Investment evaluation appends the deposit-funded balloon after existing lump sums, so it is applied before horizon settlement.

The scheduled monthly principal is `initial principal ÷ contractual term in months` because the workbook uses equal-principal installments.

A scenario may use one recurring strategy. Fixed overpayment applies the configured additional principal unchanged.
Constant cash outflow derives the month's requested recurring overpayment, starting inclusively in the configured
month, as:

```text
max(target − (scheduled principal + interest − subsidy + fees), 0)
```

The target therefore includes scheduled principal, net interest, balance-based insurance, monthly fixed fees, and the
annual fixed fee. Lump sums and horizon settlement remain additional cash outflow and are applied after the recurring
overpayment. A low target does not reduce scheduled costs: the overpayment is zero and base cash outflow may exceed
the target. In the payoff month, the remaining-balance cap may make cash outflow lower than the target.

`first_payment_date` is the single schedule anchor for calendar-day interest. Installment `m`
falls `m - 1` months after that date, and its interest period is the half-open interval from the same day in the
preceding month through its exact payment date:

```text
opening balance × applicable annual interest rate × Actual/Actual year fraction for [previous payment date, payment date)
```

Each segment uses 365 for days in an ordinary year and 366 for days in a leap year, so periods crossing New Year are
split. The installment-month annual rate and opening balance apply to the complete period before principal changes.
The selectable equal-month method preserves the workbook formula
`opening balance × applicable annual interest rate ÷ 12`. The contractual basis is detailed in
[05-calendar-day-mortgage-interest.md](05-calendar-day-mortgage-interest.md).

Monthly subsidy is:

```text
opening balance × (subsidy coefficient W − subsidized reference rate) ÷ 12
```

W is selected by payment month: `coefficient` applies in months 1–60 and `second_coefficient` in months 61–120.
The two coefficients are independent of contractual bank rates. The second-period application default is an editable
analytical assumption informed by the [second-period W outlook](bk2-info/second-period-w-outlook.md); authoritative
values and environment mapping remain in `settings.py`. Regression adapters explicitly use their manifest's
original coefficient for both periods, preserving reference expectations.

When subsidy calculations are disabled, the engine retains and validates the configured subsidy rates but returns an
exact zero subsidy for every payment. This raises base cash outflow and leaves less room for principal overpayment
under a constant-cash-outflow strategy.

Monthly insurance and fixed fees apply through the configured inclusive `insurance_end_month`. Monthly insurance
supports opening-balance, midpoint-balance, and two-interval-weighted
insured balances. The weighted method's empirical basis and limitations are documented in
[07-monthly-insurance-calculation-research.md](07-monthly-insurance-calculation-research.md). The workbook-parity
configuration explicitly uses its original opening-balance formula:

```text
opening balance × monthly insurance rate
+ monthly fixed fees
```

The engine charges the full annual fixed fee in month 1 and every twelfth month after it: months 1, 13, 25, and so on.
It is independent of `insurance_end_month`. The workbook instead spreads the annual fixed fee evenly across every
month. This is an intentional monthly-timing divergence: fee and cash-outflow comparisons adjust the workbook's
monthly share, while complete-year totals remain unchanged.

### Precision and payoff

Calculations retain `Decimal` precision and do not round daily or monthly interest to cents. Presentation formats PLN
to two decimal places. CSV output contains stable decimal representations suitable for further analysis.

Unlike workbook scenario #2, the engine never permits negative outstanding principal. When principal payments exceed the opening balance, the last month's principal components are capped and no later rows are generated.

Horizon settlement occurs immediately after the final regular horizon payment. It does not add another interest period, subsidy, or fee. When enabled, every scenario repays the original principal and ends with zero balance, so total-cash-outflow differences equal total-mortgage-cost differences. The model does not include an early-repayment charge, refinancing cost, inflation, opportunity cost, or constraints on funding the terminal payment.

### Validation

Validation fails before simulation when:

- principal, term, or horizon is not positive;
- the first payment date is outside day 1 through 28, has no representable preceding monthly boundary, or causes the
  analysis horizon to exceed Python's calendar range;
- the V1 horizon exceeds 120 months or the contractual term;
- rates or payment amounts are negative;
- either subsidy coefficient is lower than the subsidized reference rate, including when subsidies are disabled;
- an overpayment month lies outside the analysis horizon;
- both fixed recurring overpayment and cash-outflow target are positive in one scenario;
- a positive recurring amount or cash-outflow target has no valid start month, or a start month has neither value;
- scenario names are empty or duplicated;
- a lump sum refers to an unknown scenario.

Multiple lump sums for one scenario and month are valid and are applied in their input order.

Invalid input produces no partial comparison report.

## Streamlit workflow

The input area groups mortgage terms, interest calculation, subsidy assumptions, fees, and horizon. An exact first
payment date anchors calendar-day schedules, and equal months remains available for workbook comparison. A toggle
beside the analysis horizon controls terminal principal settlement. An always-visible toggle in Interest rates
controls BK2% subsidy calculations. Its detailed Subsidy assumptions expander is hidden when the subsidy is off,
while both stored W values and the reference rate remain unchanged. The expander places the two period-specific
W inputs side by side, with the shared reference rate below. Initial selections come from
[`settings.py`](../src/mortgage_simulator/settings.py). Saving mortgage terms invalidates previous simulation results.

A scenario editor supports multiple named scenarios with `name`, `strategy`, `recurring_value`, and `start_month`
fields. Each row chooses either Fixed overpayment or Constant cash outflow. A second editor assigns optional lump sums
by scenario and month. New sessions initialize both editors from optional local scenario defaults; later UI edits take
precedence for that session and are not written back to disk. A dedicated **Invest before overpaying** section attaches
one deposit to a custom scenario using Add, Edit, Remove, Apply, and Cancel controls. Pending investment edits must
be applied or cancelled before simulation. Submitting the form validates the entire run and then
calculates the baseline and all custom scenarios.

The results contain:

- summary metrics for Total mortgage payments, Principal repaid, Gross mortgage interest, subsidy, fees, Ending balance, and payoff month;
- a Cost indicators leading row with Net financing cost as the primary decision metric, followed by Total mortgage cost and Net investment earnings;
- supporting ratios and annualized-rate indicators below, with formula-based tooltips explaining their different purposes;
- conditional horizon-settlement indicators for principal repaid before settlement, the terminal amount, its share of original principal, and its reduction from the baseline;
- absolute and percentage deltas from the baseline;
- remaining-principal and monthly-cash-outflow comparison charts;
- a principal, horizon-settlement, interest, subsidy, and fee composition chart;
- a scenario-filtered monthly schedule;
- one combined mortgage CSV with a scenario column;
- investment earnings, applied repayment, retained surplus, maturity ledger, and automatic timing candidates with separate CSV downloads;
- an assumptions panel and non-advice statement.

Results and Comparison share a `Focus on typical payments` session toggle initialized from application settings. On
Results it focuses Monthly cash outflow and Payment composition; on Comparison it focuses Monthly cash outflow.
Focused mode applies terminal-payment and subsidy-mode
visibility first. Cash outflow uses the nearest-value 99th percentile across every displayed scenario as a common
y-axis ceiling, while composition uses the percentile of the selected scenario's monthly visible stack totals. Larger
marks are clamped to that edge while exact tooltip amounts and all non-chart outputs remain unchanged.

When subsidy is disabled, results use Gross mortgage interest terminology and omit subsidy metrics, comparison rows, chart
components, schedule columns, and CSV fields. Internal typed results retain zero-valued subsidy fields so calculation
and comparison schemas remain stable.

## Error handling

Pydantic validation errors are translated into concise field-level messages. A missing local scenario file is
supported, while a malformed, invalid, or unreadable existing scenario file prevents application startup. Missing
local workbook data affects only explicit regression commands, never application startup. Unexpected calculation
errors fail fast and are logged with exception context; the UI must not silently substitute values.

## Testing strategy

- Unit tests cover each formula, validation rule, period boundary, overpayment timing rule, payoff cap, and summary aggregation.
- Reporting tests assert Polars schemas, values, comparison deltas, sorting, and CSV columns.
- A Streamlit smoke test verifies that the entrypoint renders without an exception.
- The local Excel suite owns a complete immutable mortgage input fixture and does not inherit application settings
  before comparing the implementation with cached workbook outputs as described in
  [04-regression-testing.md](04-regression-testing.md).
- The local calendar suite owns a complete immutable mortgage input fixture and does not inherit application settings
  before comparing exact payment-date calculations with the reviewed bank schedule described in
  [06-calendar-regression-testing.md](06-calendar-regression-testing.md).
- The local insurance suite compares all three insured-balance strategies with the reviewed charge series and enforces
  the residual limits described in [07-monthly-insurance-calculation-research.md](07-monthly-insurance-calculation-research.md).
- Local and GitHub Actions CI run the shared pre-commit bundle (including ty and offline lychee), mypy, and pytest
  through `just ci`, as described in [ADR 0009](adr/0009-share-pre-commit-checks-with-ci.md).

## Implementation status

The V1 application implements this design. See the [documentation index](README.md) for current supporting material
and architecture-decision status.
