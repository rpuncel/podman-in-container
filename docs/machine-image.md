# The machine image

Ubuntu 24.04 + systemd + inner podman, at `images/machine/`. Built on Apple's reference
container-machine Dockerfile (ADR-0004) plus the podman layer this project needs.

```bash
container build -t pic-machine:latest -f images/machine/Containerfile images/machine
container machine create pic-machine:latest --name pic-global --memory 4G
```

`pic launch` does both, so this is the manual equivalent rather than a separate step.

## Shape

- **`Containerfile`** — packages, Apple's systemd-in-a-container hardening, and the
  static configuration (`/etc/containers/storage.conf`, the `containers.conf` drop-in,
  the iptables alternative).
- **`rootfs/usr/local/sbin/pic-machine-init`** — the entrypoint, run by a systemd
  oneshot unit at every boot. It handles what the image cannot know at build time,
  above all the **machine user**: the outer engine creates it on first boot with the
  *host* account's UID, so the image can neither name it nor predict its UID.
- **`rootfs/usr/local/sbin/pic-overlay-probe`** — one real unprivileged overlay mount,
  the evidence behind ADR-0007.

The entrypoint writes `/run/pic/machine-init.json` when it is done. That file, not
mere reachability, is what marks a machine ready: the engine's exec channel comes up
well before the machine reaches `multi-user.target`, so `Machine.wait_until_initialised`
polls for the report.

Nothing here is engine-specific. The setup runs from a systemd unit rather than Apple's
`/etc/machine/create-user.sh` first-boot hook, so any engine that boots `/sbin/init`
runs it (ADR-0004).

## Guest gotchas the entrypoint handles

Each of these was found by booting the image and watching inner podman fail (issue #4).

| Gotcha | Symptom | Handling |
| --- | --- | --- |
| ADR-0002 records no nftables in the guest kernel | container networking silently broken | `iptables` alternative pinned to `iptables-legacy`, re-asserted each boot — though see the finding below: the premise did not reproduce |
| Machine user has no subordinate IDs | rootless podman degrades to a single-UID mapping that breaks most images | `/etc/subuid` + `/etc/subgid` entries provisioned per machine user |
| No login session for `container machine run` | `systemd --user` never starts, so podman drops from the systemd cgroup manager to cgroupfs | `loginctl enable-linger` per machine user |
| `/` mounts private | podman warns and loses mounts made inside its user namespace | `mount --make-rshared /` |
| `/dev/net/tun` is 0600 | every rootless `podman run` dies with `open("/dev/net/tun"): Permission denied` | `chmod 0666`, because no udev runs to apply the usual rule |

## Findings worth knowing

- **`libpam-systemd` is not optional.** It is only a *Recommends* of `systemd`, so
  `--no-install-recommends` drops it. Without it PAM cannot set `XDG_RUNTIME_DIR`,
  `systemd --user` refuses to start, and lingering never produces `/run/user/<uid>` —
  which is what rootless podman needs to work in.
- **ADR-0002's nftables premise did not reproduce.** ADR-0002 pins the legacy backend
  because "the default guest kernel lacks nftables" — a community report, not something
  this project had measured. On the kernel a machine actually boots here (6.18.35,
  `container` 1.3.1), `iptables-nft` creates chains happily; both backends work. The
  legacy pinning is kept — the acceptance criterion asks for it, it costs nothing, and a
  future guest kernel may yet drop nftables — but it is insurance, not a workaround, and
  **ADR-0002 is worth revisiting** on this point.
- **Nothing currently exercises either backend.** Rootless podman on slirp4netns programs
  no host firewall rules at all: after running a container, `iptables-legacy -t nat -S`
  shows no podman or CNI chains. So "podman uses the iptables-legacy firewall driver" is
  assertable only as "the `iptables` alternative resolves to legacy", which is what the
  acceptance test claims and no more. A real firewall assertion arrives with the
  default-deny egress work, where rules are the point.
- **Ubuntu 24.04 ships podman 4.9.3 on the CNI backend, and packages no netavark.** The
  `[network] firewall_driver` key in `containers.conf` configures netavark, so today it
  is inert; the legacy backend is actually selected by the `iptables` alternative, which
  is the binary CNI shells out to. The key is set anyway so the machine stays correct
  when podman ≥ 5 (netavark by default) lands — the upgrade ADR-0004 anticipates.
- **`systemd-detect-virt` reports `container-other`, not a VM.** That is an artefact of
  Apple's reference recipe setting `ENV container=container`, which is how systemd
  decides it is containerized; it is not evidence of nesting. Non-nesting is instead
  proved from podman's own store: a real `extfs` backing filesystem, a native overlay
  diff, and no `mount_program`. Podman inside a container cannot show that combination —
  it cannot stack overlay on overlay, so its store lands on the outer engine's
  `overlayfs` and it must fall back to fuse-overlayfs (docs/research/podman-nesting.md).
- **Ubuntu's stock `ubuntu` account (UID 1000) is removed** at build time. It is unwanted
  in a sandbox, and it would otherwise masquerade as the machine user: the entrypoint
  identifies machine users by login shell, since a UID threshold cannot — the real one
  arrives with the host's UID (501 on macOS), *below* the usual 1000 cutoff.
- **`/etc/containers/storage.conf` must set `runroot` and `graphroot`.** Once a
  `[storage]` section exists, rootful podman requires them explicitly and otherwise
  fails every command with `runroot must be set`, which shows up as four failed podman
  units at boot. Rootless podman ignores both and derives its own paths.

## Known limitations

- **`container machine run` is not a login session**, so it sets no `XDG_RUNTIME_DIR`
  and podman falls back to the cgroupfs cgroup manager. Lingering makes the runtime
  directory exist, but nothing puts it in the exec environment. Harmless for the
  workloads acceptance (a) covers; it needs settling before running systemd-based
  workloads, which is where the cgroup manager starts to matter. Tracked as #14.
- **`podman machine` cannot boot this image.** `podman machine init` has no way to take
  a base image, so the fallback engine can build the image but not run a machine from
  it, and `PodmanMachineEngine.create` says so rather than handing back a machine
  without any of this setup. Provisioning the podman fallback — or retiring it — is
  tracked as #13.
