# 0003. Use environment-backed application defaults

## Status

Superseded by ADR 0008

## Context

Application defaults currently mix environment-specific assumptions with reusable domain defaults. This couples local
startup behavior to one source profile and makes calculations that rely implicitly on defaults vulnerable to unrelated
configuration changes.

## Decision

Retain general, validated code fallbacks and layer local or deployment configuration through native
`pydantic-settings` sources. Local dotenv configuration is optional; process-environment values retain their standard
precedence over dotenv values.

Regression parity suites own explicit, immutable input fixtures. They never inherit application configuration, so
local or deployment settings cannot change governed parity inputs.

## Consequences

- Local `.env` files are untracked.
- Missing dotenv files are supported and the application falls back to validated general values.
- Deployments must provide their own environment-specific values when the general profile is not appropriate.
- Complex settings use the representation accepted natively by `pydantic-settings`; ADR 0004 replaces that
  representation with paired scalars for the application's fixed UI rate periods.
