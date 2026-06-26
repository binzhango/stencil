"""Command-line interface."""

import json
from pathlib import Path
from typing import Annotated

import click
import typer

from .errors import StencilError
from .render import render

app = typer.Typer(help="Render Stencil Office templates.")


@app.callback()
def main() -> None:
    """Stencil command-line interface."""


@app.command(name="render")
def render_command(
    template: Annotated[Path, typer.Argument(help="Path to the Office template.")],
    data: Annotated[Path, typer.Argument(help="Path to a JSON data file.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path to write the rendered document."),
    ],
    output_format: Annotated[
        str | None,
        typer.Option("--format", "-f", help="Output format. Defaults to the output suffix."),
    ] = None,
) -> None:
    """Render a template with JSON data."""

    try:
        payload = json.loads(data.read_text(encoding="utf-8"))
    except OSError as exc:
        raise typer.BadParameter(f"Could not read data file: {exc}", param_hint="data") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON data file: {exc}", param_hint="data") from exc

    if not isinstance(payload, dict):
        raise typer.BadParameter("JSON data must be an object at the top level", param_hint="data")

    requested_format = output_format or output.suffix.removeprefix(".") or None

    try:
        rendered = render(template, payload, output_format=requested_format)
    except StencilError as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(rendered)
    except OSError as exc:
        raise click.ClickException(f"Could not write output file: {exc}") from exc
