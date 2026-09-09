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
    workspace = _Document.read(home / WORKSPACES_DIR / f"{name}.yaml")

    base_name = workspace.extends()
    base = _Document.read(home / BASES_DIR / f"{base_name}.yaml") if base_name else _NOTHING
    if base.extends():
        raise ConfigError(
            f"base config '{base_name}' may not itself extend another base: "
            "layering is one level deep"
        )

    return WorkspaceConfig(
        name=name,
        egress_allow=_merge_egress(base.egress(), workspace.egress()),
        # The secret manifest is base entries overridden by key by the workspace, so a
        # workspace can swap the one credential that differs (spec item 37 of #1).
        secrets={**base.secrets(), **workspace.secrets()},
    )


class _Document:
    """One config file, read and validated, able to say where a problem was.

    Every check here exists because the quiet failure mode is bad: a mistyped
    `exclude` that got ignored would leave an endpoint reachable. So anything this
    file says that we would not otherwise act on is an error, named with its path.
    """

    def __init__(self, path: Path | None, body: dict) -> None:
        self.path = path
        self.body = body
        self._reject_unknown_keys(body, _TOP_LEVEL_KEYS, "")

    @classmethod
    def read(cls, path: Path) -> _Document:
        try:
            text = path.read_text()
        except FileNotFoundError:
            raise ConfigError(f"no config at {path}") from None
        try:
            body = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"{path} is not valid YAML: {exc}") from None

        if body is None:
            body = {}
        if not isinstance(body, dict):
            raise ConfigError(f"{path} should hold a mapping, not {type(body).__name__}")
        return cls(path, body)

    @classmethod
    def nothing(cls) -> _Document:
        """What a workspace that extends nothing layers over: an empty base.

        It has no path because it has no file, which is safe only because an empty
        body gives every check below nothing to complain about.
        """
        return cls(None, {})

    def _error(self, message: str) -> ConfigError:
        return ConfigError(f"{self.path}: {message}")

    def _reject_unknown_keys(self, mapping: dict, known: set[str], prefix: str) -> None:
        unknown = sorted(set(mapping) - known)
        if unknown:
            raise self._error(
                f"unknown {prefix}key(s) {', '.join(unknown)}; "
                f"expected one of {', '.join(sorted(known))}"
            )

    def _section(self, key: str) -> dict:
        section = self.body.get(key) or {}
        if not isinstance(section, dict):
            raise self._error(f"`{key}` should hold a mapping")
        return section

    def extends(self) -> str | None:
        """The base config this one layers over, if it names one."""
        extends = self.body.get("extends")
        if extends is not None and not isinstance(extends, str):
            raise self._error("`extends` should name one base config")
        return extends

    def egress(self) -> dict[str, tuple[str, ...]]:
        """The `allow` and `exclude` lists, each a list of endpoints."""
        section = self._section("egress")
        self._reject_unknown_keys(section, _EGRESS_KEYS, "egress: ")
        return {key: self._endpoints(section, key) for key in _EGRESS_KEYS}

    def _endpoints(self, egress: dict, key: str) -> tuple[str, ...]:
        listed = egress.get(key) or ()
        # A bare `allow: ghcr.io` would otherwise allow-list one hostname's letters.
        if isinstance(listed, str) or not isinstance(listed, (list, tuple)):
            raise self._error(f"`egress: {key}` should hold a list of endpoints")
        return tuple(str(endpoint) for endpoint in listed)

    def secrets(self) -> dict[str, Reference]:
        """The secret manifest, parsed now so a bad reference fails before launch."""
        parsed = {}
        for name, text in self._section("secrets").items():
            if not isinstance(text, str):
                raise self._error(f"secret '{name}' should be a credential reference")
            try:
                parsed[name] = Reference.parse(text)
            except CredentialError as exc:
                raise self._error(f"secret '{name}': {exc}") from None
        return parsed


_NOTHING = _Document.nothing()


def _merge_egress(base: dict, workspace: dict) -> tuple[str, ...]:
    """base union workspace-adds minus workspace-excludes (spec item 36 of #1)."""
    excluded = set(workspace["exclude"])
    allowed = [*base["allow"], *workspace["allow"]]
    return tuple(dict.fromkeys(e for e in allowed if e not in excluded))
