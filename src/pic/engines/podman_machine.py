from __future__ import annotations

import shutil
import subprocess

from .base import Engine, EngineError


class PodmanMachineEngine(Engine):
    name = "podman"

    def is_available(self) -> bool:
        return shutil.which("podman") is not None

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["podman", *args], capture_output=True, text=True)

    def create(self, machine_name: str) -> None:
        result = self._run("machine", "init", "--now", machine_name)
        if result.returncode != 0:
            raise EngineError(f"podman machine init failed: {result.stderr.strip()}")
        self._wait_until_ready(machine_name)

    def exec(self, machine_name: str, *command: str) -> subprocess.CompletedProcess:
        result = self._run("machine", "ssh", machine_name, "--", *command)
        if result.returncode != 0:
            raise EngineError(f"podman machine ssh failed: {result.stderr.strip()}")
        return result

    def destroy(self, machine_name: str) -> None:
        self._run("machine", "stop", machine_name)
        self._run("machine", "rm", "-f", machine_name)
