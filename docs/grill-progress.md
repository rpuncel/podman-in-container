# Grilling progress — resume note

**Status: FRONTIER EMPTY.** Every branch of the design tree visited; awaiting user confirmation of shared understanding, then → `/to-spec`. ADRs 0001–0006 written; CONTEXT.md glossary current.

## Settled (see CONTEXT.md glossary + docs/adr/)

- **Goal**: a performant, safe sandbox on macOS for an agent harness (Claude Code) that manipulates container workloads; pre-grant broad permissions because the sandbox contains the blast radius.
- **Deliverable**: a Containerfile for the machine image + an entrypoint + setup docs (machine instantiation) + test cases, including a `compose.yaml` that runs in the sandbox.
- **Agent runs inside the sandbox** — ADR-0001.
- **Sandbox = a machine** (persistent Linux VM; Apple `container machine` primary, `podman machine` fallback; systemd PID 1; podman non-nested inside) — ADR-0002.
- **Isolation unit = workspace** (user-defined group of repos sharing a machine); image store shared host-globally — ADR-0003.
- **Outer engine**: Apple `container` first, keep image/entrypoint engine-agnostic so podman-as-outer is a drop-in fallback.
- **Lifecycle**: machines are persistent and resettable (reset = `rm` + `create`).
- **Env facts**: macOS 15.7.7 arm64; `container` 1.3.1, `podman` 5.8.2 (machine running, libkrun); macOS-15 host→workload networking is degraded (full networking wants macOS 26) — but this only affects *human preview*, not the agent loop (agent tests from inside the machine).

## Settled this session (round 2)

