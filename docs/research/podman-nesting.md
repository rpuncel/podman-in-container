# Podman "machine" concept & nested Podman (podman-in-container)

Research date: 2026-09-06. Sources are primary: docs.podman.io, the
`containers/podman` and `containers/common` GitHub repos, and Red Hat's
official blog. Claims that could not be pinned to a primary source are marked
**UNCONFIRMED**.

---

## 1. What "machine" means (macOS)

A `podman machine` is a **managed Linux virtual machine**, not a container. The
Podman client (CLI) on the macOS host talks over a socket to the Podman service
running *inside* that Linux VM, because containers are a Linux-kernel feature.

Verbatim from the man page:

> "`podman machine` is a set of subcommands that manage Podman's virtual machine."
>
> "Podman on MacOS and Windows requires a virtual machine. This is because
> containers are Linux - containers do not run on any other OS because
> containers' core functionality are tied to the Linux kernel. Podman machine
> must be used to manage MacOS and Windows machines, but can be optionally used
> on Linux."
>
> "All `podman machine` commands are rootless only."

Source: `podman-machine.1.md`
(https://github.com/containers/podman/blob/main/docs/source/markdown/podman-machine.1.md),
rendered at https://docs.podman.io/en/latest/markdown/podman-machine.1.html

### Providers (why the VM exists, and what runs it)

The man page's provider table (asterisk = default per platform):

| Platform | Provider |
| -------- | -------- |
| Linux    | qemu*    |
| MacOS    | libkrun* |
| MacOS    | applehv  |
| Windows  | wsl*     |
| Windows  | hyperv   |

So on macOS the two providers are **`libkrun`** (default) and **`applehv`**.
Mapping to the underlying host helper binaries:

- **`applehv`** uses macOS **Virtualization.framework**, driven by the
  **`vfkit`** helper binary. (Confirmed indirectly: Podman issue #28017,
  "[macOS Sequoia][applehv] vfkit crashes … Podman machine fails," ties the
  applehv provider to the `vfkit` process —
  https://github.com/containers/podman/issues/28017)
- **`libkrun`** uses the **`krunkit`** helper binary (libkrun VMM on Apple's
  Hypervisor Framework), and exposes a virtio-gpu device so GPU workloads can be
  offloaded to the host GPU. (Red Hat Developer, "How we improved AI inference
  on macOS Podman containers,"
  https://developers.redhat.com/articles/2025/06/05/how-we-improved-ai-inference-macos-podman-containers)

Note: The exact `applehv`→`vfkit` and `libkrun`→`krunkit` binary mapping is
well-established but is drawn from issue trackers / blog rather than the man
page itself. Treat the *provider names* as confirmed by the man page and the
*helper-binary names* as strongly-supported-but-not-in-the-man-page.

### Why "machine" and not "container"

"Machine" is literally a virtual machine — a full Linux kernel + userspace
booted under a hypervisor. A container is a set of namespaced/cgroup-isolated
processes sharing the host kernel. On macOS there is no Linux kernel to share,
so a real VM ("machine") is mandatory; containers then run *inside* that VM.
The term distinguishes the persistent VM layer from the containers it hosts.

### Lifecycle: long-lived, user-managed

The VM is a persistent, explicitly user-managed object with its own config,
not an ephemeral process. Config lives under
`$XDG_CONFIG_HOME/containers/podman/machine/`. Lifecycle subcommands
(from the man page):

- `init` — "Initialize a new virtual machine"
- `start` — "Start a virtual machine"
- `stop` — "Stop a virtual machine"
- `restart` — "Restart a virtual machine"
- `rm` — "Remove a virtual machine"
- plus `set`, `ssh`, `cp`, `inspect`, `list`, `info`, `os`, `reset`.

Source: `podman-machine.1.md` (same URL as above).

---

## 2. Auto-mounts (what a macOS machine gets "for free")

**Yes — `podman machine` auto-mounts host directories into the VM by default,
and on macOS the defaults are broad.** These defaults come from
`containers.conf`, key `volumes` in the `[machine]` section.

Verbatim from `containers.conf.5.md`:

> **volumes**=["$HOME:$HOME"]
>
> Host directories to be mounted as volumes into the VM by default.
> Environment variables like $HOME as well as complete paths are supported for
> the source and destination. An optional third field `:ro` can be used to
> tell the container engines to mount the volume readonly.
>
> On Mac, the default volumes are:
>
>    `[ "/Users:/Users", "/private:/private", "/var/folders:/var/folders" ]`

Source: `containers/common` `docs/containers.conf.5.md`
(https://github.com/containers/common/blob/main/docs/containers.conf.5.md)

So on macOS, out of the box the VM sees:

- **`/Users`** → all user home directories on the Mac
- **`/private`** → includes `/private/etc`, `/private/tmp`, `/private/var`
- **`/var/folders`** → macOS per-user temp/cache dirs

Security implication: any container that bind-mounts one of these host paths (or
that runs with enough host reach inside the VM) can touch essentially the whole
user data area and much of the system, since the VM has `/Users`, `/private`,
and `/var/folders` mounted by default. This is "free" access granted at the VM
layer before any per-container `-v` flag.

### Configuring / overriding

- Per-machine at creation: `podman machine init --volume/-v source:target[:options]`
  with options `ro`, `rw` (default), `security_model=[model]`. On macOS the
  default 9p security model is `none` (so symlinks work).
  Forbidden mount *targets*: `/bin /boot /dev /etc /home /proc /root /run /sbin
  /sys /tmp /usr /var` (subdirectories are allowed).
  > "Default volume mounts are defined in *containers.conf*. Unless changed,
  > the default values is `$HOME:$HOME`."
  Source: `podman-machine-init.1.md.in`
  (https://github.com/containers/podman/blob/main/docs/source/markdown/podman-machine-init.1.md.in),
  https://docs.podman.io/en/latest/markdown/podman-machine-init.1.html
- Globally: edit the `[machine] volumes=[...]` list in `containers.conf`.

Note: passing `--volume` overrides/sets what the machine mounts; the macOS
three-path default is what applies when you do not change it. **UNCONFIRMED**
whether `libkrun` vs `applehv` differ in *how* these are mounted (virtiofs vs
9p) — issue trackers report differing bind-mount permission behavior between
the two providers, but the default *path list* above is provider-independent.

---

## 3. Nested Podman (podman-in-podman / podman-in-a-container)

Primary source: Red Hat blog, **"How to use Podman inside of a container"**
(https://www.redhat.com/en/blog/podman-inside-container), plus the Podman
troubleshooting guide
(https://github.com/containers/podman/blob/main/troubleshooting.md). The
reference image is **`quay.io/podman/stable`**, which is pre-configured for
nesting.

### What the reference image bakes in

- A `podman` user with subuid/subgid ranges for the inner user namespace:
  ```dockerfile
  RUN useradd podman; \
      echo podman:10000:5000 > /etc/subuid; \
      echo podman:10000:5000 > /etc/subgid;
  ```
- Dedicated volumes so the inner storage is not overlay-on-overlay (the kernel
  disallows stacking overlay on overlay):
  ```dockerfile
  VOLUME /var/lib/containers
  VOLUME /home/podman/.local/share/containers
  ```
- Inner storage driver **`fuse-overlayfs`** by default:
  > "We use fuse-overlayfs as our container storage within the container. Other
  > people have used VFS storage driver, but this is not that efficient."

### Minimum viable sets (from the blog, exact commands)

**a) `--privileged` (simplest, discouraged for security):**
```bash
podman run --privileged quay.io/podman/stable podman run ubi8 echo hello           # rootful-in-rootful
podman run --user podman --privileged quay.io/podman/stable podman run ubi8 echo hello   # rootless-in-rootful
```

**b) Rootful-inner without `--privileged` (minimum caps):**
```bash
podman run --cap-add=sys_admin,mknod --device=/dev/fuse \
  --security-opt label=disable quay.io/podman/stable podman run ubi8-minimal echo hello
```
- `CAP_SYS_ADMIN` — "required for the Podman running as root inside of the
  container to mount the required file systems"
- `CAP_MKNOD` — "required for Podman running as root inside of the container to
  create the devices in `/dev`"
- `--device=/dev/fuse` — enables the fuse-overlayfs storage driver inside
- `--security-opt label=disable` — "SELinux does not allow containerized
  processes to mount all of the file systems required"

**c) Rootless-inner (MOST SECURE, minimum set):**
```bash
podman run --user podman --security-opt label=disable \
  --device /dev/fuse quay.io/podman/stable podman run alpine echo hello
```
- **Does NOT require `CAP_SYS_ADMIN` or `CAP_MKNOD`.** "The user namespace
  automatically confines privileges, making this significantly more secure than
  rootful-in-rootful."
- Still needs: `--user podman` (a user with a subuid/subgid range),
  `--device /dev/fuse` (for fuse-overlayfs), and `--security-opt label=disable`
  (on an SELinux host).

So the **minimum viable rootless-inner set** = run as a user that has
subuid/subgid ranges + `/dev/fuse` + (on SELinux) `label=disable`. No added
Linux capabilities, no `--privileged`.

**Why privileges are needed at all:** container engines need "multiple UIDs.
Most container images need more than one UID to work," plus the ability to
mount filesystems and use `clone` for user namespaces. Rootless-inner satisfies
the UID need via the mapped user namespace instead of real privilege.

### Docker as the outer runtime (stricter defaults)

Docker's default seccomp profile blocks calls Podman needs, so you must relax
seccomp:
```bash
docker run --cap-add=sys_admin --cap-add mknod --device=/dev/fuse \
  --security-opt seccomp=unconfined --security-opt label=disable \
  quay.io/podman/stable podman run ubi8-minimal echo hello
```
> Docker's stricter default seccomp policy requires either disabling it entirely
> or "use a Podman security policy by using
> `--seccomp=/usr/share/containers/seccomp.json`".

(Under Podman-as-outer, Podman applies its own seccomp profile that already
permits these calls, so `seccomp=unconfined` is not listed as required.)
AppArmor is not called out as a specific requirement in this blog; on
AppArmor-based hosts the equivalent relaxation would parallel the SELinux
`label=disable` step. **UNCONFIRMED** for exact AppArmor flags.

### Storage / config tweaks & the socket alternative

- storage.conf: to force fuse-overlayfs on a host where rootless overlay fails,
  set `mount_program = "/usr/bin/fuse-overlayfs"` under `[storage.options]`
  (troubleshooting.md, "Rootless 'podman build' fails when using OverlayFS":
  rootless users lack privilege to call `mknod` for native overlay, so install
  and configure fuse-overlayfs).
- If instead you bind the host's storage into the container, troubleshooting.md
  ("Running Podman inside a container…") warns you must mount **at least**
  `/var/lib/containers/storage/`, and if you do, also `/run/libpod` and
  `/run/containers/storage`, or Podman mis-detects restarts and loses track of
  running containers.
- **Remote-socket alternative (explicitly insecure):**
  ```bash
  podman run -v /run:/run --security-opt label=disable \
    quay.io/podman/stable podman --remote run busybox echo hi
  ```
  > "this is extremely insecure. The processes within the container can totally
  > take over the host machine."

Sources: https://www.redhat.com/en/blog/podman-inside-container ;
https://github.com/containers/podman/blob/main/troubleshooting.md

---

## 4. Performance (inner storage driver when nested)

From the Podman troubleshooting guide
(https://github.com/containers/podman/blob/main/troubleshooting.md):

- **Symptom:** "Using the default `overlay` storage driver, a `COPY`, `ADD`, or
  an I/O intensive `RUN` line … is very slow or hangs completely when running a
  `podman build` inside the running parent container." (This refers to
  fuse-overlayfs, the default used inside containers.)
- **Fastest option — native `overlay`:** bind a **local host directory** to
  `/var/lib/containers/storage` as a volume in the child container. This lets
  the inner Podman use the kernel's native overlay driver instead of
  fuse-overlayfs. Native overlay avoids overlay-on-overlay (the reason the image
  declares `VOLUME /var/lib/containers`) and avoids the FUSE userspace hop.
- **Fallback — `vfs`:** switch the storage driver to `vfs`, described as
  "slower but significantly faster than `fuse-overlayfs`" for this I/O-intensive
  build case. (Note the tradeoff: vfs does full copies rather than layered COW,
  so it uses much more disk, but for the heavy-build case it beat fuse-overlayfs
  here.)

Ranking for the nested / heavy-I/O-build scenario, per the docs:
**native `overlay` (needs host dir bound to inner storage) > `vfs` >
`fuse-overlayfs`**.

Requirements to make **native overlay** work nested:
1. Inner storage must not sit on top of another overlay → provide a real
   backing filesystem, i.e. bind a host directory (or a non-overlay volume) at
   `/var/lib/containers/storage`.
2. Native overlay for a **rootful** inner Podman needs `mknod`/mount privilege
   (`CAP_MKNOD`, `CAP_SYS_ADMIN`) — the same caps from section 3(b). Rootless
   users "do not have the privileges to use `mknod`," which is exactly why the
   rootless path defaults to fuse-overlayfs + `/dev/fuse`. (troubleshooting.md,
   "Rootless 'podman build' fails when using OverlayFS.")

Consequence: the *fast* native-overlay path pairs naturally with the *less
secure* rootful-inner (caps) or a bound host storage dir; the *secure*
rootless-inner path pays the fuse-overlayfs performance cost unless you give it
a bound host storage directory.

---

## 5. "Machine" vs "container" — the conceptual distinction

They are **not** the same thing. Crisp distinction:

| | **Machine** (podman machine) | **Container** |
|---|---|---|
| What it is | A full **virtual machine**: its own Linux **kernel** + userspace under a hypervisor | A set of host-kernel **processes** isolated via namespaces + cgroups |
| Kernel | Brings and boots its own kernel | **Shares** the host/VM kernel |
| Isolation boundary | Hardware-virtualization (hypervisor) | Kernel namespaces (weaker boundary) |
| Lifetime / intent | **Long-lived, persistent, explicitly user-managed** (`init`/`start`/`stop`/`rm`); stateful config on disk | Typically **ephemeral**, cheap to create/destroy, disposable |
| Boot cost | Boots an OS (seconds+, heavier) | Starts a process (near-instant, light) |
| Why it exists on macOS | Because there is no Linux kernel to share | Because you want isolated app processes |

Man-page framing (section 1) is the anchor: the machine exists precisely
*because* containers need a Linux kernel and macOS/Windows do not provide one —
i.e. a container cannot substitute for the machine; the machine is the host that
runs containers.

### Naming guidance for your outer layer

- Call your outer layer a **"machine"** only if it is a persistent,
  hypervisor-backed VM with its own kernel that you manage over a lifecycle
  (init/start/stop) — the Podman-machine model.
- Call it a **"container"** if it is a namespaced process tree sharing a kernel,
  even if it in turn runs nested containers (that is the podman-in-a-container
  model in sections 3–4). Running containers *inside* it does not make it a
  "machine."
- The deciding questions: **Does it boot its own kernel? Is it persistent and
  lifecycle-managed as an object?** Yes to both → "machine." Otherwise →
  "container" (and "nested" / "outer container" if you need to signal that it
  hosts more containers).

---

## Source list

- Podman machine man page —
  https://docs.podman.io/en/latest/markdown/podman-machine.1.html ·
  https://github.com/containers/podman/blob/main/docs/source/markdown/podman-machine.1.md
- Podman machine init man page —
  https://docs.podman.io/en/latest/markdown/podman-machine-init.1.html ·
  https://github.com/containers/podman/blob/main/docs/source/markdown/podman-machine-init.1.md.in
- containers.conf(5) (default machine volumes, incl. macOS defaults) —
  https://github.com/containers/common/blob/main/docs/containers.conf.5.md
- Red Hat blog, "How to use Podman inside of a container" —
  https://www.redhat.com/en/blog/podman-inside-container
- Podman troubleshooting guide (nested Podman, storage drivers, performance) —
  https://github.com/containers/podman/blob/main/troubleshooting.md
- Red Hat Developer, "How we improved AI inference on macOS Podman containers"
  (libkrun/krunkit, GPU) —
  https://developers.redhat.com/articles/2025/06/05/how-we-improved-ai-inference-macos-podman-containers
- Podman issue #28017 (applehv ↔ vfkit) —
  https://github.com/containers/podman/issues/28017
