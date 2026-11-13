# Understanding the metrics

## Which metric should drive the decision?

**Net financing cost is the primary decision metric. Lower is better.** It combines mortgage charges with deposit
earnings, so it answers whether investing first improves the financing outcome compared with overpaying immediately.
Automatic investment timing minimizes this metric, then prefers the earliest effective completion month and fewer
planned deposit terms. The decision is recorded in [ADR 0010](adr/0010-use-net-financing-cost-for-investment-timing.md).

The **Cost indicators** section puts Net financing cost next to its two components: Total mortgage cost and Net
investment earnings. The other metrics explain payments, remaining debt, and retained funds rather than replacing
the primary metric.

## Definitions

| Metric | Formula | What it tells you |
| --- | --- | --- |
| **Total mortgage payments** | **Principal repaid + Gross mortgage interest − Subsidy received + Fees paid** | Payments applied to the mortgage, including deposit-funded balloons and any horizon settlement, net of subsidy. This is not your personal cash contribution. |
| **Total mortgage cost** | **Gross mortgage interest − Subsidy received + Fees paid** | Mortgage financing charges, excluding repayment of the borrowed capital and excluding deposit earnings. |
| **Net investment earnings** | **Gross deposit interest − Deposit tax** | Earnings credited by the deposit after tax. These earnings are part of its final balance. |
| **Net financing cost** | **Total mortgage cost − Net investment earnings** | Combined financing cost after accounting for deposit earnings. Without an investment, this equals Total mortgage cost. |
| **Retained surplus** | **Final deposit balance − Applied to mortgage** | Deposit funds remaining after the mortgage repayment cap. This may include original capital as well as earnings. |

**Gross mortgage interest** is interest charged on the outstanding mortgage before subsidy. **Gross deposit interest**
is interest credited by the deposit before tax. **Principal repaid** is the borrowed amount returned through scheduled
payments, recurring overpayments, balloons, and horizon settlement. **Ending balance** is mortgage principal still
outstanding at the end of the modeled mortgage schedule.

**Net financing cost difference** means this scenario's Net financing cost minus Baseline's Net financing cost.
A negative difference means the scenario has lower net financing cost. Baseline is the no-overpayment scenario.
The leading **Difference from Baseline** metric is **Net financing cost saved**: Baseline Net financing cost minus
this scenario's Net financing cost. Positive means a saving, including deposit earnings.
The investment recommendation instead shows **Net financing savings versus immediate repayment**: the immediate
candidate's Net financing cost minus the recommended candidate's Net financing cost. A positive saving favors the
recommended timing. Both comparisons use the same cost formula, but their reference scenarios differ.

## Why principal repayment is not a financing charge

Suppose you borrow 100,000 PLN and repay 103,000 PLN without subsidy, fees, or investments. The principal repayment
returns the 100,000 PLN you borrowed. The remaining 3,000 PLN is Gross mortgage interest and therefore Total mortgage
cost. Total mortgage payments are 103,000 PLN; Net financing cost is 3,000 PLN.

Separating principal from charges prevents a larger repayment from being mistaken for a more expensive mortgage.
It also prevents treating borrowed capital as an extra financing charge. The principal remains visible in Principal
repaid and Ending balance, so it is not ignored when interpreting a partial-horizon result.

## Why deposit earnings change the comparison

Consider the following simplified, illustrative one-year comparison for the same 100,000 PLN: mortgage interest of
approximately 2% and a deposit at 10% gross, with 19% deposit tax. This isolates the contribution of that capital;
it is not a complete equal-principal mortgage schedule or an application default.

| Effect attributable to the capital | Overpay immediately | Invest, then overpay |
| --- | --- | --- |
| Additional mortgage charges while waiting | 0 PLN | Approximately 2,000 PLN |
| Gross deposit interest | 0 PLN | 10,000 PLN |
| Deposit tax | 0 PLN | 1,900 PLN |
| Net investment earnings | 0 PLN | 8,100 PLN |
| Net financing cost contribution | 0 PLN | Approximately −6,100 PLN |

Investing has higher Total mortgage cost during the waiting period, but lower Net financing cost by approximately
6,100 PLN. A mortgage-only objective would count the additional mortgage charges while missing the direct value of
the deposit earnings. The larger balloon may also save subsequent mortgage interest; those savings already enter
Total mortgage cost through the simulated schedule.

Subtracting Net investment earnings is not double-counting those subsequent interest savings: the earnings fund
principal repayment, while the mortgage calculation measures interest and fees saved because the debt is lower.
A negative Net financing cost means earnings exceed mortgage charges in the modeled period. It does not mean there
were no payments or that the mortgage provider paid you money.

## Does a negative cost mean the deposit earned money?

Yes, in the simulation. **Net investment earnings** reports the deposit interest actually credited after tax under
the configured assumptions. A negative **Net financing cost** means those earnings exceed **Total mortgage cost**.

For example, an illustrative result with Net investment earnings of **101,572.44 PLN** and Total mortgage cost of
**88,262.76 PLN** gives:

```text
Net financing cost = 88,262.76 PLN - 101,572.44 PLN = -13,309.68 PLN
```

The modeled deposit earnings exceed the mortgage charges by **13,309.68 PLN**. This is not necessarily cash left in
your account: the earnings form part of the deposit balance used to repay mortgage principal. Only **Retained
surplus** describes funds left after that repayment, and it may include your original capital as well as earnings.

A deposit can earn money even when Net financing cost is positive; in that case its earnings are smaller than the
mortgage charges. A negative cost alone also does not establish which timing is best: compare Net financing cost
between scenarios with the same starting capital and horizon.

These are modeled earnings, not guaranteed future returns. Renewals assume the configured deposit rate remains
available. Principal repayments still occur, and a negative cost does not mean the mortgage provider pays you.

## Remaining debt and retained funds

If horizon settlement is enabled, every scenario repays the original mortgage principal. If it is disabled, compare
Ending balance alongside Net financing cost: a partial-horizon result may leave significant debt to repay later.
The metric measures modeled charges and earnings, not affordability or a forecast beyond the horizon.

For a deposit starting with 100,000 PLN and earning 8,100 PLN after tax, the Final deposit balance is 108,100 PLN.
If only 80,000 PLN is needed for the mortgage, Retained surplus is 28,100 PLN. Net financing cost deducts the 8,100 PLN
of earnings once. It does not also deduct the 28,100 PLN surplus, which contains original capital and already-counted
earnings. Nor does it deduct the 80,000 PLN balloon as an extra saving.

Deposit funds satisfy this conservation identity:

```text
Initial capital + Net investment earnings = Applied to mortgage + Retained surplus
```

If other payments clear the mortgage during a term, that term finishes and its earnings count, but the deposit does
not renew again. The early-payoff rules are detailed in [Invest before overpaying](09-invest-before-overpaying.md).

## Comparison assumptions

Compare investment timings using the same initial capital, shared mortgage assumptions, and analysis horizon.
The model uses nominal amounts: it does not discount future cash flows, apply inflation, or assume additional returns
on retained funds or money freed after early mortgage payoff. It is therefore a comparison of the modeled financing
costs, not a complete investment portfolio or household cash-flow model.

The underlying field `total_cash_outflow` retains its name for compatibility; its UI label is Total mortgage payments.
Authoritative domain definitions live in [`simulation/models.py`](../src/mortgage_simulator/simulation/models.py).
For deposit configuration and the exhaustive timing search, see [Invest before overpaying](09-invest-before-overpaying.md).