- **Q12 — egress policy** (CONTEXT.md glossary): per-workspace, configurable/tunable list of outbound endpoints + minimal injected creds. In scope: public **and private** registries (pull); public **and private** package indexes; **git push over HTTPS-token** (opt-in per workspace); Anthropic API (given). Credential *mechanism* is still open (Q16).
- **Q13 — workspace membership**: launch-time `--workspace <name>`, default global workspace. **Config map queued as a concrete future improvement** (not v1).
- **Q14 — machine base image**: Ubuntu 24.04 + systemd — ADR-0004.
- **Q15 — inner podman**: target **rootless + native overlay**, spike-gated fallback to fuse-overlayfs then rootful. (ADR deferred until spike #1 confirms guest-kernel unprivileged overlay.)

## Settled this session (round 3)

- **Q16 — credential injection**: **host-side secret resolver** at machine launch. Per-workspace manifest maps each credential to a reference in the store the user already uses (`pass:`, `op://`, `gh` via `gh auth token`, `keychain:`, `env:`); resolver fetches on host (triggers existing interactive unlock — GPG pinentry / `op signin`), injects only resolved values into machine **tmpfs**, wired to git credential helper + containers `auth.json` + `.npmrc`/`pip.conf` + `ANTHROPIC_API_KEY`. Master keys never cross into the machine; nothing baked into image; reset wipes tmpfs. Keychain is one backend, not primary. OPEN sub-decision: gh host-token reuse vs dedicated per-workspace fine-grained PAT (Q16b).
- **Q17 — egress enforcement**: **default-deny** chosen (bite it off first; relax if it becomes a slog). Mechanism recommendation pending confirmation: per-workspace filtering forward-proxy allow-listing by hostname/SNI + machine firewall (iptables-legacy) blocking all direct egress. **ADR-0005 to write once mechanism confirmed.**
- **Q18 — mount policy**: confirmed. `home-mount=none`; workspace repos bind-mounted **rw** at `/workspace/<repo>`; image store shared host-globally; multiple repos side-by-side. PLUS new requirement → **Context mount** (CONTEXT.md glossary): additional host paths exposed for reference, ro by default, rw opt-in, mix-and-match at launch, independent of workspace membership. Details in Q18b.

## Open frontier — round 4 (my recommendations in brackets)

- **Q16b — gh token scope**: reuse host `gh auth token` (convenient, full GitHub scope) vs dedicated per-workspace fine-grained PAT (least-privilege, matches default-deny). [(b) dedicated fine-grained PAT for work; (a) as easy path for throwaway/personal]
- **Q17b — egress mechanism**: confirm filtering forward-proxy (hostname/SNI allow-list, wildcard domains) + firewall blocks direct egress + only the human tunes the allow-list per workspace (agent cannot widen its own egress). [as stated → ADR-0005]
- **Q18b — context mounts**: confirm ro-default + `:rw` opt-in per mount + namespace `/context/<name>` + launch-time `--context <path>[:ro|rw][=name]`, workspace-config association queued with Q13's config map.
### Settled (round 4 partial)

- **Q19 — reset UX**: `pic reset --workspace <name>` = `rm` + `create`, wipes runtime state. Image store is **host-global on a shared mount (option a)** — lives *outside* any machine, so reset never touches it (survives incidentally, no re-pull). Consistent with ADR-0003; no revision. A separate `--deep-clean` would be the only thing that nukes the shared store (future, not v1).
- **Q20 — human-preview networking (macOS 15)**: **defer for v1**. Document the limitation; rely on the agent's internal-network testing; best-effort host port-forward later, gated by spike #2.

### Settled (round 4 complete)

- **Q16b — git push auth**: **dedicated per-workspace fine-grained PAT** (work); reuse host `gh auth token` as easy path for throwaway/personal.
- **Q17b — egress mechanism**: filtering forward-proxy (hostname/SNI, wildcards) + firewall blocks all direct egress + human-only allow-list tuning — **ADR-0005** written.
- **Q18b — context mounts**: confirmed. ro-default + `:rw` opt-in + `/context/<name>` + launch-time `--context <path>[:ro|rw][=name]`. User flag: the more per-workspace options, the more a config mechanism is wanted up front → Q21.

### Settled (round 5)

- **Q21 — config mechanism (v1)**: per-workspace **YAML config** at `~/.config/pic/workspaces/<name>.yaml`. **Required in config**: egress allow-list + secret manifest (flag-hostile). **Optional in config or launch flags**: repo membership + context mounts (flags = ad-hoc/override, mix-and-match). Pulls Q13's config-map forward into v1 for the parts that need it. NEW requirement from user → config **layering** (Q21b): egress list + secret manifest are re-defined across workspaces, so a **shared base + per-workspace tuning** is wanted. (Config-file structure is implementation → lives here, NOT in CONTEXT.md.)

### Settled (round 6)

- **Q21b — config layering**: **multiple named base configs**; a workspace `extends: <base>` (maps to work=`pass` / personal=`op`). Merge: egress allow-list = base ∪ workspace-adds **minus** optional workspace-excludes (tighter always allowed, wider must be stated — matches default-deny); secret manifest = base entries **overridden by key** by the workspace.

### Settled (round 7 — LAST NODE, frontier now empty)

- **Q22 — `compose.yaml` shape**: minimal multi-service fixture — in-repo-built app service + datastore (e.g. postgres) on a user-defined network, `depends_on`, named volume for db data, app exposes a port; agent reaches app over machine-internal network. **systemd-based service variant is IN SCOPE for v1** (proves the systemd-workload requirement behind ADR-0002).
- **Q23 — acceptance coverage**: confirmed as listed — (a) boot + inner podman non-nested; (b) build+run single workload; (c) compose up + inter-service + agent reaches app internally; (d) egress default-deny (allowed OK, disallowed BLOCKED — the ADR-0005 negative test); (e) credential injection (git push over injected HTTPS token OK, no secret persists post-reset); (f) mount policy (repo rw, home absent, context mount ro write-denied); (g) image store shared across two workspaces (2nd pull = cache hit); (h) reset wipes runtime state, image store survives. Out of scope: macOS-15 human-preview networking (Q20).
- **Q24 — harness**: pytest suite (Poetry-managed) shelling out to podman/compose **inside the machine**; `compose.yaml` an in-repo fixture. **Machine lifecycle is itself a (session-scoped) pytest fixture** — create + teardown, so tests never assume a hand-provisioned machine.
- **Credential model** promoted to **ADR-0006** (host-side resolver; no master keys cross the boundary; dedicated per-workspace fine-grained PAT for git push).

## Queued spikes (`/prototype` — technical, not grilling)

1. **Podman-in-container-machine on macOS 15**: create a machine from a systemd image, install/run podman, run a workload. Verify: iptables-legacy firewall driver, RAM bump (`set memory=`), native rootless overlay vs fuse-overlayfs.
2. **Host→workload preview networking** extent on macOS 15 (how much is actually degraded).

## Research already done

- `docs/research/apple-container.md` — Apple `container` architecture, mounts (opt-in), networking.
- `docs/research/podman-nesting.md` — podman machine, auto-mounts, nested-podman requirements.
- `docs/research/apple-container-machine.md` — `container machine` boots systemd; podman-in-machine confirmed; gotchas.

## After the frontier closes

Write remaining ADRs if any new hard-to-reverse decisions surface, then move to `/to-spec` → `/to-tickets` → `/implement` (per the main flow). Fold spike results into the implementation.
