# ADR 0008: Centralize environment configuration

- Status: Accepted
- Date: 2026-08-01

## Context

Application defaults were stored on domain models and exposed indirectly through a partly flat `AppSettings` model.
Developers had to inspect both modules to learn what could be configured, and constructing a domain model without
arguments silently selected application behavior. The settings model also accepted unrelated or obsolete inputs.

The application needs one discoverable environment contract without making the simulation domain depend on dotenv,
deployment naming, or application startup concerns.

## Decision

Define every environment-configurable attribute and fallback in `settings.py`. Group the root settings into
`mortgage`, `scenarios`, and `charts`, with `subsidy` and `fees` nested under `mortgage`. Use the `MS_` environment
prefix and `__` group delimiter. Reject unknown inputs and all previous `MORTGAGE_SIMULATOR_...` keys with migration
guidance.

Convert `AppSettings` once at startup through `to_mortgage_terms()`. Keep `MortgageTerms`, `SubsidyTerms`, `FeeTerms`,
and `SimulationRequest.terms` free of application fallback values, so callers must provide complete domain inputs.
Keep the optional scenario JSON schema in the application loader because it describes per-session scenario data, not
environment configuration.

## Consequences

- `settings.py` is sufficient to discover the complete environment contract and its code fallbacks.
- The simulation domain remains independent of Pydantic Settings and environment-variable names.
- Environment keys and the settings constructor hierarchy change incompatibly; legacy inputs fail at startup.
- Tests and non-application callers must use explicit complete domain inputs.
- The two fixed application rates remain paired configuration values and become generic domain rate periods only at
  the conversion boundary.

## Alternatives considered

### Keep defaults on domain models

This minimizes constructor verbosity but leaves application policy hidden across two modules and permits accidental
implicit simulation inputs.

### Make domain models read settings

This creates one apparent source of values but reverses the dependency direction and couples reusable calculations to
environment loading.

### Move scenario JSON into AppSettings

This would conflate the environment contract with dynamic scenario-file data and make settings responsible for a
separate input schema.
