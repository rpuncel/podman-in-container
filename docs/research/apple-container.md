# Apple `container` / Containerization — Research Notes

Research into Apple's `container` CLI and the underlying `Containerization` Swift framework,
open-sourced by Apple in 2025. Focus: how it differs from Docker Desktop / `podman machine`,
and its suitability for running a container engine (podman) inside a container.

**Primary sources (all fetched):**

- apple/container README — https://github.com/apple/container/blob/main/README.md
- Technical overview — https://github.com/apple/container/blob/main/docs/technical-overview.md
- Command reference — https://github.com/apple/container/blob/main/docs/command-reference.md
- Volumes — https://github.com/apple/container/blob/main/docs/volumes.md
- Networking — https://github.com/apple/container/blob/main/docs/networking.md
- Host integration — https://github.com/apple/container/blob/main/docs/host-integration.md
- Container machine — https://github.com/apple/container/blob/main/docs/container-machine.md
- Containerization framework — https://github.com/apple/containerization

Requirements note: `container` "relies on the new features and enhancements present in macOS 26."
It can run on macOS 15 but with documented networking limitations that Apple states it has no
plans to fix. (technical-overview.md)

---

## 1. ARCHITECTURE — how it runs Linux containers on macOS

**CONFIRMED: one lightweight VM per container** (not a single shared VM like Docker Desktop
or `podman machine`).

Verbatim, from the technical overview:

> "the typical way to run Linux containers is to launch a Linux virtual machine (VM) that hosts
> all of your containers."

`container` deliberately rejects that shared-VM model:

> "Using the open source Containerization package, it runs a lightweight VM for each container
> that you create."

The README frames the same claim: `container` lets you "create and run Linux containers as
lightweight virtual machines on your Mac."

Reasons Apple gives for the per-container VM design (verbatim):

- **Security**: "Each container has the isolation properties of a full VM, using a minimal set
  of core utilities and dynamic libraries to reduce resource utilization and attack surface."
- **Privacy**: "When sharing host data using `container`, you mount only necessary data into
  each VM. With a shared VM, you need to mount all data that you may ever want to use into the VM."
- **Performance**: "Containers created using `container` require less memory than full VMs, with
  boot times that are comparable to containers running in a shared VM."

Host-side process/daemon architecture (verbatim, technical-overview.md):

