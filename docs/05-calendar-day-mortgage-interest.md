# Calendar-day interest calculation for monthly mortgage payments

## Calculation rule

Calendar-day interest accrues daily on the current outstanding principal. Each day uses the actual number of days in
its calendar year as the denominator, so a period crossing New Year is split between the affected years. This is not
an Actual/365 Fixed or equal-month convention.

For a period during which principal and rate remain constant:

```text
period interest = principal × annual rate × sum(days in each calendar-year segment / days in that year)
```

The engine retains full `Decimal` precision and does not round daily or monthly interest. The implemented segmentation,
year handling, and schedule construction live in
[`simulation/mortgage_schedule.py`](../src/mortgage_simulator/simulation/mortgage_schedule.py), with edge cases covered by
[`test_engine.py`](../tests/simulation/test_engine.py).

## Interest-period boundaries

`first_payment_date` is the schedule anchor. Each installment advances that date by one month, and its interest period
is the half-open interval from the preceding payment boundary through the current payment date. The installment's
opening balance and applicable rate apply before that month's principal changes.

The validated date and horizon constraints are authoritative in
[`MortgageTerms`](../src/mortgage_simulator/simulation/models.py). A replacement schedule with different per-installment
payment dates would require a separate model rather than an implicit adjustment to this rule.

## Subsidy and equal-month behavior

The optional subsidy remains a separate monthly calculation; it does not change with the number of calendar days in
the interest period. Equal-month interest remains available as an explicit alternative for workbook parity. The
authoritative calculation order and formulas are implemented in
[`simulation/mortgage_schedule.py`](../src/mortgage_simulator/simulation/mortgage_schedule.py).

The reviewed payment-date behavior is protected by the local suite described in
[Calendar-day mortgage regression testing](06-calendar-regression-testing.md).
