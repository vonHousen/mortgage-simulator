# ADR 0011: Provide a headless simulation interface

- Status: Accepted
- Date: 2026-11-13

## Context

Agents need to compare supported mortgage strategies without manipulating Streamlit or assembling Python scripts.
The engine already accepts validated inputs and returns immutable results. A second interface must preserve that
calculation path and avoid duplicating financial rules, configuration defaults, reporting, or workflow documentation.

## Decision

Provide Just recipes forwarding to a thin Typer executable. Typer owns arguments, delegation, response serialization,
and exit-code translation only. Interface-independent application services own explicit profile/request resolution,
baseline insertion, validation, simulation orchestration, and artifact exports. Simulation owns financial behavior;
reporting owns comparison and schedule projections. Extract investment projections from the UI into reporting so
both interfaces reuse them, with UI labels and display formatting remaining in Streamlit.

Every simulation capability must be available through both the GUI and CLI, using shared application/domain logic.
Interface-specific presentation and operational features are exempt. Integration tests must verify equivalent
results for equivalent inputs across both interfaces.

Dependencies flow from Just to Typer to application services, and from services to settings, simulation, and reporting.
Reporting depends on simulation models. Streamlit remains a separate interface consuming simulation/reporting code.
The CLI and application services must never import or launch Streamlit; neither shared reporting nor simulation may
import either interface. No domain calculation depends on Typer, Just, filesystem profiles, or environment settings.

Read settings only during explicit profile export. A run consumes supplied profile terms and request overrides, then
saves complete effective inputs for replay. Generate schemas from Pydantic contracts rather than maintaining separate
schema documents. Keep decimal values precise through machine outputs. Expose the current shared Net financing cost
metric and baseline deltas, and preserve the automatic timing objective recorded in
[ADR 0010](0010-use-net-financing-cost-for-investment-timing.md).

Maintain the command workflow in `docs/11-cli-simulations.md`. The repository-local skill routes agents there and to
existing model/configuration documentation, adding only agent-specific discovery and clarification guidance. It uses
Just recipes rather than duplicating CLI commands or writing execution scripts.

## Alternatives considered

- A skill that writes Python scripts requires less interface code, but repeats orchestration and exports and creates
  inconsistent agent workflows.
- Putting orchestration inside Typer couples reusable use cases to command handling and makes cross-layer tests
  dependent on a transport adapter.
- Driving Streamlit requires UI state and a running application for a use case already supported by the pure engine.

## Consequences

- Agents and humans can run reproducible comparisons without starting a server.
- Just, Typer, application services, reporting, and simulation have separate, testable responsibilities.
- Integration tests exercise actual engine/export behavior, installed commands, Just forwarding, and the absence of
  Streamlit imports.
- Saved inputs and outputs are local financial artifacts; the workflow uses ignored `data/` paths.
- The CLI inherits existing model capabilities and limits; it does not add financial formulas or a general optimizer.