- "The `container-apiserver` is a launch agent that launches when you run the `container system
  start` command, and terminates when you run `container system stop`."
- "When `container-apiserver` starts, it launches an XPC helper `container-core-images` that
  exposes an API for image management and manages the local content store, and another XPC helper
  `container-network-vmnet` for the virtual network."
- "For each container that you create, `container-apiserver` launches a container runtime helper
  `container-runtime-linux` that exposes the management API for that specific container."

macOS frameworks used (verbatim): "The Virtualization framework for managing Linux virtual
machines and their attached devices. The vmnet framework for managing the virtual network to
which the containers attach. XPC for interprocess communication. Launchd for service management.
Keychain services for access to registry credentials. The unified logging system for application
logging."

Sources: technical-overview.md, README.md.

> UNCONFIRMED: The in-guest init process (the `Containerization` project describes an init
> called `vminitd`) is **not** named in `container`'s technical-overview.md. That detail comes
> from the separate apple/containerization repo and was not directly quoted here. Treat the
> `vminitd` name as belonging to the Containerization framework, not verified from container's docs.

---

## 2. "MACHINE" CONCEPT — is there a `podman machine` analog?

Nuanced answer. There are **two distinct things**, and neither is the single shared VM that
`podman machine` gives you:

### (a) `container system` — the host-side control-plane daemon (NOT a VM you manage)

For running normal containers, the user manages a **background service**, not a long-lived VM.
The VM lifecycle for `container run` is per-container and hidden.

Verbatim from command-reference.md:

- `container system start` — "Starts the container services and (optionally) installs a default
  kernel. It will start the `container-apiserver` and background services."
- `container system stop` — "Stops the container services and deregisters them from launchd."

Other `container system` subcommands: `status`, `version`, `logs`, `df`, `dns create/delete/list`,
`kernel set`, `property list`.

So `container system start` is analogous in *ergonomics* to `podman machine start` (you run it
once before using containers), but architecturally it starts a **launchd-managed host daemon
(`container-apiserver`)**, not a Linux VM. Each container gets its own throwaway VM behind the
scenes (see §1).

### (b) `container machine` — an OPTIONAL persistent Linux dev environment

Separately, there IS a command literally named `machine`, but it is a *different* concept from
`podman machine`. Per container-machine.md:

> "Container machine provides a highly integrated Linux environment that works seamlessly on your
> Mac. Container machines are fast, lightweight and persistent."

> "A container machine is modeled after a Linux environment ... It runs the image's init system
> allowing you to register long running services."

Subcommands (command-reference.md): `container machine create`, `run`, `list`, `inspect`, `set`,
`set-default`, `logs`, `stop`, `delete`. "If the container machine is stopped, `run` boots it first."

This is a persistent, user-managed Linux environment (a dev-box style VM you name and keep
around) — you can "Create as many container machines as you have target distros." It is an
opt-in convenience, **not** the mandatory shared VM that all containers run inside. Ordinary
`container run` workloads still get their own per-container VMs.

**Bottom line for the question:** For normal container workloads, VM lifecycle is per-container
and hidden; the user only manages a host daemon via `container system start/stop`. There is no
mandatory single shared VM. A `container machine` exists but is an optional persistent dev
environment, not the Docker-Desktop/podman-machine "one VM hosts all containers" model.

Sources: command-reference.md, container-machine.md, technical-overview.md.

---

## 3. HOST DIRECTORY MOUNTING — flags, and default auto-mount behavior

**CONFIRMED: mounts are strictly opt-in per run. No host paths are auto-mounted by default.**

The volumes doc describes host↔container sharing only via explicit flags:

- `--volume` (verbatim example):
  ```
  container run --volume ${HOME}/Desktop/assets:/content/assets docker.io/python:alpine ls -l /content/assets
  ```
- `--mount` (verbatim example):
  ```
  container run --mount source=${HOME}/Desktop/assets,target=/content/assets docker.io/python:alpine ls -l /content/assets
  ```

Framing (verbatim): "With the `--volume` option of `container run`, you can share data between
the host system and one or more containers."

There is **no documentation of any automatic host mount** (no default `$HOME`, `/Users`, or cwd
sharing). This follows directly from the per-container-VM privacy rationale in §1: "you mount
only necessary data into each VM." This is a meaningful contrast with Docker Desktop and
`podman machine`, which commonly auto-share `/Users` (or `$HOME`) into the shared VM by default.

Related host-integration features (opt-in, host-integration.md):

- `--ssh` — "mount the macOS SSH authentication socket into your container" for passwordless
  git/SSH.
- `--localhost <ipv4-address>` — create a DNS domain so a container can reach a host service.
  Documented limitation: "Creating a localhost domain disables Private Relay. The local domain
  packet filter rule is removed on a restart."

> Known bug worth noting (mounting edge case): apple/container#2148 — "A file mount nested inside
> a directory mount replaces the parent share." And #1890 requests nested bind mounts / making a
> subdir read-only within a mount (not yet supported).

Sources: volumes.md, host-integration.md.

---

## 4. NESTED CONTAINERS — running podman/docker (and its own containers) inside

Status: **container-in-container / docker-in-docker is expected to work; `--privileged` is not
supported (and appears unnecessary because each container is already its own VM); nested
*virtualization* (KVM/VMs-in-container) needs a user-supplied custom kernel.**

Evidence from primary GitHub issues:

- **apple/container#87** — "Running docker-in-docker inside container (container-in-container)"
  (CLOSED). Maintainer @crosbymichael replied verbatim:
  > "Yes, you should be able to run the dind images with container. Give it a try and let us
  > know if you run into any blockers."
  This is the strongest primary-source signal that running a nested container engine is
  supported/intended. Because every `container` container is a full lightweight VM with its own
  Linux kernel, an inner engine has real kernel features to work with (unlike sharing a host
  daemon socket).

- **apple/container#206** — request for `--privileged` (CLOSED). Key findings:
  - `--privileged` is **not** a recognized flag: `container run ... --privileged` returns
    `Error: Unknown option '--privileged'`.
  - Maintainer @jglogan (verbatim): "Since your containerized workload runs in its own VM some
    docker-isms aren't necessary." The reporter confirmed the Dagger engine (which normally needs
    `--privileged` + `CAP_SYS_ADMIN` under Docker) worked **without** `--privileged` on
    `container`. So the lack of a privileged flag does not necessarily block engines that assume it.

- **apple/container#376** — "Virtualization support in containers" (CLOSED, request). Verbatim:
  > "Containerization already exposes the nested virtualization capabilities on any SoCs that
  > support it. We should expose a flag on run/create that expose it as well. The kata kernel we
  > use by default doesn't have kvm on iirc, so a user would need to provide their own kernel
  > however."
  Takeaway: nested *VM* capability (KVM) exists at the framework level on supported Apple silicon,
  but the **default guest kernel lacks KVM**; running VMs-inside-a-container requires supplying a
  custom kernel. This concerns nested *virtualization*, not plain nested *containers*.

- Related: **apple/container#1737** (Redroid / Android-in-container) and #191 ("ability to run
  inside of a macOS VM") show the community actively pushing on nested/edge scenarios.

**Assessment for the podman-in-container goal:**

- Running podman *containers* inside an Apple `container` container: LIKELY SUPPORTED — the inner
  environment is a real VM with its own kernel, and the maintainer explicitly endorsed dind. This
  is favorable for podman, which is designed to run rootless without a privileged daemon.
- `--privileged` / explicit `CAP_SYS_ADMIN`: NOT available as a flag today, but often unnecessary
  given the per-VM isolation (confirmed for Dagger).
- Running full nested *VMs* inside a container: requires a custom KVM-enabled kernel.

> UNCONFIRMED: There is no dedicated primary-source doc/tutorial demonstrating **podman**
> specifically running nested containers inside `container`. The support inference rests on the
> per-container-VM architecture plus the maintainer's dind endorsement (#87) and the Dagger
> success (#206). Actual podman-inside-container behavior (rootless user namespaces, cgroups v2
> availability, fuse-overlayfs vs native overlay in the guest) is NOT verified from primary docs
> and should be tested empirically.

Sources: apple/container issues #87, #206, #376, #1737, #191 (GitHub).

---

## 5. NETWORKING — exposing ports to the macOS host

**CONFIRMED: each container gets its own IP directly reachable from the host, AND there is
explicit port publishing.**

Verbatim from networking.md:

> "Every container gets an IP address on its network, always reachable by that IP from the host
> and from other containers on the same network."

Port publishing via `--publish` / `-p`:

- Syntax: `[host-ip:]host-port:container-port[/protocol]` (protocol `tcp` or `udp`).
- Verbatim example:
  ```
  container run -d --rm -p 127.0.0.1:8080:8000 node:latest npx http-server
  ```

So you can either (a) hit the container directly on its per-container IP (no publish needed for
host-to-container), or (b) publish/forward a port to a host address.

**Differences / limitations vs Docker:**

- **Per-container routable IP is the primary model** — unlike Docker Desktop on macOS, where
  containers live behind the VM and you generally must publish ports. Here the container IP is
  "always reachable by that IP from the host."
- **No zero-config service discovery on custom networks** (verbatim networking.md): bare hostname
  resolution doesn't work on custom networks — "the kind of zero-configuration, Compose-style
  service discovery some users expect" is unsupported; workaround is to "reach a container on a
  custom network by its IP address instead." (Tracked open upstream.)
- **macOS 15 limitations** (technical-overview.md): on macOS 15, container-to-container
  communication (network isolation), multiple networks, and reliable IP assignment are all
  broken/limited due to vmnet timing; macOS 26 is required for the full feature set.
- **Privileged/low ports**: apple/container#1985 (open bug) — binding a host port < 1024 on an
  explicit host IP (e.g. `127.0.0.1:80`) fails with a permission error, though `0.0.0.0:80`
  succeeds. #626 (port ranges when publishing) was a separate request.

Sources: networking.md, technical-overview.md, apple/container issue #1985.

---

## Summary of confirmations

| # | Question | Verdict |
|---|----------|---------|
| 1 | Separate lightweight VM per container? | **CONFIRMED** — "it runs a lightweight VM for each container that you create." |
| 2 | A `podman machine`-style single shared VM the user manages? | **NO shared VM.** `container system start` runs a host daemon; per-container VMs are hidden. A separate optional `container machine` = persistent Linux dev env, not the shared-VM model. |
| 3 | Auto-mounts host paths by default? | **NO** — mounts strictly opt-in via `--volume`/`--mount`. |
| 4 | podman/docker nested inside? | **Likely yes** (dind endorsed by maintainer, per-VM isolation). `--privileged` unsupported but often unneeded. Nested *VMs* need custom KVM kernel. Not verified specifically for podman. |
| 5 | Port exposure to host? | **CONFIRMED** — per-container routable IP + `-p/--publish` forwarding. No Compose-style DNS discovery on custom networks; macOS 15 networking limited. |
