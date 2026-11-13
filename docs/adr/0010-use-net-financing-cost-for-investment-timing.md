# ADR 0010: Use net financing cost for investment timing

- Status: Accepted
- Date: 2026-11-13

## Context

Automatic deposit timing initially minimized Total mortgage cost: Gross mortgage interest minus Subsidy received plus
Fees paid. All net deposit earnings funded a balloon payment or remained as surplus. The larger balloon reduced future
mortgage charges, but the objective did not include the earnings themselves because principal repayments are excluded
from mortgage cost.

This could recommend immediate repayment even when investing generated earnings greater than the additional mortgage
charges incurred while waiting. The mortgage-only objective answered which timing minimized mortgage charges rather
than which timing minimized the combined financing cost of the mortgage and deposit.

## Decision

Use **Net financing cost = Total mortgage cost − Net investment earnings** as the primary decision metric and the
single automatic timing objective. Net investment earnings equal Gross deposit interest minus Deposit tax. Without an
investment, Net financing cost equals Total mortgage cost.

Retain exhaustive enumeration of eligible deposit term counts. Select the lowest Net financing cost, breaking ties
by earliest effective completion month and then fewer planned terms. Keep mortgage calculations, tax, renewal,
repayment caps, and existing payment order unchanged.

Keep Total mortgage cost as a separate metric. Label the existing cash-outflow total **Total mortgage payments**:
Principal repaid plus Gross mortgage interest minus Subsidy received plus Fees paid. Its underlying field name remains
unchanged. Use Gross mortgage interest and Gross deposit interest to distinguish the two sources of interest.

Make Net financing cost prominent alongside Total mortgage cost and Net investment earnings. Explain their formulas
in UI hints and [Understanding the metrics](../10-understanding-metrics.md).

## Consequences

- Automatic recommendations can change even though every manually selected timing produces the same mortgage and
  deposit calculations as before.
- Deposit earnings are deducted once, including earnings retained after payoff. Retained surplus is not deducted
  again because it can contain both original capital and already-counted earnings.
- Repayment of borrowed principal is shown as a payment, not a financing charge. Remaining debt remains visible for
  partial-horizon comparisons.
- Negative Net financing cost is valid: modeled deposit earnings exceed mortgage financing charges.
- Comparisons assume the same starting capital and a shared horizon. Values are nominal, without discounting or
  additional returns on retained funds or money freed after payoff.
- Mortgage-only regression references and underlying payment/CSV field names remain unchanged.

## Alternatives considered

### Continue minimizing Total mortgage cost

This preserves the earlier recommendation behavior but ignores the direct financial value of deposit earnings.
Mortgage-only cost remains useful for explaining charges, but it is not the investment decision objective.

### Minimize Total mortgage payments

This includes principal and deposit-funded balloon amounts. A larger repayment can increase this total while reducing
remaining debt, so it cannot by itself identify a better financing outcome.

### Add an objective selector

This would support both interpretations, but would ask users to select between objectives where the product question
is whether to invest or repay now. A single primary metric with visible components is easier to interpret.

### Model personal contributions or discounted household wealth

This would require separate funding flows, valuation timing, discounting, and assumptions about reinvesting money
freed by payoff. Those are outside the nominal financing comparison implemented here.
