# Sandbox is a machine, not a nested container

The sandbox is realized as a persistent Linux VM (a "machine") — an Apple `container machine` (primary) or a `podman machine` (fallback) — booting systemd as PID 1, with inner podman running inside it **non-nested**, as it would on any Linux host.

Chosen over running podman *nested* inside a plain Apple `container` because: (1) it eliminates the unverified nested-rootless-podman feasibility risk — podman runs normally on a full Linux host; and (2) it provides systemd, satisfying the requirement to run systemd-based workloads.

Confirmed viable by research (`docs/research/apple-container-machine.md`): `container machine` boots the base image's own init (Apple ships an Ubuntu 24.04 + systemd reference Dockerfile), and podman-in-machine is community-demonstrated on Fedora. `--virtualization` (nested KVM) is NOT required for podman.

Trade-off / known gotchas to handle in the entrypoint: the default guest kernel lacks nftables, so podman must use **iptables-legacy** as its firewall driver; default machine RAM is **1 GiB** (must be raised); clean reset is **`rm` + `create`** (no in-place factory reset).
