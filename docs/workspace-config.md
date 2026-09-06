# Workspace config

Each [workspace](../CONTEXT.md) has a YAML config on the host holding the settings
that are hostile to command-line flags: its **egress policy** allow-list (ADR-0005)
and its **secret manifest** (ADR-0006). Settings shared between workspaces live in a
**base config** that a workspace `extends`.

```
~/.config/pic/
├── bases/
│   └── work.yaml          # shared egress + secrets, extended by many workspaces
└── workspaces/
    ├── global.yaml        # the default workspace
    └── acme.yaml
```

`~/.config` here is `$XDG_CONFIG_HOME` when that is set.

## A workspace config

```yaml
# ~/.config/pic/workspaces/acme.yaml
extends: work

egress:
  allow:
    - registry.acme.example      # this workspace's private registry
  exclude:
    - ghcr.io                    # the base allows it; this workspace doesn't need it

secrets:
  git_token: pass:acme/github-pat
```

...over a base:

```yaml
# ~/.config/pic/bases/work.yaml
egress:
  allow:
    - api.anthropic.com
    - ghcr.io
    - "*.pythonhosted.org"

secrets:
  anthropic_api_key: op://Private/Anthropic/api-key
  git_token: gh
```

which merges to an allow-list of `api.anthropic.com`, `*.pythonhosted.org` and
`registry.acme.example`, and a manifest of the base's `anthropic_api_key` with
`git_token` swapped for the workspace's own PAT.

Every key is optional. A workspace that names neither section (and extends nothing)
reaches nothing and injects nothing — default-deny all the way down.

## How the merge works

**Egress** is `base ∪ workspace-adds − workspace-excludes`. Tightening a base takes
one line under `exclude`; widening has to be written out under `allow`, in the
workspace file, where a human reviewing the workspace sees it. An `exclude` beats an
`allow` of the same endpoint. Endpoints are matched by hostname/TLS SNI and may be
wildcards (`*.pythonhosted.org`) — this file just carries the strings; the filtering
proxy inside the machine does the matching.

**Secrets** are base entries **overridden by key** by the workspace, so a workspace
can swap the one credential that differs without restating the rest.

Layering is one level deep: a workspace extends a base, and a base extends nothing.

Unknown keys are an error rather than being ignored, because the quiet failure mode
here is bad: a mistyped `exclude` would silently leave an endpoint reachable.

## Credential references

A manifest entry names *where* a credential lives, never the credential itself, so a
config is safe to keep in a dotfiles repo. `pic` resolves references on the host at
launch and injects only the resolved values into the machine (ADR-0006); resolving
from a locked store triggers that store's normal interactive unlock.

| Reference | Resolved by | Notes |
| --- | --- | --- |
| `env:ANTHROPIC_API_KEY` | the launching shell's environment | what the tests use |
| `pass:acme/github-pat` | `pass show` | first line only; GPG pinentry may prompt |
| `op://Private/Anthropic/api-key` | `op read` | may prompt for `op signin` |
| `gh` | `gh auth token` | the host `gh` token, whole-scope — the easy path for throwaway workspaces |
| `keychain:pic-acme` | `security find-generic-password` | `keychain:<service>[/<account>]` |

For a work workspace, prefer a dedicated fine-grained PAT (`pass:`/`op://`/`keychain:`)
over `gh`, which hands the machine the full scope of your host token.

## Using it

The resolver is host-side and callable on its own, with no machine involved:

```python
from pic import workspace_config

config = workspace_config.load("acme")
config.egress_allow            # ('api.anthropic.com', '*.pythonhosted.org', 'registry.acme.example')
config.secrets                 # {'anthropic_api_key': Reference(...), 'git_token': Reference(...)}
config.resolve_secrets()       # {'anthropic_api_key': 'sk-...', ...} -- fetches, may prompt
```
