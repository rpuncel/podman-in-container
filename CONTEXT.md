# Podman-in-Container

A performant, safe sandbox for running AI agent harnesses (e.g. Claude Code) that manipulate container workloads on a macOS host. The agent runs *inside* an isolated environment so it can be granted broad permissions without putting the host at risk.

## Language

**Sandbox**:
The isolated environment on the macOS host where the agent runs and where its container workloads execute. It is the security boundary: the blast radius of a rogue or mistaken agent is confined to it. Realized as a **machine**.
_Avoid_: box, jail

**Machine**:
The persistent Linux VM that realizes a sandbox: an Apple `container machine` (primary) or a `podman machine` (fallback). Because it is a full Linux host with its own kernel, podman runs inside it normally rather than nested, and its init (systemd, if the base image provides it) manages workloads.
_Avoid_: VM (loosely), box

**Agent harness**:
The AI tool (Claude Code or similar) that manipulates containers. It runs *inside* the sandbox, never on the host.
_Avoid_: agent (ambiguous), assistant, harness (alone)

**Inner podman**:
The Podman engine running inside the machine that runs the agent's workloads. Distinguished from the outer engine on the host (Apple `container` or podman) that creates and manages the machine itself. Not nested: it runs as it would on any Linux host.
_Avoid_: podman (unqualified, when the outer/inner distinction matters)

**Workload**:
A container or compose stack the agent runs inside the sandbox via inner podman.
_Avoid_: job, task, service (when meaning the containers themselves)

**Image store**:
Inner podman's cache of pulled and built image layers. Shared host-globally across all sandboxes so images are pulled/built once, not per project.
_Avoid_: image cache, registry cache

**Workspace**:
A user-defined group of related repositories (typically a workstream), managed as a unit and sharing one machine. The unit of runtime isolation: workloads are isolated *between* workspaces, not between repos within a workspace. A default/global workspace catches repos not assigned to a named one.
_Avoid_: project, group, workstream (as the canonical term)

**Runtime state**:
A workspace's running containers, named volumes, networks, and published ports. Isolated per workspace, so one workspace's agent cannot touch another's running workloads.
_Avoid_: container state, session state

**Egress policy**:
The per-workspace set of outbound endpoints the agent is allowed to reach — public and private registries, public and private package indexes, git push (HTTPS-token), and the Anthropic API — together with the minimal credentials injected to reach them. Configurable and tunable per workspace. The injected credential set is exactly this list and nothing more. Enforced default-deny: only listed endpoints are reachable.
_Avoid_: firewall, allowlist (alone), network policy

**Context mount**:
A host filesystem path exposed into the machine for the agent to *reference* — related repositories, source of dependency services, worked examples, a shared knowledge/context repository — as distinct from the workspace's own editable **repos**. Read-only by default; read-write is opt-in per mount. Attachable ad-hoc at launch and mix-and-match, independent of workspace membership.
_Avoid_: volume, bind mount (as the canonical term), reference repo

**Workspace config**:
The per-workspace YAML on the host at `~/.config/pic/workspaces/<name>.yaml` holding the settings that are hostile to flags: the workspace's **egress policy** allow-list and its **secret manifest**. Shared settings live in a named **base config** it `extends`. Egress merges as base ∪ workspace-adds minus workspace-excludes; the secret manifest merges as base entries overridden by key.
_Avoid_: settings, profile, config (unqualified)

**Base config**:
A named config under `~/.config/pic/bases/<name>.yaml` that many **workspace configs** share by declaring `extends: <name>`. Extends nothing itself: layering is one level deep.
_Avoid_: parent, template, default config

**Secret manifest**:
A workspace's map from credential name (`git_token`, `anthropic_api_key`) to a **credential reference**. Exactly the credential set that gets injected into the machine, and nothing more.
_Avoid_: secrets file, vault, credential list

**Credential reference**:
Where one credential lives in a store the user already runs — `pass:`, `op://`, `gh`, `keychain:` or `env:` — never the credential itself, so a **workspace config** is safe to keep in a dotfiles repo. Resolved on the host at launch (ADR-0006).
_Avoid_: secret, pointer, credential (when the value is meant)
