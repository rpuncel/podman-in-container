"""Acceptance (a): the machine boots, and inner podman runs non-nested inside it.

These assert against a real machine booted from the pic machine image, so they are
the proof behind ADR-0002's central bet -- that putting the sandbox in a VM lets
inner podman run as it would on any Linux host, rather than paying the
nested-podman tax catalogued in docs/research/podman-nesting.md.
"""

from __future__ import annotations

import json

# The outer engine's own default is 1 GiB, which ADR-0002 flags as too small.
ONE_GIB_IN_KB = 1024 * 1024


def podman_info(machine) -> dict:
    return json.loads(machine.exec("podman", "info", "--format", "json").stdout)


def test_systemd_is_pid_one(machine):
    assert machine.exec("cat", "/proc/1/comm").stdout.strip() == "systemd"


def test_machine_ram_is_raised_above_the_engine_default(machine):
    meminfo = machine.exec("cat", "/proc/meminfo").stdout
    total_kb = next(
        int(line.split()[1]) for line in meminfo.splitlines() if line.startswith("MemTotal:")
    )
    assert total_kb > ONE_GIB_IN_KB


def test_machine_init_reports_what_it_provisioned(machine):
    report = machine.init_report()
    assert report["firewall_driver"] == "iptables-legacy"
    assert report["native_rootless_overlay"] is True
    assert report["machine_users"], "no machine user was provisioned for rootless podman"


def test_boot_leaves_no_failed_units(machine):
    failed = machine.exec("systemctl", "--failed", "--no-pager", "--no-legend").stdout
    assert failed.strip() == "", f"units failed during boot:\n{failed}"


def test_iptables_resolves_to_the_legacy_backend(machine):
    # ADR-0002 requires the legacy backend, because it records the guest kernel as
    # having no nftables. This asserts the alternative resolves that way -- which is
    # all that is assertable today: rootless podman on slirp4netns programs no host
    # firewall rules, so nothing here exercises either backend. See
    # docs/machine-image.md, which records that the nft backend in fact also works
    # on the kernel measured.
    assert "legacy" in machine.exec("iptables", "--version").stdout


def test_inner_podman_runs_non_nested(machine):
    """Inner podman's store sits on the machine's own disk, driving overlay directly.

    This is what non-nested buys, and it is why it is checkable: podman inside a
    container cannot stack overlay on overlay, so its store lands on the outer
    engine's `overlayfs` and it must fall back to a fuse-overlayfs mount_program
    (docs/research/podman-nesting.md). A real backing filesystem plus a native
    overlay diff plus no mount_program is a combination nested podman cannot show.
    """
    info = podman_info(machine)
    store = info["store"]

    assert store["graphStatus"]["Backing Filesystem"] == "extfs"
    assert store["graphDriverName"] == "overlay"
    assert store["graphStatus"]["Native Overlay Diff"] == "true"
    assert "mount_program" not in store["graphOptions"]
    # And it gets all of that while staying rootless, which nested podman must give
    # up to use the kernel overlay driver at all.
    assert info["host"]["security"]["rootless"] is True


def test_inner_podman_runs_a_workload(machine):
    assert "Hello from Docker!" in machine.exec("podman", "run", "--rm", "hello-world").stdout
