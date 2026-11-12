# Excel regression testing

## Purpose

The Excel regression suite checks that the equal-month simulation remains a faithful translation of the reviewed
reference workbook. It complements unit tests, which verify formulas and edge cases independently of private source
data.

## Public and private boundary

The workbook and `data/regression/excel.json` are private, Git-ignored development inputs. Their expected paths and the
command that guards them are defined by the [`regression-excel` Just recipe](../Justfile). The manifest owns artifact
identity, terms, scenarios, worksheet mappings, comparisons, exclusions, accepted differences, and tolerances; the
tracked tests contain only generic regression mechanics.

Detailed source identity, worksheet mapping, and cached financial values remain in ignored maintainer documentation.
The application never reads the workbook at runtime.

## Commands

Run CI-safe checks without private artifacts:

```bash
just ci
```

Run workbook parity, or all three local end-to-end suites:

```bash
just regression-excel
just e2e-regression-tests
```

The recipe fails explicitly when either its artifact or manifest is absent. GitHub Actions runs `just ci` and skips
private suites without both inputs; maintainers with every reviewed artifact-manifest pair run
`just e2e-regression-tests` before merges and important commits.

## Controlled updates

Reference values, hashes, tolerances, exclusions, formulas, and expected results are governed regression inputs. They
must not change merely to make a failure pass. Any change requires explicit agreement that records the requirement
change, why current parity is no longer correct, and the exact approved action for restoring every affected suite.

When an approved source changes, review formula changes separately from cached-value changes, retain the previous
artifact until its replacement is identified, update the private source record and manifest together, and run both
`just ci` and `just e2e-regression-tests`.
