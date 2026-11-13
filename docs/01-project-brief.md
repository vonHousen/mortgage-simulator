# Mortgage Simulator — Project Brief

## Summary

Mortgage Simulator is a decision-support tool for exploring how mortgage overpayments affect cash flow, interest,
and remaining principal.

Its starting point is a local reference workbook modelling part of a Polish subsidized mortgage. The application
makes those calculations easier to inspect, configure, compare, and verify.

## Problem

The workbook contains useful analysis, but each overpayment strategy is copied into a separate worksheet. This makes scenarios cumbersome to change, comparisons difficult to read, and calculation defects easy to miss.

The simulator should express one mortgage model and apply different scenario data to it, giving the user a consistent view of every strategy.

## Intended user

The intended users are people comparing mortgage overpayment strategies who value transparent assumptions and
detailed results over generalized financial guidance.

## Product direction

The first version translates the workbook's intentional behavior into an interactive Streamlit application. It
compares a no-overpayment baseline with configurable recurring and lump-sum overpayments over a selected analysis
horizon. Scenarios can also invest available capital in a fixed-rate deposit, renew it after tax, and apply the
net balance as a later mortgage repayment. Net financing cost combines mortgage charges and net investment earnings
as the primary comparison metric; [Understanding the metrics](10-understanding-metrics.md) explains the distinction. See [Invest before overpaying](09-invest-before-overpaying.md).
It can also settle principal remaining after the final regular horizon payment so scenarios can be compared
with identical principal repayment; users can disable this option for partial-horizon and workbook-parity analysis.

Later versions may replace spreadsheet assumptions with independently researched current rules and extend the analysis beyond the subsidy period. That work is separate because real-world rules may change the model rather than merely add features.

## Principles

- Make every material financial assumption visible and configurable.
- Use one calculation path for the baseline and all overpayment scenarios.
- Keep financial logic independent from the interface and reporting tools.
- Prefer explainable results over opaque spreadsheet replication.
- Identify estimates clearly; the application does not provide financial or legal advice.

Technical behavior is specified in [02-design.md](02-design.md). See the [documentation index](README.md) for model
research, validation guidance, configuration, and architecture decisions.
