# ADR 0007: Adopt ty alongside mypy

- Status: Accepted
- Date: 2026-08-01

## Context

The project uses strict mypy checking for application and test code. Astral's `ty` provides an additional, fast type
checker, but its pre-1.0 type analysis does not yet model every third-party API in the project consistently with mypy.
In particular, it misidentifies Polars frames returned by Streamlit's data editor and cannot resolve parts of Altair's
generated fluent chart API.

The project should benefit from `ty` diagnostics without weakening the established mypy gate or hiding unrelated type
errors project-wide.

## Decision

Run both mypy and `ty` from the existing `just typecheck` recipe, making both part of `just ci`. Add `ty` as a locked
development dependency so local and CI checks use the same version.

Use rule-specific `# ty: ignore[...]` comments only for confirmed incompatibilities in external typing. Every such
suppression includes a concise reason, and unused `ty` suppression comments are errors so obsolete workarounds are
removed when upstream typing improves.

Resolve project-owned narrowing gaps with explicit annotations or `typing.cast()` instead of suppressions. Do not use
blanket, file-wide, or project-wide suppression for the affected rules.

## Consequences

- `just ci` rejects diagnostics from either mypy or `ty`.
- Third-party typing gaps remain visible and localized next to the affected integration.
- Upstream typing improvements can turn suppressions into actionable unused-comment errors.
- Developers must justify new `ty` suppressions as external typing incompatibilities.
- The project carries both type-checker dependencies while `ty` remains pre-1.0.

## Alternatives considered

### Replace mypy with ty

This would reduce duplicate tooling, but it would discard the established strict gate while `ty` still handles some
third-party APIs differently.

### Suppress every current diagnostic

This would produce a clean `ty` run with the smallest diff, but it would also suppress project-owned narrowing gaps
that can be expressed explicitly.

### Disable affected rules globally

Ignoring argument, attribute, or return-type rules in configuration would also hide legitimate errors elsewhere in
the project.
