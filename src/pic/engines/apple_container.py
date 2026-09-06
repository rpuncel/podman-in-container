from __future__ import annotations

import shutil
import subprocess

from .base import Engine, EngineError


class AppleContainerEngine(Engine):
    name = "container"

    def is_available(self) -> bool:
        return shutil.which("container") is not None

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["container", *args], capture_output=True, text=True)

    def create(self, machine_name: str, image: str, memory: str) -> None:
        # Idempotent: safe to call even if the service is already running.
        self._run("system", "start")
        result = self._run(
            "machine", "create", image, "--name", machine_name, "--memory", memory
        )
        if result.returncode != 0:
            raise EngineError(f"container machine create failed: {result.stderr.strip()}")
        self._wait_until_ready(machine_name)

    def exec(self, machine_name: str, *command: str) -> subprocess.CompletedProcess:
        result = self._run("machine", "run", "-n", machine_name, "--", *command)
        if result.returncode != 0:
            raise EngineError(f"container machine run failed: {result.stderr.strip()}")
        return result

    def destroy(self, machine_name: str) -> None:
        self._run("machine", "stop", machine_name)
        self._run("machine", "delete", machine_name)
