"""The per-workspace config file, and the layering that produces the merged one.

A workspace's flag-hostile settings -- its egress allow-list (ADR-0005) and its
secret manifest (ADR-0006) -- live in `~/.config/pic/workspaces/<name>.yaml`. Shared
settings live in a named *base config* under `~/.config/pic/bases/<name>.yaml` that
a workspace picks up with `extends: <base>`.

The two merges are deliberately asymmetric, because the two settings fail
differently. Egress is `base ∪ workspace-adds − workspace-excludes`: tightening is
one line, and any widening is stated outright in the workspace file where a human
reviewing it will see it. The secret manifest is overridden per key, so a workspace
can swap the one credential that differs -- its own fine-grained PAT, say -- without
restating the rest.

This module plus `pic.credentials` is the whole host-side resolver: callable
directly, with no machine involved.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .credentials import CredentialError, Reference

WORKSPACES_DIR = "workspaces"
BASES_DIR = "bases"

_TOP_LEVEL_KEYS = {"extends", "egress", "secrets"}
_EGRESS_KEYS = {"allow", "exclude"}

# What a workspace that extends nothing merges over.
_NO_BASE = {"extends": None, "egress": {"allow": (), "exclude": ()}, "secrets": {}}


class ConfigError(Exception):
    """A config file is missing, malformed, or says something we can't honour."""


@dataclass(frozen=True)
class WorkspaceConfig:
    """One workspace's settings, with any base it extends already merged in.

    `egress_allow` is the endpoints the workspace may reach, in declaration order
    (base first). `secrets` maps each credential's name to where it lives; the values
    are fetched only when `resolve_secrets` asks for them.
    """

    name: str
    egress_allow: tuple[str, ...] = ()
    secrets: dict[str, Reference] = field(default_factory=dict)

    def resolve_secrets(self) -> dict[str, str]:
        """Fetch every referenced credential on the host, keyed as the manifest was.

        Fetching a locked store prompts the user for their unlock, so this is a
        launch-time call, not something to make casually.
        """
        return {name: reference.resolve() for name, reference in self.secrets.items()}


def default_config_home() -> Path:
    """Where pic keeps its configs: `$XDG_CONFIG_HOME/pic`, else `~/.config/pic`."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return (Path(xdg) if xdg else Path.home() / ".config") / "pic"


def load(name: str, config_home: Path | None = None) -> WorkspaceConfig:
    """Load workspace `name`, merged over the base config it extends (if any)."""
    home = config_home if config_home is not None else default_config_home()
    document = _read(home / WORKSPACES_DIR / f"{name}.yaml")

    base_name = document["extends"]
    base = _read(home / BASES_DIR / f"{base_name}.yaml") if base_name else _NO_BASE
    if base["extends"]:
        raise ConfigError(
            f"base config '{base_name}' may not itself extend another base: "
            "layering is one level deep"
        )

    return WorkspaceConfig(
        name=name,
        egress_allow=_merge_egress(base["egress"], document["egress"]),
        secrets=_merge_secrets(base["secrets"], document["secrets"]),
    )


def _read(path: Path) -> dict:
    """Parse one config file into a normalised document: every section a mapping.

    Rejects anything we wouldn't otherwise act on, so a config that survives this is
    a config the merges below can trust.
    """
    try:
        text = path.read_text()
    except FileNotFoundError:
        raise ConfigError(f"no config at {path}") from None
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from None

    if document is None:
        document = {}
    if not isinstance(document, dict):
        raise ConfigError(f"{path} should hold a mapping, not {type(document).__name__}")
    _reject_unknown_keys(path, document, _TOP_LEVEL_KEYS, "")

    egress = _section(path, document, "egress")
    _reject_unknown_keys(path, egress, _EGRESS_KEYS, "egress: ")
    return {
        "extends": document.get("extends"),
        "egress": {key: _endpoints(path, egress, key) for key in _EGRESS_KEYS},
        "secrets": _references(path, _section(path, document, "secrets")),
    }


def _reject_unknown_keys(path: Path, document: dict, known: set[str], prefix: str) -> None:
    """Refuse a key we don't understand: a typo here silently widens egress."""
    unknown = sorted(set(document) - known)
    if unknown:
        raise ConfigError(
            f"{path} has unknown {prefix}key(s) {', '.join(unknown)}; "
            f"expected one of {', '.join(sorted(known))}"
        )


def _section(path: Path, document: dict, key: str) -> dict:
    section = document.get(key) or {}
    if not isinstance(section, dict):
        raise ConfigError(f"{path}: `{key}` should hold a mapping")
    return section


def _endpoints(path: Path, egress: dict, key: str) -> tuple[str, ...]:
    """One egress list, as a list of hostnames -- a bare string is a mistake, not one."""
    listed = egress.get(key) or ()
    if isinstance(listed, str) or not isinstance(listed, (list, tuple)):
        raise ConfigError(f"{path}: `egress: {key}` should hold a list of endpoints")
    return tuple(str(endpoint) for endpoint in listed)


def _references(path: Path, secrets: dict) -> dict[str, Reference]:
    """Parse the manifest at load time, so a bad reference fails long before launch."""
    parsed = {}
    for name, text in secrets.items():
        if not isinstance(text, str):
            raise ConfigError(f"{path}: secret '{name}' should be a credential reference")
        try:
            parsed[name] = Reference.parse(text)
        except CredentialError as exc:
            raise ConfigError(f"{path}: secret '{name}': {exc}") from None
    return parsed


def _merge_egress(base: dict, workspace: dict) -> tuple[str, ...]:
    """base ∪ workspace-adds − workspace-excludes (spec #36)."""
    excluded = set(workspace["exclude"])
    allowed = [*base["allow"], *workspace["allow"]]
    return tuple(dict.fromkeys(e for e in allowed if e not in excluded))


def _merge_secrets(base: dict, workspace: dict) -> dict[str, Reference]:
    """Base entries, overridden by key by the workspace (spec #37)."""
    return {**base, **workspace}
