# Calendar-day mortgage regression testing

## Purpose

The calendar regression compares the payment-date engine with a reviewed repayment schedule. It is an end-to-end
local parity check, separate from formula-level unit tests and equal-month workbook regression.

## Public and private boundary

The transcribed schedule and `data/regression/calendar.json` are private, Git-ignored inputs. Their expected paths and
command are defined by the [`regression-calendar` Just recipe](../Justfile). The manifest owns artifact identity,
expected rows, immutable terms, scenario identity, and tolerances; the tracked test contains only generic schema and
comparison mechanics.

Detailed source descriptions and financial values remain in ignored maintainer documentation.

## Commands and CI behavior

```bash
just regression-calendar
just e2e-regression-tests
```

The individual command fails explicitly when its artifact or manifest is absent. `just e2e-regression-tests` requires
all three artifact-manifest pairs. `just ci` and GitHub Actions skip private suites without both inputs.

## Controlled updates

Reference values, hashes, tolerances, exclusions, formulas, and expected results are governed regression inputs. They
must not change merely to make a failure pass. Any change requires explicit agreement that records the requirement
change, why current parity is no longer correct, and the exact approved action for restoring every affected suite.

After approval, retain the previous artifact until its replacement is identified and reviewed, update the private
source record and manifest together, then run both `just ci` and `just e2e-regression-tests`.
