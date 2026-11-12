# Second-period BGK indicator W: exploratory outlook

Research date: 12 November 2026.

## Purpose and scope

Provide provisional sensitivity inputs for the second five-year BK2 subsidy period. The estimate below concerns a reset around 2028–2029; the borrower's actual reset date has not been established. It is an analytical judgement, not a BGK forecast, a statistical confidence interval, or a guaranteed range.

For the calculation rules and research limitations, see the underlying Safe Mortgage 2% research (retained in the original planning worktree). W is separate from the borrower's contractual bank rate.

## Evidence checked

- BGK's notice dated 5 November 2026 sets W at **5.48% from 12 November 2026**. This supersedes the May 2026 value as the latest observation used for this outlook. [Official BGK notice page](https://www.bgk.pl/bip/komunikat-z-5112026/); [PDF accessed on the research date](https://www.bgk.pl/files/public/Pliki/bip/Mieszkanie_na_start/KOMUNIKAT_BIP.pdf). The generic PDF address may be reused for later notices; use the dated notice page to identify the observation.
- PKO BP's analysis dated 4 November 2026 reports an NBP reference rate of **3.75%**. Its central scenario sees no need for rate increases, while market pricing described in the report implies approximately **0.75 percentage points of increases by the end of 2027**. It also describes inflation and geopolitical risks. This is evidence of uncertainty about the rate outlook, not a direct forecast of W. [PKO BP analysis](https://centrumanaliz.pkobp.pl/makroekonomia/makro-flash-stopy-nbp-bez-zmian-ale-inflacja-w-projekcji-mocno-rosnie)

The BGK archive now lists 2026 notices, including November. Thus the earlier research note's concern about publication in 2026–2028 should not be interpreted as an absence of published 2026 observations. This check does not resolve the legal interpretation identified in that note.

## Provisional simulation assumptions

| Scenario | Second-period W |
| --- | ---: |
| Lower-rate environment | 4.5% |
| Central assumption | 5.5% |
| Higher-rate environment | 6.5% |
| Additional stress case | 7.5% |

The central assumption is anchored near the latest observed 5.48%. The 4.5–6.5% working range and 7.5% stress case are deliberately chosen sensitivity inputs, not outputs of an estimated forecasting model. No probabilities are assigned, and outcomes outside the range remain possible.

The available outlook does not justify mechanically extrapolating earlier declines in W. Revisit these assumptions as the reset approaches using new BGK notices and the bank's actual rate offer.

## Interpreting the results

Vary the second-period contractual bank rate alongside W when modelling different market environments. A lower W reduces the subsidy, but falling market rates may also reduce the contractual bank rate. Holding the bank rate fixed while lowering W tests a less favourable gap between the two rather than a complete falling-rate scenario. There is no assumed one-for-one relationship between changes in W and the individual bank's offer.

Under the implemented monthly subsidy formula, at an opening balance of PLN 300,000, a one-percentage-point change in W changes that month's subsidy by **PLN 250**:

```text
300,000 × 0.01 ÷ 12 = 250
```

This illustration holds the balance and all other inputs fixed. It is not a prediction of the total instalment change because contractual interest may change as well.

## Contractual bank-rate sensitivity

Model lower, central, and higher contractual bank-rate scenarios alongside the W
scenarios above. Select these inputs independently from public market assumptions;
keep individual bank offers and agreement terms in private configuration.

W and the contractual bank rate measure different things. Dividing W by the
reference-market adjustment factor gives an indicative market average, not a rate
that an individual bank must offer. It does not establish a fixed spread between
W and a borrower's contractual rate.

For each scenario, the annualized net interest burden on the opening balance is:

```text
contractual bank rate − (W − subsidized reference rate)
```

This excludes fees and principal repayments and is not an APR or the total
instalment. The gap between the bank rate and W is a separate source of uncertainty.
Authoritative application defaults live in
[settings.py](../../src/mortgage_simulator/settings.py); research scenarios do not
define them.
