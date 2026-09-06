from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod


class EngineError(RuntimeError):
    """Raised when an outer engine operation fails."""


class Engine(ABC):
    """A container-machine outer engine: creates, execs into, and destroys machines.

    Implementations wrap a specific host tool (Apple `container`, `podman machine`)
    behind this shared surface so callers never need to know which one is in use.
    """

    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this engine's CLI is present on the host."""

    @abstractmethod
    def create(self, machine_name: str) -> None:
        """Create and boot a machine with the given name."""

    @abstractmethod
    def exec(self, machine_name: str, *command: str) -> subprocess.CompletedProcess:
        """Run `command` inside the named machine and return the completed process."""

    @abstractmethod
    def destroy(self, machine_name: str) -> None:
        """Stop and remove the named machine."""

    def _wait_until_ready(self, machine_name: str, attempts: int = 10, delay: float = 1.0) -> None:
        """Block until the machine accepts exec calls.

        `create` reporting success doesn't mean the exec channel is up yet: right
        after boot, the first exec can fail transiently. Poll a trivial command
        until it succeeds rather than making callers race the boot themselves.
        """
        last_error: EngineError | None = None
        for _ in range(attempts):
            try:
                self.exec(machine_name, "true")
                return
            except EngineError as exc:
                last_error = exc
                time.sleep(delay)
        raise EngineError(f"machine '{machine_name}' never became ready: {last_error}")
