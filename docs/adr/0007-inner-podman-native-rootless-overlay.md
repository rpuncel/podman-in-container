# Inner podman uses native rootless overlay

Inner podman runs **rootless** with the **native `overlay`** storage driver and **no
`mount_program`**. `fuse-overlayfs` is not installed in the machine image at
all, and the rootful fallback is not taken.

This settles the choice ADR-0004 and the round-2 grill left open pending a spike
("target rootless + native overlay, spike-gated fallback to fuse-overlayfs then
rootful"). The spike (issue #4) probed the guest kernel directly — an unprivileged
`mount -t overlay ... -o userxattr` inside a user namespace — and it succeeds, so the
condition the fallback was gated on does not hold. A machine booted from the image
reports `graphDriverName: overlay`, `Native Overlay Diff: true`, and empty
`graphOptions`.

Chosen because native overlay is the fastest of the three (docs/research/podman-nesting.md
ranks native overlay > vfs > fuse-overlayfs for I/O-heavy builds) and rootless is the
most secure. Running the sandbox as a machine rather than a nested container is exactly
what makes both available at once: nested podman must pay fuse-overlayfs *or* give up
rootless, which is the trade-off ADR-0002 bought its way out of.

The image states the driver explicitly in `/etc/containers/storage.conf` rather than
relying on podman's default, because *not* setting `mount_program` is the decision. The
entrypoint re-probes the kernel on every boot and publishes the answer in its init
report, so a guest-kernel change that withdraws unprivileged overlay surfaces as a
failed assertion rather than as mysteriously slow builds.

Trade-off: this ties us to a guest kernel that permits unprivileged overlay mounts. If a
future kernel withdraws that, the fallback ladder in ADR-0004's trade-off note is still
the answer — install `fuse-overlayfs` and set `mount_program` — but that is a rebuild
of the image, a deliberate change rather than a silent runtime degradation.
