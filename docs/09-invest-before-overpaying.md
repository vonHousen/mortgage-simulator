# Invest before overpaying

## What this compares

Use this feature to answer: **Should I overpay X PLN now, or invest that same capital and overpay later?**
A custom mortgage scenario can contain several deposits. Each deposit uses its balance, including after-tax interest,
to fund a balloon repayment. Recurring overpayments and other lump sums continue alongside them.

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

Use **Edit investment** or **Remove investment** on an individual entry. Resolve investment assignments if you
rename or remove the associated scenario. One single-deposit entry per scenario may use automatic timing.

To compare manually, create scenarios with identical mortgage overpayments and investment inputs, changing only
**Terms before repayment**: zero for immediate repayment, one for the first maturity, two for one renewal, and so on.
Automatic mode performs this timing comparison within one scenario; the term-count input is disabled in that mode.

## Example: up-front and monthly deposits together

Use mortgage terms with an analysis horizon of at least **36 months**. The amounts and rates below are illustrative.

1. On **Overpayment scenarios**, add a scenario named **Up-front and monthly deposits**. Select **Fixed overpayment**,
   enter **1,000 PLN**, and set **Starting month** to **1**.
2. Select **Add investment**, choose that scenario and **Single deposit**, then enter **100,000 PLN**, start month
   **1**, a **6%** gross annual rate, and a **3-month** term. Select **Manual**, enter **1** term, and apply.
3. Select **Add investment** again, choose the same scenario and **Monthly deposits**, then enter **1,000 PLN**
   per deposit, start month **1**, **12** monthly openings, a **10%** gross annual rate, and a **12-month** term.
   Enter **2** terms before repayment to renew each deposit once. The preview shows openings in months **1–12**
   and planned payouts in months **25–36**. Apply and run the simulation.
4. Check the monthly mortgage schedule for recurring overpayments and the up-front deposit's payout in month **4**,
   if the mortgage is still open. In **Investment outcome**, follow each monthly deposit by entry and opening
   month. Check its first maturity in the term ledger and its repayment and surplus in the deposit outcomes table.

Use a monthly series for two or more planned openings. The contribution period controls how many deposits open. The term length controls how long each deposit runs
before earning interest, and the term count controls how many times that same balance rolls over before payout.
If the mortgage pays off early, new monthly deposits and renewals stop. Deposits already open finish their current
term and you retain their unused proceeds. Money earmarked for future monthly contributions stays in cash.

See the [equivalent CLI request](11-cli-simulations.md#example-mix-up-front-and-monthly-deposits).

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
terms before repayment changes. Any other entries keep their configured inputs. Each candidate is ranked using
its own actual deposit openings, renewals, repayments, and combined net earnings.

For opening month `T`, term length `M`, and analysis horizon `H`, candidates are all integer counts from zero through
`floor((H - T) / M)`, inclusive. Count zero means immediate overpayment; positive counts target month `T + count × M`.
For example, `T = 1`, `M = 3`, and `H = 12` produces counts 0, 1, 2, and 3: repayment months 1, 4, 7, and 10.

For each candidate, the evaluator projects the deposit payouts and calculates the resulting mortgage schedule.
Its payoff month determines which deposits actually open and which renewals complete. A deposit whose current term
finishes after payoff returns its balance as retained surplus.

Candidates are sorted by Net financing cost, effective completion month, and planned term count, in that order.
The first candidate is recommended; the others remain available for inspection and CSV download. Manual mode uses
the same calculations for just the selected count.

The search guarantees the lowest Net financing cost among these eligible candidates under the configured assumptions.
It does not search different capital amounts, opening dates, rates, term lengths, products, or partial repayments,
or model discounted household wealth. Net investment earnings enter the objective once; retained surplus is shown
separately and is not deducted again.

The search evaluates one automatic entry within the supported horizon. Its size is `floor((H - T) / M) + 1`; the authoritative
horizon limit lives in [`simulation/models.py`](../src/mortgage_simulator/simulation/models.py). Each candidate requires
one mortgage schedule and the term calculations for its configured deposits. Candidate enumeration and selection live in
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

Existing mortgage payments are applied first, then monthly deposit payouts, single-deposit payouts, and any
terminal horizon settlement. Payouts within either deposit group use configuration order. Each payment is capped
at the remaining balance.

- If 102,444.76 PLN is available but only 80,000 PLN of debt remains after other payments, 80,000 PLN repays the
  mortgage and 22,444.76 PLN remains as retained surplus.
- If other payments clear the mortgage during a deposit term, that term finishes at its selected maturity, but no
  further renewal starts. All remaining deposit funds are retained.
- If other payments clear the mortgage exactly at maturity, no deposit funds are needed for repayment and no renewal
  starts. Payoff on or before the opening month leaves the initial capital uninvested.

## JSON configuration

Each scenario can use an `investments` list. Existing configurations using the singular `investment` key also
load. For a list that combines single and monthly deposits, see the [CLI example](11-cli-simulations.md#example-mix-up-front-and-monthly-deposits).

This example seeds three equivalent capital allocations with different repayment timings:

```json
{
  "scenarios": [
    {
      "name": "Repay immediately",
      "investments": [{
        "initial_amount": "100000.00",
        "start_month": 1,
        "annual_rate": "0.06",
        "term_months": 3,
        "mode": "manual",
        "term_count": 0
      }]
    },
    {
      "name": "Renew once then repay",
      "investments": [{
        "initial_amount": "100000.00",
        "start_month": 1,
        "annual_rate": "0.06",
        "term_months": 3,
        "mode": "manual",
        "term_count": 2
      }]
    },
    {
      "name": "Optimize timing",
      "investments": [{
        "initial_amount": "100000.00",
        "start_month": 1,
        "annual_rate": "0.06",
        "term_months": 3,
        "mode": "automatic"
      }]
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
