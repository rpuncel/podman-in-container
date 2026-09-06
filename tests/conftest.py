from __future__ import annotations

import subprocess

import pytest

from pic.engines import Engine, detect_engine


class MachineHandle:
    """Handle to a running machine: seam 1 for acceptance tests."""

    def __init__(self, engine: Engine, name: str) -> None:
        self._engine = engine
        self.name = name
        self.engine_name = engine.name

    def exec(self, *command: str) -> subprocess.CompletedProcess:
        return self._engine.exec(self.name, *command)


@pytest.fixture(scope="session")
def machine():
    engine = detect_engine()
    name = "pic-test"
    try:
        engine.create(name)
        yield MachineHandle(engine, name)
    finally:
        engine.destroy(name)
