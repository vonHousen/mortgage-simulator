# ADR 0002: Use Payment-Date Interest Periods

## Status

Accepted

## Context

The calendar-day engine previously estimated each interest period from the number of days in a displayed calendar
month. A reviewed repayment schedule demonstrated that the contractual daily rule must use consecutive payment dates,
including a split at New Year.

## Decision

`MortgageTerms.first_payment_date` is the single schedule anchor. It accepts days 1
through 28. Installment `m` occurs `m - 1` months after the anchor. Calendar-day interest accrues over the half-open
interval from the same day in the preceding month through the exact payment date.

The calculation uses contractual Actual/Actual daily accrual. Each calendar-year segment uses 365 or 366 as
appropriate, and New-Year-crossing periods are split. The installment-month annual rate and opening balance apply to
the complete period; principal changes follow the interest calculation. Values retain full `Decimal` precision.

The monthly subsidy remains a separate one-twelfth calculation. Equal-month interest remains isolated for Excel
parity and continues to use annual rate divided by 12. The authoritative implementation lives in
[`mortgage/calendar.py`](../../src/mortgage_simulator/simulation/mortgage/calendar.py), while the private artifact identity,
fixture assumptions, comparisons, and exclusions are enforced by
[`test_calendar_parity.py`](../../tests/regression/test_calendar_parity.py).

## Consequences

Schedules, reports, charts, tables, and exported scenario CSV use `payment_date` instead of an artificial calendar
month. The default calendar-day results change; equal-month Excel results do not.

All three ignored reference artifacts are mandatory for `just e2e-regression-tests`. That command and `just ci` must
run before every merge and important commit. Any parity failure blocks the action. Reference values, hashes,
tolerances, exclusions, formulas, or expected results may change only with explicit user agreement stating the
requirement change, why current parity is wrong, and the exact action approved to restore every affected suite.
