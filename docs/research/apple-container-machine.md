# Apple `container machine` — research findings

Research target: the `container machine` subcommand of Apple's `container` CLI
(apple/container, macOS, Apple silicon). This is **distinct from `podman machine`**.

Primary sources used:

- Standalone docs page: <https://github.com/apple/container/blob/main/docs/container-machine.md>
  (raw: <https://raw.githubusercontent.com/apple/container/main/docs/container-machine.md>)
- Introducing PR #1662 "Add `container machine` for managing persistent Linux environments":
  <https://github.com/apple/container/pull/1662>
- VS Code example: <https://github.com/apple/container/tree/main/examples/container-machine-vscode>
- Release 1.1.0 changelog (machine doc / example / nested virt landed here):
  <https://github.com/apple/container/releases/tag/1.1.0>
- Podman-inside-machine discussion (community, primary-ish):
  <https://github.com/containers/podman/discussions/27278>

Version note: the `container machine` docs, example, and nested-virt support landed
around the 1.0.0 -> 1.1.0 timeframe. Release 1.1.0 explicitly lists "add standalone
container machine document" (#1674), "Adds container machine example" (#1676), and
"add container machine nested virt" (#1742). The feature itself was introduced by
PR #1662. Everything below is current as of the `main` branch docs (~1.3.x era).

---

## 1. PURPOSE — what is `container machine` for?

**Answer: primarily (b) — a general-purpose, persistent Linux dev VM you shell into
and use directly.** It is NOT the substrate that runs your ordinary `container run`
containers.

From the docs (container-machine.md):

> "Container machine provides a highly integrated Linux environment that works
> seamlessly on your Mac. Container machines are fast, lightweight and persistent."

> "Containers are typically modeled after an application. A container machine is
> modeled after a Linux environment. It runs the image's init system allowing you to
> register long running services or test your application under a process supervisor."

The introducing PR #1662 states the motivating gap directly:

> "container runs each workload in an ephemeral VM, so there's no built-in way to keep
> a persistent Linux environment you can log into and work in."

> Container machines are "lightweight, persistent, and integrated Linux environments
> that feel like an extension of your Mac, created from standard OCI images with a
> familiar UX."

**Relationship to the per-container-VM model of `container run`:**

- `container run` (the base product) runs *each container as its own ephemeral
  lightweight VM* via Apple's Virtualization framework, then throws the VM away. Good
  for isolated app workloads; no persistent shell-in environment.
- `container machine` is a *separate* construct: a long-lived VM (one per target
  distro) that you log into, that mounts your macOS `$HOME`, and that boots a real init
  system. It is oriented at "edit on the Mac, build inside" development, not at hosting
  your `container run` containers.

So the correct framing is: it is **not** a Docker-Desktop-style single shared host VM
for all your containers (option a). Nothing in Apple's docs positions the machine as
the substrate for `container run`; `container run` keeps its own per-container VM model.
It is closer to a WSL2-style / multipass-style persistent dev VM (option b).
Whether one *could* additionally run container workloads inside a machine is covered in
Q3 — that is a user pattern, not the documented purpose.

Distinguishing host integrations (from docs):

- Your macOS `$HOME` is mounted into the VM (default read-write).
- The login user matches your host account and has passwordless `sudo` (per PR #1662).
- "One environment per target distro" — create separate machines for `alpine`,
  `ubuntu`, `debian`, each sharing the same `$HOME`/dotfiles.

---

## 2. INIT / SYSTEMD — the key question

**Answer: YES. A container machine boots the base image's own init system as PID 1.**
This is documented and explicit — it is a real init, not a bare rootfs that `run` execs
into.

From the docs:

> "It runs the image's init system allowing you to register long running services or
> test your application under a process supervisor."

> "Real Linux services for testing. Run a database or whatever your stack needs as a
> system service — `systemctl start postgresql` works on images with `systemd`
> installed."

From PR #1662:

> Each machine "keeps its filesystem and runs the image's own init system (such as
> **systemd or openrc**)."

So `systemctl` works when the image ships systemd; Alpine images run OpenRC instead.
`container machine run` execs a shell/command *into* the already-booted machine (as your
host user) — the init is running underneath it.

**Base image requirement / recommendations (from docs "Bring your own container
machine image"):**

> "Any Linux image that includes `/sbin/init` works as a container machine."

- Quickstart examples use `alpine:latest` (OpenRC).
- The docs provide a full **Ubuntu 24.04 + systemd** Dockerfile as the reference for a
  systemd machine. It installs `dbus systemd openssh-server ...`, runs
  `yes | unminimize`, clears `/etc/machine-id` and `/var/lib/dbus/machine-id`, sets
  `systemctl set-default multi-user.target`, and masks a set of units
  (`dev-hugepages.mount`, `sys-fs-fuse-connections.mount`,
  `systemd-update-utmp.service`, `systemd-tmpfiles-setup.service`,
  `console-getty.service`) plus disables `networkd-dispatcher.service`. This is the
  standard "systemd-in-a-container" hardening recipe.
- First-boot user provisioning: `container` runs a built-in setup script on first boot
  to create the user. You can override it with an executable `/etc/machine/create-user.sh`
  in the image, run once as root with `CONTAINER_UID`, `CONTAINER_GID`, `CONTAINER_USER`,
  `CONTAINER_HOME`, `CONTAINER_MACHINE_ID` env vars set.

Documented example of running systemd inside a machine: yes — the Ubuntu 24.04 Dockerfile
above plus the `systemctl start postgresql` line in the docs.

---

## 3. RUNNING PODMAN (OR DOCKER) INSIDE A MACHINE

**Answer: Not covered by Apple's own docs, but demonstrated to work by the community.**
Because a machine is a full Linux VM with a real init, podman runs *non-nested* (the
containers podman starts are regular Linux namespaces/cgroups inside the machine, not
another layer of VMs).

- Apple's `docs/container-machine.md` and the VS Code example **do not** mention running
  podman/docker inside a machine. (UNCONFIRMED from Apple primary docs.)
- Community discussion — containers/podman Discussion #27278 "Running Podman containers
  in Apple Container VM" (<https://github.com/containers/podman/discussions/27278>) —
  demonstrates installing and running **Podman inside an Apple container machine**
  (Fedora-based), optionally with systemd. Reported working, with these caveats tied to
  Apple's default machine kernel:
  - **Networking:** use legacy `iptables` rather than `nftables` — nft support is
    missing from the default kernel.
  - **IPv6:** only partial support; workaround is installing `procps-ng` and disabling
    IPv6 via `sysctl`.
  - **Memory:** the default machine gets only ~1 GiB RAM; bump it via
    `container machine set -n <name> memory=8G` (see Q5).
  - **Custom kernel:** users can build a custom kernel to remove these limitations.
  - The discussion positions Apple's machine VM alongside WSL2 / Kata as a "native VM
    provider," i.e. **no explicit nested-virtualization requirement to run ordinary
    OCI containers** inside the machine.

Caveat on running podman inside: this is a community-verified pattern, not an
Apple-supported/documented workflow. Treat the networking/IPv6/kernel caveats as real.

Docker (dockerd) inside a machine: **UNCONFIRMED** — not found in Apple docs or the
primary discussion above; only podman was demonstrated.

---

## 4. NESTED VIRTUALIZATION FLAG (`--virtualization`)

**Answer: `--virtualization` exposes `/dev/kvm` inside the machine — i.e. it enables
running *actual VMs / KVM guests* inside the machine. It is NOT required to run ordinary
containers or podman inside the machine.**

From the docs ("Nested virtualization and custom kernels"):

Requirements:
1. Apple Silicon **M3 or later** with **macOS 15 or later**.
2. A Linux kernel with **`CONFIG_KVM=y`** enabled — "The default kernel does not support
   this," so you must supply your own via `--kernel`.

Usage:

```bash
container machine create \
    --virtualization \
    --kernel /path/to/vmlinux-kvm \
    --name kvm-dev \
    alpine:latest

container machine run -n kvm-dev -- ls -l /dev/kvm   # verify /dev/kvm is exposed
```

Toggle on an existing machine:

```bash
container machine set -n dev virtualization=true kernel=/path/to/vmlinux-kvm
container machine stop dev
container machine run -n dev -- ls -l /dev/kvm
container machine set -n dev kernel=          # reset to default kernel
```

What it enables: the presence of `/dev/kvm` means workloads inside the machine that need
a hypervisor (KVM-based VMs, QEMU/KVM, nested VM tooling, some hardware-accelerated
emulation) can run. Running regular containers / podman does **not** need this
(confirmed by Q3's discussion running podman without nested virt). So:

- Running containers or podman inside a machine: `--virtualization` **not** needed.
- Running real VMs / KVM guests inside a machine: `--virtualization` + a `CONFIG_KVM=y`
  kernel + M3/macOS 15 **is** needed.

---

## 5. PERSISTENCE & RESET

**Answer: Yes, container machines are persistent — they keep their filesystem on disk,
and they survive across stop/start (and, per the design, across host reboots).**

From the docs:

> "Container machines are fast, lightweight and **persistent**."

> `container machine stop dev` — stop the machine.
> `container machine rm dev` — "delete, **including its persistent storage**."

> "Typically, you'll keep container machines for longer than a typical container."
> (VS Code example README.)

From PR #1662: each machine "keeps its filesystem" and is "persistent."

Storage / disk:
- Each machine has its own persistent filesystem derived from the base OCI image;
  writes inside the machine persist to that filesystem. `container machine rm` is what
  destroys the persistent storage.
- Exact on-disk location / disk-image format on the macOS host is **UNCONFIRMED** from
  primary docs (the docs describe persistence behaviorally, not the storage layout).
  It lives under `container`'s application data area, but I did not verify the path from
  a primary source.

Persistence across host reboots specifically:
- The feature is explicitly "persistent" and the filesystem is retained; a machine is
  not auto-deleted. **UNCONFIRMED** whether a running machine auto-restarts after a host
  reboot or whether you must `container machine run` (which boots it if stopped) again.
  The docs say `run` "boots it first" if the machine is stopped, which implies you
  re-launch it after a reboot; the *data* persists regardless.

Reset / recreate cleanly:
- Config changes (cpus, memory, home-mount, virtualization, kernel) via
  `container machine set ...` take effect after the next `stop` + `run`.
- Full clean reset = delete and recreate:

  ```bash
  container machine rm dev          # removes machine + persistent storage
  container machine create alpine:latest --name dev
  ```

- There is **no documented in-place "factory reset"** subcommand; recreate is the clean
  path. (UNCONFIRMED that any reset-without-delete exists.)

---

## Command / flag reference (from primary docs)

Subcommands: `create`, `run`, `list`/`ls`, `inspect`, `set`, `set-default`, `logs`,
`stop`, `delete`/`rm`. Alias for `machine` is `m`.

- `container machine create <image> --name <name>` — create from an OCI image.
  Flags seen in docs: `--name`, `--virtualization`, `--kernel <path>`. (`--set-default`,
  `--cpus`, `--memory`, `--home-mount` at create time appear in some secondary sources
  but the primary docs show cpus/memory/home-mount via `set`; treat create-time cpus/
  memory/home-mount flags as UNCONFIRMED against primary docs.)
- `container machine run [-n <name>] [-- <cmd>]` — open a shell or run one command;
  boots the machine if stopped.
- `container machine set -n <name> cpus=4 memory=8G` — resize (takes effect after next
  stop/start). Memory defaults to half of host memory. Home-mount is `rw` (default),
  `ro`, or `none`, e.g. via `set`. Also `virtualization=true kernel=<path>`.
- `container machine set-default <name>` — pick default so `-n` can be omitted.
- `container machine ls` / `inspect <name>` / `logs` / `stop <name>` / `rm <name>`.

---

## Honesty / confidence notes

- Q1, Q2, Q4, Q5 (persistence behavior, systemd/init, nested virt) are **well
  supported by Apple primary docs and the introducing PR.**
- Q3 (podman inside) is **community-verified, not Apple-documented.** Docker-inside is
  UNCONFIRMED.
- On-disk storage layout/path, host-reboot auto-restart behavior, and create-time
  cpus/memory/home-mount flags are **UNCONFIRMED** against primary docs — flagged inline.
