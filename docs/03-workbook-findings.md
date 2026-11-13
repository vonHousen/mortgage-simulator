# Reference workbook findings

## Purpose

The local reference workbook records the behavior that the first simulator version translated into typed Python. It
is a development and regression source, not a runtime dependency or authoritative documentation of current mortgage
or subsidy rules.

The workbook itself remains under the Git-ignored `data/` directory. Detailed source values, worksheet identities,
and cached results are retained in the private maintainer notes described in the
[documentation index](README.md#model-and-evidence).

## Relevant behaviors

The workbook established the main V1 behaviors:

- equal-principal scheduled payments;
- two fixed interest-rate periods over a ten-year analysis horizon;
- a monthly mortgage subsidy calculated separately from interest;
- balance-based insurance and fixed fees;
- a baseline plus recurring and lump-sum overpayment scenarios;
- duplicated scenario worksheets that should instead use one calculation path with different scenario data.

The application keeps those concepts configurable and applies every scenario through the same simulation engine.
Authoritative application defaults live in [`settings.py`](../src/mortgage_simulator/settings.py); the implemented
model lives in [`simulation/models.py`](../src/mortgage_simulator/simulation/models.py) and
[`simulation/mortgage_schedule.py`](../src/mortgage_simulator/simulation/mortgage_schedule.py).

## Intentional divergences

The simulator corrects or makes explicit several workbook limitations:

- principal payments are capped at the outstanding balance;
- annual fees are charged on their due months instead of spread evenly across the year;
- calendar-day and equal-month interest are both available, with equal-month interest retained for workbook parity;
- remaining principal can be settled at the analysis horizon so scenarios repay equal principal;
- spreadsheet assumptions are not presented as verified current law or a complete bank contract.

Exact parity behavior is enforced by the local suite described in
[Excel regression testing](04-regression-testing.md). The implementation does not include the workbook's separate
investment-product analysis.
