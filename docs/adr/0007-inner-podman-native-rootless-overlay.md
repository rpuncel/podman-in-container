# Inner podman uses native rootless overlay

Inner podman runs **rootless** with the **native `overlay`** storage driver and **no
`mount_program`**. `fuse-overlayfs` is not installed in the machine image at all, and the
rootful path is not taken.

Ordinarily podman inside another container cannot have this. The kernel refuses to stack
overlay on overlay, so an inner engine whose storage sits on the outer engine's overlay
filesystem has to route overlay through FUSE (`mount_program = "/usr/bin/fuse-overlayfs"`)
or give up rootless and run as root with `CAP_SYS_ADMIN` and `CAP_MKNOD`. The Podman
troubleshooting guide ranks the options for I/O-heavy builds as native `overlay` > `vfs` >
`fuse-overlayfs`, and reports FUSE-backed builds as slow to the point of hanging
(`docs/research/podman-nesting.md`). So nested podman must trade away either speed or
rootlessness.

Running the sandbox as a machine — a Linux VM with its own kernel, rather than a nested
container ([ADR-0002](0002-sandbox-is-a-machine.md)) — is what buys both at once. Inner
podman's store lands on the machine's own disk, a real filesystem rather than another
engine's overlay, and the guest kernel permits an unprivileged overlay mount inside a user
namespace. That second condition is not assumed: the machine's entrypoint performs a real
`mount -t overlay ... -o userxattr` in a user namespace at every boot and publishes the
answer in its init report, so a guest-kernel change that withdraws the capability surfaces
as a failed assertion rather than as mysteriously slow builds.

A machine booted from the image reports `graphDriverName: overlay`, `Native Overlay Diff:
true`, `Backing Filesystem: extfs`, and empty `graphOptions`.

Chosen because native overlay is the fastest of the three drivers and rootless is the
safest of the two privilege models, and nothing forces a choice between them here.

Rejected: **fuse-overlayfs**, which costs the FUSE userspace hop for no benefit once the
kernel driver is available. Rejected: **rootful inner podman**, which would buy native
overlay at the price of the user-namespace confinement that makes a compromised inner
engine survivable.

The image states the driver explicitly in `/etc/containers/storage.conf` rather than
leaning on podman's default, because *not* setting `mount_program` is the decision and
should be legible as one. Leaving `fuse-overlayfs` uninstalled is deliberate for the same
reason: it removes any path by which the machine could quietly degrade to it.

Trade-off: this ties the machine to a guest kernel that permits unprivileged overlay
mounts. Ubuntu's packaged podman lagging upstream is a related standing risk, noted in
[ADR-0004](0004-ubuntu-2404-machine-base-image.md). If a future guest kernel withdraws the
capability, the recovery is to install `fuse-overlayfs` and set `mount_program` — a rebuild
of the image, and so a deliberate change rather than a silent runtime degradation.
