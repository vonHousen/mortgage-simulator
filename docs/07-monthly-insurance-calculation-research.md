# Monthly-insurance calculation research

## Purpose

The simulator supports several ways to estimate monthly balance-insurance charges. The alternatives were compared
against a short reviewed charge series because the original workbook formula did not reproduce every observed charge.
The private source data and detailed empirical results remain Git-ignored.

## Supported strategies

The engine supports opening-balance, midpoint-balance, and two-interval-weighted insured balances. Their authoritative
definitions are implemented in
[`monthly_insurance.py`](../src/mortgage_simulator/simulation/monthly_insurance.py), and the available model values live
in [`simulation/models.py`](../src/mortgage_simulator/simulation/models.py).

The two-interval-weighted method had the best fit to the reviewed series. It uses adjacent balances and payment-period
lengths, but it remains a best-effort approximation rather than a verified contractual bank formula. Users can select
any supported method in Mortgage setup; the current application selection lives in
[`settings.py`](../src/mortgage_simulator/settings.py).

## Regression

The local suite protects the private artifact identity and enforces reviewed residual limits for every supported
strategy. The expected artifact and `data/regression/insurance.json` manifest paths are defined by the
[`regression-insurance` Just recipe](../Justfile). The manifest owns artifact identity, expected installments, the
monthly rate, and strategy limits; the tracked test contains only generic residual calculations.

Run it independently or with every private-data suite:

```bash
just regression-insurance
just e2e-regression-tests
```

Artifact identities, formulas, exclusions, and limits are governed inputs. Changing them requires explicit agreement
covering the requirement change, why the current regression contract is no longer correct, and the exact approved
restoration action. An approved source change updates the private source record and manifest together.

## Limitations

The model does not establish a bank's accounting cutoff, daily rounding policy, internal precision, or annual
reconciliation behavior. Only the relevant contractual calculation clause could replace the selected approximation
with an authoritative rule.
