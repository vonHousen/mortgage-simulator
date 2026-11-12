# Deposit verification brief

Use three fresh Luna agents with isolated worktrees and synthetic local `data/config/scenarios.json` files. Never
edit production code or regression expectations. Load each fixture using `load_local_scenarios`, run `simulate`, and
independently calculate expected values. Report fixture, commands, expected and actual results, and defects.

## Round 1 — maturity arithmetic and configuration

Use capital 100000 PLN and annual rate 0.06. Three-month one-term balance must be 101215.00; two terms must produce
second gross interest 1518.23, tax 288.47, balance 102444.76. A 36-month single term must produce 114580.00.
Check zero rate, zero terms, rounding boundaries, old JSON, negative rate, zero term length, and maturity beyond horizon.

## Round 2 — mortgage integration

Use small synthetic debt and explicit zero-fee, equal-month terms. Combine regular principal, recurring overpayment,
existing balloons, and investment maturity. Independently calculate their application order. Check exact payoff and
surplus conservation. Clear the mortgage during the first deposit term of a three-term plan: only that term may
finish. Check payoff exactly at maturity and before T. Check final-horizon maturity with settlement on and off.
No candidate may repay principal twice.

## Round 3 — optimization and UI

Independently enumerate all manual candidates and compare automatic results, including rate/subsidy boundaries,
zero rate, exact ties, and no eligible positive-term maturity. Earnings and surplus must not change the mortgage-cost
objective. Load synthetic JSON in a fresh Streamlit AppTest session, verify configured values, Add/Edit/Remove,
Apply/Cancel, mode changes, session navigation, validation, simulation, and exports.

## Primary-agent browser inspection

Connect personally to the running worktree app with synthetic Quarterly deposit, Three-year deposit, and Optimize
deposit scenarios. Verify loaded inputs and every investment button, mode switch, run, results and downloads.
Inspect desktop and narrow layouts for spacing, readable numbers, useful labels, overflow and validation. Capture
and inspect screenshots of the populated section, manual editor, automatic controls and results. Fix defects and
repeat affected interactions. AppTest does not replace personal visual inspection.

## Final gates

Run `just ci` and `just e2e-regression-tests`. Reference values and manifests are immutable. Missing artifacts or
failures block completion. Keep ignored synthetic configuration out of commits.

## Verification performed

Three fresh Luna agents used isolated fixtures under `.worktrees/deposit-verification-1`,
`.worktrees/deposit-verification-2`, and `.worktrees/deposit-verification-3`. Arithmetic and mortgage interaction
cases passed; exhaustive manual candidates matched the optimizer. JSON-backed AppTest sessions loaded their
configured investments and produced results.

Interactive AppTest verification initially encountered stale term-count state. A subsequent targeted test
reproduced a real navigation defect: an edited manual term count reset when navigating away and returning.
Session persistence fixes that defect. The regression test now verifies navigation, automatic/manual switching,
cancellation, and a subsequent rerun without exceptions.

Live visual inspection was **not completed**: the browser host was unavailable, and native-browser screenshots
remained frozen on an older app at port 8501 despite accessibility state showing navigation to port 8511.
Automated interaction coverage does not establish visual quality; personal screenshot-based UI/UX inspection remains
outstanding until browser access works.
