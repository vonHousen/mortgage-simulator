# Invest before overpaying

## What this compares

Use this feature to answer: **Should I overpay X PLN now, or invest that same capital and overpay later?**
A deposit belongs to a custom mortgage scenario. Its entire balance, including interest after tax, funds a balloon
repayment. Existing recurring overpayments and balloons continue alongside it.

Useful comparisons include:

- immediate repayment versus one deposit term;
- repayment at the first maturity versus renewing for several terms;
- automatic selection of the repayment timing with the lowest Net financing cost;
- investing more than the remaining mortgage requires, with the unused amount retained.

These are fixed-rate analytical scenarios. Renewal rates are assumed unchanged, not forecast. The examples below
are illustrative inputs, not application defaults or bank offers.

## Using the app

1. Save the shared mortgage assumptions, including the analysis horizon.
2. On **Overpayment scenarios**, create the custom scenario rows you want to compare.
3. In **Invest before overpaying**, choose **Add investment** and select its scenario.
4. Enter initial capital, investment start month, annual gross rate, and deposit term in months.
5. Choose **Manual** and enter the number of terms, or choose **Automatic** to compare eligible timings.
6. Choose **Apply investment**, then **Run simulation**. Apply or cancel pending edits before running.
7. On Results, select the scenario and inspect **Investment outcome**. Automatic results include a recommended
   timing and the other candidates. Download the investment ledger and repayment candidates separately from the
   mortgage schedule CSV.

Use **Edit investment** to change applied settings or **Remove investment** to detach them. A scenario has at most
one investment. Resolve investment assignments if you rename or remove the associated scenario.

To compare manually, create scenarios with identical mortgage overpayments and investment inputs, changing only
**Terms before repayment**: zero for immediate repayment, one for the first maturity, two for one renewal, and so on.
Automatic mode performs this timing comparison within one scenario; the term-count input is disabled in that mode.

## Timing and interest

Months refer to mortgage payment numbers. Opening at month T with term M and N terms gives a planned repayment at
`T + N × M`. For example, opening in month 1 with a three-month term matures in month 4, then month 7 after renewal.
Zero terms means repayment in month T without earning interest. Start and planned manual maturity must fit the
analysis horizon; automatic mode includes zero terms and every full-term maturity inside that horizon.

Interest is simple within each term, including multi-year terms:

```text
Gross deposit interest = opening deposit balance × annual gross rate × term months / 12
```

Gross deposit interest is rounded half-up to grosze. The taxable base and 19% interest tax are rounded upward to grosze.
Tax is deducted at each maturity; renewal reinvests principal plus net interest. There is no compounding within a
term, early withdrawal, daily-accrual model, or changing renewal rate. The authoritative implementation is
[`investment/schedule.py`](../src/mortgage_simulator/simulation/investment/schedule.py).

### Example: repay now, after three months, or after six months

For illustrative capital of 100,000 PLN, an annual gross rate of 6%, and a three-month term starting in month 1:

| Timing | Repayment month | Gross deposit interest this term | Tax this term | Available balance |
| --- | --- | --- | --- | --- |
| Immediate | 1 | 0.00 PLN | 0.00 PLN | 100,000.00 PLN |
| First maturity | 4 | 1,500.00 PLN | 285.00 PLN | 101,215.00 PLN |
| Second maturity | 7 | 1,518.23 PLN | 288.47 PLN | 102,444.76 PLN |

The second maturity has cumulative net earnings of 2,444.76 PLN. The available balance is applied to the mortgage,
up to the remaining debt. Whether waiting reduces Net financing cost depends on the mortgage terms, subsidy, and fees;
the deposit balance alone does not determine the winner.

### Example: a three-year deposit

For 100,000 PLN at 6% annually over one 36-month term, Gross deposit interest is 18,000 PLN, tax is 3,420 PLN, and the final
balance is 114,580 PLN. Starting in month 1 gives maturity in month 37. This is one simple-interest term, not three
annual compounding events.

## How automatic optimization works

Automatic mode uses **exhaustive search (brute force)** over eligible deposit term counts. It keeps initial capital,
opening month, annual gross rate, term length, and existing mortgage payments fixed; only the planned number of
terms before repayment changes.

For opening month `T`, term length `M`, and analysis horizon `H`, candidates are all integer counts from zero through
`floor((H - T) / M)`, inclusive. Count zero means immediate overpayment; positive counts target month `T + count × M`.
For example, `T = 1`, `M = 3`, and `H = 12` produces counts 0, 1, 2, and 3: repayment months 1, 4, 7, and 10.

