# 0004. Use scalar settings for fixed rate periods

## Status

Superseded in part by ADR 0008

## Context

The domain model supports arbitrary mortgage rate periods, but the application UI exposes two fixed periods. Mapping
the generic tuple directly to environment configuration required a quoted JSON array, making the local and deployment
contract harder to read and maintain than the UI behavior it represents.

Every other shared mortgage assumption exposed by the setup UI can be configured with a scalar environment value.
Dynamic overpayment scenarios and lump sums are per-session inputs rather than application defaults.

## Decision

Configure the two UI rates through paired scalar settings named for their fixed month ranges. Both values are required
when either is supplied. `AppSettings` assembles them into the existing generic `MortgageTerms.rate_periods` tuple
after native settings sources apply their standard precedence.

Reject the former JSON rate-period environment variable with a migration error. At the time of this decision,
complete `MortgageTerms` objects were accepted at the settings constructor boundary; ADR 0008 replaces that coupling
with an explicit settings-to-domain conversion.

## Consequences

- Local and deployment configuration contains only scalar dotenv entries.
- The environment contract matches the two rate controls exposed by the application UI.
- The domain model remains reusable for explicit schedules outside the application-default boundary.
- Supplying only one fixed-period rate prevents application startup with a validation error.
