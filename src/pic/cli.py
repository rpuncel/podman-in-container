from __future__ import annotations

import click

from . import machine as machine_mod
from .engines import EngineError

DEFAULT_WORKSPACE = machine_mod.DEFAULT_WORKSPACE


@click.group()
def main() -> None:
    """Launch and manage podman-in-container sandbox machines."""


@main.command()
@click.option("--workspace", default=DEFAULT_WORKSPACE, show_default=True)
def launch(workspace: str) -> None:
    """Launch a workspace machine."""
    name = machine_mod.machine_name(workspace)
    click.echo(f"Launching machine '{name}' (building the machine image if needed)...")
    try:
        machine_mod.launch(workspace)
    except (EngineError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Machine '{name}' is up.")


@main.command()
@click.option("--workspace", default=DEFAULT_WORKSPACE, show_default=True)
def teardown(workspace: str) -> None:
    """Tear down a workspace machine."""
    name = machine_mod.machine_name(workspace)
    click.echo(f"Tearing down machine '{name}'...")
    try:
        machine_mod.teardown(workspace)
    except EngineError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Machine '{name}' torn down.")


if __name__ == "__main__":
    main()
