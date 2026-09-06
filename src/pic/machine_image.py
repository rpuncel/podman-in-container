"""The machine base image: Ubuntu 24.04 + systemd + inner podman (ADR-0002, ADR-0004).

The build context lives at `images/machine/` in the repo rather than inside the
package: the Containerfile and its entrypoint are a deliverable in their own right,
readable and buildable without the CLI.
"""

from __future__ import annotations

from pathlib import Path

TAG = "pic-machine:latest"

# The outer engine defaults a machine to 1 GiB, which ADR-0002 records as too small
# for inner podman to build and run workloads in.
MEMORY = "4G"

# Written by the image's pic-machine-init entrypoint once boot-time setup is done.
# Its presence is what makes a machine ready to use, not merely reachable. The path is
# also named in images/machine/rootfs/usr/local/sbin/pic-machine-init; keep them in step.
INIT_REPORT_PATH = "/run/pic/machine-init.json"

_CONTEXT_DIR = Path(__file__).resolve().parents[2] / "images" / "machine"


def context_dir() -> Path:
    """The build context directory for the machine image."""
    if not (_CONTEXT_DIR / "Containerfile").is_file():
        raise FileNotFoundError(f"machine image build context not found at {_CONTEXT_DIR}")
    return _CONTEXT_DIR
