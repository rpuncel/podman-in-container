"""A machine: the persistent Linux VM that realizes a sandbox (ADR-0002).

Wraps an outer engine and the machine image together, so callers -- the CLI and the
acceptance tests alike -- work in terms of a booted, provisioned machine rather than
in terms of engine subcommands.
"""

from __future__ import annotations

import json
import subprocess
import time

from . import machine_image
from .engines import Engine, EngineError, detect_engine

DEFAULT_WORKSPACE = "global"


def machine_name(workspace: str) -> str:
    return f"pic-{workspace}"


class Machine:
    """A booted machine, addressed by name through the engine that created it."""

    def __init__(self, engine: Engine, name: str) -> None:
        self._engine = engine
        self.name = name

    def exec(self, *command: str) -> subprocess.CompletedProcess:
        """Run `command` inside the machine, raising EngineError if it fails."""
        return self._engine.exec(self.name, *command)

    def succeeds(self, *command: str) -> bool:
        """Whether `command` exits zero inside the machine."""
        try:
            self.exec(*command)
        except EngineError:
            return False
        return True

    def init_report(self) -> dict:
        """What the image's entrypoint provisioned at boot: firewall driver, storage, users.

        Shape and path are the entrypoint's: images/machine/rootfs/usr/local/sbin/pic-machine-init.
        """
        return json.loads(self.exec("cat", machine_image.INIT_REPORT_PATH).stdout)

    def wait_until_initialised(self, attempts: int = 30, delay: float = 2.0) -> None:
        """Block until the entrypoint has finished its boot-time setup.

        The engine's exec channel comes up well before the machine reaches
        multi-user.target, so a machine that answers commands is not yet a machine
        whose podman can run anything. Poll for the entrypoint's report instead of
        letting every caller race the boot.
        """
        for _ in range(attempts):
            if self.succeeds("test", "-f", machine_image.INIT_REPORT_PATH):
                return
            time.sleep(delay)
        raise EngineError(f"machine '{self.name}' never finished its boot-time setup")


def launch(workspace: str = DEFAULT_WORKSPACE) -> Machine:
    """Build the machine image if needed, boot a machine for `workspace`, and wait for it."""
    engine = detect_engine()
    machine = Machine(engine, machine_name(workspace))
    engine.build_image(machine_image.TAG, machine_image.context_dir())
    engine.create(machine.name, image=machine_image.TAG, memory=machine_image.MEMORY)
    machine.wait_until_initialised()
    return machine


def teardown(workspace: str = DEFAULT_WORKSPACE) -> None:
    """Stop and remove the machine for `workspace`."""
    detect_engine().destroy(machine_name(workspace))