The evaluator first calculates the mortgage without investment funds to identify payoff caused by other payments.
For each candidate, it calculates deposit maturities, tax, and renewals, then calculates the mortgage with the
available deposit balance added as a balloon. If other payments have already paid off the mortgage, no additional
mortgage calculation is needed for that candidate. Early payoff stops renewals as described below.

Candidates are sorted by Net financing cost, effective completion month, and planned term count, in that order.
The first candidate is recommended; the others remain available for inspection and CSV download. Manual mode uses
the same calculations for just the selected count.

The search guarantees the lowest Net financing cost among these eligible candidates under the configured assumptions.
It does not search different capital amounts, opening dates, rates, term lengths, products, or partial repayments,
or model discounted household wealth. Net investment earnings enter the objective once; retained surplus is shown
separately and is not deducted again.

The search space is small within the supported horizon. Its size is `floor((H - T) / M) + 1`; the authoritative
horizon limit lives in [`simulation/models.py`](../src/mortgage_simulator/simulation/models.py). Each candidate requires
at most one mortgage schedule and up to its selected number of deposit terms, making exhaustive comparison practical
without a heuristic optimizer. Candidate enumeration and selection live in
[`investment/evaluation.py`](../src/mortgage_simulator/simulation/investment/evaluation.py).

## Reading the comparison

**Net financing cost = Total mortgage cost − Net investment earnings** is the primary decision metric. Automatic
mode minimizes this value, breaking ties by earliest effective completion month and then fewer planned terms.
**Total mortgage cost = Gross mortgage interest − Subsidy received + Fees paid** remains visible separately.
**Net investment earnings = Gross deposit interest − Deposit tax** accounts for the direct value of the deposit.

On Results, **Cost indicators** shows these three metrics together. Investment outcome reports Gross deposit interest,
Deposit tax, the amount applied to the mortgage, retained surplus, and maturity details. The automatic recommendation
shows Net financing savings versus immediate repayment; the scenario comparison page instead uses the no-overpayment
Baseline as its reference.

Earnings already form part of the repayment balance. They are deducted once in Net financing cost; do not deduct
retained surplus or the balloon amount again. If horizon settlement is disabled, compare Ending balance alongside
costs because repayment may be incomplete. See [Understanding the metrics](10-understanding-metrics.md) for formulas,
worked examples, the distinction between principal and financing charges, and comparison assumptions.

## Early payoff and surplus

Existing mortgage payments are applied first, then the investment-funded balloon, then any terminal horizon
settlement. The balloon is capped at the remaining balance.

- If 102,444.76 PLN is available but only 80,000 PLN of debt remains after other payments, 80,000 PLN repays the
  mortgage and 22,444.76 PLN remains as retained surplus.
- If other payments clear the mortgage during a deposit term, that term finishes at its selected maturity, but no
  further renewal starts. All remaining deposit funds are retained.
- If other payments clear the mortgage exactly at maturity, no deposit funds are needed for repayment and no renewal
  starts. Payoff on or before the opening month leaves the initial capital uninvested.

## JSON configuration

This complete example seeds three equivalent capital allocations with different repayment timings:

```json
{
  "scenarios": [
    {
      "name": "Repay immediately",
      "investment": {
        "initial_amount": "100000.00",
        "start_month": 1,
        "annual_rate": "0.06",
        "term_months": 3,
        "mode": "manual",
        "term_count": 0
      }
    },
    {
      "name": "Renew once then repay",
      "investment": {
        "initial_amount": "100000.00",
        "start_month": 1,
        "annual_rate": "0.06",
        "term_months": 3,
        "mode": "manual",
        "term_count": 2
      }
    },
    {
      "name": "Optimize timing",
      "investment": {
        "initial_amount": "100000.00",
        "start_month": 1,
        "annual_rate": "0.06",
        "term_months": 3,
        "mode": "automatic"
      }
    }
  ]
}
```

JSON rates are fractions (`0.06`); the UI shows percentages (`6`). Manual mode requires `term_count`; automatic mode
requires it to be omitted or null. These examples require a horizon that includes the specified repayment months.

See [Local scenario configuration](08-local-scenario-configuration.md) for selecting the file and loading behavior.
JSON seeds a fresh session and is not updated by UI edits. Schema and validation are defined in
[`simulation/models.py`](../src/mortgage_simulator/simulation/models.py); environment defaults remain authoritative in
[`settings.py`](../src/mortgage_simulator/settings.py).
