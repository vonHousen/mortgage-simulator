"""Thin command-line adapter for headless application services."""

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from mortgage_simulator.application.simulation_runs import (
    draft_profile,
    export_profile,
    input_schema,
    run_comparison,
    validate_profile,
)

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
profile_app = typer.Typer(no_args_is_help=True)
app.add_typer(profile_app, name="profile")
logger = logging.getLogger(__name__)


class SchemaKind(StrEnum):
    """Input contracts discoverable through the schema command."""

    PROFILE = "profile"
    REQUEST = "request"


@profile_app.command("export")
def profile_export(output: Annotated[Path, typer.Option(help="New profile JSON path.")]) -> None:
    """Freeze application settings into a reusable profile.

    Args:
        output: Destination file for the exported mortgage terms.
    """
    with _command_errors():
        typer.echo(json.dumps({"profile": str(export_profile(output))}))


@profile_app.command("draft")
def profile_draft(
    env_file: Annotated[Path, typer.Option(help="Dotenv file supplying the starting mortgage settings.")],
    output: Annotated[Path, typer.Option(help="New draft JSON path.")],
) -> None:
    """Draft an editable profile from explicitly supplied mortgage settings.

    Args:
        env_file: File containing the mortgage settings to import.
        output: Destination for the editable draft.
    """
    with _command_errors():
        fields = draft_profile(env_file, output)
        typer.echo(json.dumps({"draft": str(output), "fields_needing_attention": fields}))


@profile_app.command("validate")
def profile_validate(profile: Annotated[Path, typer.Argument(help="Complete JSON profile to validate.")]) -> None:
    """Check whether a profile is ready for use in a comparison.

    Args:
        profile: Profile file to validate.
    """
    with _command_errors():
        validate_profile(profile)
        typer.echo(json.dumps({"profile": str(profile)}))


@app.command()
def schema(kind: SchemaKind) -> None:
    """Print an authoritative JSON input schema.

    Args:
        kind: Profile or comparison-request schema.
    """
    with _command_errors():
        typer.echo(json.dumps(input_schema(kind)))


@app.command()
def run(
    request: Annotated[Path, typer.Option(help="Comparison request or resolved request JSON.")],
    output: Annotated[Path, typer.Option(help="New result directory.")],
    profile: Annotated[Path | None, typer.Option(help="Optional complete mortgage profile JSON.")] = None,
) -> None:
    """Compare strategies and export reproducible results without a UI.

    Args:
        request: Input file containing terms and custom scenarios.
        output: Destination directory for a successful comparison.
        profile: Saved terms to merge with request overrides.
    """
    with _command_errors():
        typer.echo(run_comparison(request, output, profile).model_dump_json())


@contextmanager
def _command_errors() -> Iterator[None]:
    try:
        yield
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    except OSError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    except Exception as error:
        logger.exception("Simulation command failed")
        raise typer.Exit(code=1) from error
