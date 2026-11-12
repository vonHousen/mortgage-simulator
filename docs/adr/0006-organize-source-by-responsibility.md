# 0006. Organize source by responsibility

## Status

Accepted

## Context

The application grew from a small package into a financial engine, reporting layer, Streamlit workflow, and local
reference adapters. Keeping all modules at the package root made related files difficult to identify and left generic
names such as `logic.py`, `data.py`, and `ui_results.py` without enough context.

The documented architecture already requires one-way dependencies from calculation through reporting to the user
interface. The source tree did not make those boundaries visible. Organizing every architectural stage as a separate
package would make several directories contain only one file, while feature-oriented packages would split shared
simulation models across UI concerns.

## Decision

Organize the installable package into `simulation`, `reporting`, `app`, and `reference_data` subpackages. Keep
environment-backed `settings.py` at the package root because it supplies application defaults across the entrypoint,
session state, and input conversion.

Use nested `app/app_pages` for direct Streamlit scripts and `app/presentation` for reusable result rendering. Keep the
name `app_pages` to avoid Streamlit's legacy `pages` auto-discovery behavior. Split scenario defaults from environment
settings, and split scenario comparison reporting from payment-schedule projection and CSV serialization.

Update repository imports to the new paths without compatibility modules or package-level re-exports. Preserve public
function signatures, validated models, financial behavior, and regression expectations.

## Consequences

- Source paths communicate dependency boundaries and make related modules easier to find.
- Simulation code remains independent of Streamlit, Polars, Altair, settings, and local reference files.
- Existing callers must update imports to the new module paths.
- Tests mirror the source responsibility areas and make cross-layer coverage visible.
- New modules belong in the narrowest existing responsibility instead of a generic `utils` package.
