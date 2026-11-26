---
name: run-mortgage-simulation
description: Use when an agent needs to run mortgage simulations, compare overpayment or deposit strategies, or replay saved results in this repository without starting the UI.
---

# Run mortgage simulations

Read [the headless workflow](../../../docs/11-cli-simulations.md) for profile selection, schemas, request construction,
Just recipes, replay, artifacts, and interpretation. Run the documented **Just commands** from the repository root.

For “my mortgage,” use the approved profile in the main checkout as described in the headless workflow. If it is
missing or invalid, pause and offer setup or correction. To set up from `.env`, draft the profile, ask for missing
or invalid terms, edit the draft, and validate it. Ask the user to review and approve the draft before promoting it
to the shared profile. Use the existing approved profile until a replacement is approved.

Honor an explicitly selected profile and clarify ambiguous selections or material assumptions. For “pay now” on a
schedule that starts in the past, ask whether to use a modeled balance or wait for current terms. Translate the
question into equal-funded strategies when appropriate, and explain the payment date, balance source, and
differences with links to generated artifacts.

Follow the workflow's links to existing configuration and model documentation as needed. Use the shared executable
through Just rather than creating calculation scripts or starting Streamlit.
