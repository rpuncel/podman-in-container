from __future__ import annotations

import click

from .engines import EngineError, detect_engine

DEFAULT_WORKSPACE = "global"


def machine_name(workspace: str) -> str:
    return f"pic-{workspace}"


@click.group()
def main() -> None:
    """Launch and manage podman-in-container sandbox machines."""


@main.command()
@click.option("--workspace", default=DEFAULT_WORKSPACE, show_default=True)
def launch(workspace: str) -> None:
    """Launch a workspace machine."""
    engine = detect_engine()
    name = machine_name(workspace)
    click.echo(f"Launching machine '{name}' via engine '{engine.name}'...")
    try:
        engine.create(name)
    except EngineError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Machine '{name}' is up.")


@main.command()
@click.option("--workspace", default=DEFAULT_WORKSPACE, show_default=True)
def teardown(workspace: str) -> None:
    """Tear down a workspace machine."""
    engine = detect_engine()
    name = machine_name(workspace)
    click.echo(f"Tearing down machine '{name}' via engine '{engine.name}'...")
    try:
        engine.destroy(name)
    except EngineError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Machine '{name}' torn down.")


if __name__ == "__main__":
    main()
