# ADR 0009: Share pre-commit checks with CI

- Status: Accepted
- Date: 2026-11-13
- Supersedes [ADR 0007](0007-adopt-ty-alongside-mypy.md) only for check orchestration.

## Context

Commit hooks and CI need consistent quality checks without duplicating tool commands or Python dependency versions.
Fast feedback before committing should not require running both type checkers or the application test suite.
Local documentation links also need validation without depending on external website availability.

## Decision

Define the shared quality-check bundle in the repository's [pre-commit configuration](../../.pre-commit-config.yaml).
Use local hooks invoking Python tools through `uv run --locked`, with dependencies resolved in `uv.lock` rather than
remote hook revisions or separate hook environments. uv itself remains an external prerequisite.

The bundle includes uv lockfile validation, safe Ruff lint fixes and formatting, ty, YAML/TOML validation,
merge-conflict and private-key detection, whitespace and final-newline cleanup, and offline lychee link checking.
Lockfile validation checks consistency without regenerating the lockfile. ty checks the whole project rather than
only the staged filenames. Markdown hard breaks are preserved by whitespace cleanup.

Git commits run the bundle on staged files. `just pre-commit` runs it on all tracked files, and `just ci` runs that
same bundle followed by mypy and pytest. Therefore local `just ci` and GitHub Actions both run lychee and both type
checkers, while commit hooks run only ty. The `just typecheck` recipe continues to run both checkers.
Individual Just recipes delegate shared checks to their corresponding hooks; mypy's command is defined once in Just.

Keep lychee as an external executable, installed locally and in GitHub Actions. It checks local Markdown/HTML links
without network access. Python tooling remains locked through uv; lychee is not a Python dependency.

Hooks apply safe fixes and fail when files change, including in CI. Developers review and stage corrections before
retrying. Installation of Git hooks is explicit through `just hooks-install`, separate from dependency synchronization.
Private regression suites remain an explicit prerequisite before merges and important commits.

## Consequences

- One bundle determines the shared checks for commits, local CI, and GitHub Actions.
- Commit hooks provide ty feedback; CI retains the independent strict mypy gate.
- Python tool versions come from one lockfile; uv, Just, and lychee must be installed separately.
- Offline link checks are repeatable but do not verify external websites.
- Safe automatic fixes can require another commit attempt; CI rejects changes that require those fixes.
- ADR 0007's typing configuration and suppression policies remain in force.

## Alternatives considered

### Duplicate commands in Just and hook configuration

This is straightforward initially but allows the checks and their options to diverge.

### Use remote hook repositories

Remote integrations maintain separate revisions and environments, duplicating Python version management outside uv.

### Run both type checkers before every commit

This preserves every CI check in commit hooks but adds a second type-checking pass to the commit workflow.

### Check external links in the shared bundle

This catches unavailable websites but makes ordinary commits depend on networking, rate limits, and site availability.
