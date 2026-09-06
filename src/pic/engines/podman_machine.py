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

    def create(self, machine_name: str, image: str, memory: str) -> None:
        # `podman machine init` boots its own bundled base image and has no way to
        # take one -- so this engine can build the pic machine image but cannot boot
        # a machine from it, and a machine without the image's entrypoint has none of
        # the inner-podman setup the sandbox depends on. Provisioning the podman
        # fallback -- or retiring it -- is tracked as #13; fail loudly rather than
        # hand back a machine that looks right and is not.
        raise EngineError(
            f"`podman machine` cannot boot a custom base image, so it cannot provide "
            f"the pic machine image ({image}). Use Apple `container` (ADR-0002)."
        )

    def exec(self, machine_name: str, *command: str) -> subprocess.CompletedProcess:
        result = self._run("machine", "ssh", machine_name, "--", *command)
        if result.returncode != 0:
            raise EngineError(f"podman machine ssh failed: {result.stderr.strip()}")
        return result

    def destroy(self, machine_name: str) -> None:
        self._run("machine", "stop", machine_name)
        self._run("machine", "rm", "-f", machine_name)
