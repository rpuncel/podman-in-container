"""Credential references, and fetching their values on the host (ADR-0006).

A *credential reference* names where a secret lives in whatever store the user
already runs -- it is never the secret itself, so a workspace config is safe to keep
in a dotfiles repo. Resolution runs on the host, at machine launch, and triggers the
user's normal interactive unlock (GPG pinentry, `op signin`) when the store is
locked. That is the whole point of ADR-0006: the master key stays on the host and
only the resolved values ever reach the machine.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


class CredentialError(Exception):
    """A reference could not be understood, or its value could not be fetched."""


def _fetch_env(locator: str) -> str:
    try:
        return os.environ[locator]
    except KeyError:
        raise CredentialError(f"environment variable {locator} is not set") from None


def _run(*command: str) -> str:
    """Run a secret-store command on the host and return its single-line output."""
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError:
        raise CredentialError(f"{command[0]} is not installed on this host") from None
    if result.returncode != 0:
        raise CredentialError(
            f"`{' '.join(command)}` failed: {result.stderr.strip() or result.returncode}"
        )
    return result.stdout.splitlines()[0] if result.stdout else ""


def _fetch_pass(locator: str) -> str:
    # `pass show` prints the password on the first line; anything after it is the
    # entry's free-form notes, which are not part of the credential.
    return _run("pass", "show", locator)


def _fetch_op(locator: str) -> str:
    # The locator is the whole `op://vault/item/field` URI, which is what `op read`
    # takes; there is nothing for us to pick apart.
    return _run("op", "read", locator)


def _fetch_gh(locator: str) -> str:
    return _run("gh", "auth", "token")


def _fetch_keychain(locator: str) -> str:
    service, _, account = locator.partition("/")
    command = ["security", "find-generic-password", "-s", service]
    if account:
        command += ["-a", account]
    return _run(*command, "-w")


# Each backend is a scheme in the reference plus the host command that fetches it.
# `gh` is the odd one out: it takes no locator, because `gh auth token` already
# knows which token it means.
_BACKENDS = {
    "env": _fetch_env,
    "pass": _fetch_pass,
    "op": _fetch_op,
    "gh": _fetch_gh,
    "keychain": _fetch_keychain,
}

_SCHEMES = {
    "env:": "env",
    "pass:": "pass",
    "op://": "op",
    "keychain:": "keychain",
}


@dataclass(frozen=True)
class Reference:
    """Where one credential lives: a backend and, for all but `gh`, a locator in it."""

    backend: str
    locator: str

    @classmethod
    def parse(cls, text: str) -> Reference:
        """Read a reference as written in a secret manifest, e.g. `pass:work/pat`."""
        if text == "gh":
            return cls("gh", "")
        for prefix, backend in _SCHEMES.items():
            if not text.startswith(prefix):
                continue
            body = text[len(prefix) :]
            if not body:
                break  # a bare `pass:` or `op://` names nothing
            # `op://` is a URI that `op read` wants whole, so its locator keeps the
            # scheme; the `<scheme>:<locator>` backends drop theirs.
            return cls(backend, text if backend == "op" else body)
        raise CredentialError(
            f"{text!r} is not a credential reference: expected one of "
            f"env:NAME, pass:PATH, op://VAULT/ITEM/FIELD, keychain:SERVICE[/ACCOUNT], gh"
        )

    def resolve(self) -> str:
        """Fetch the referenced value on the host, unlocking the store if it asks."""
        return _BACKENDS[self.backend](self.locator)

    def __str__(self) -> str:
        """The reference as a secret manifest would write it."""
        if not self.locator:
            return self.backend
        if self.locator.startswith(f"{self.backend}:"):
            return self.locator  # `op://...` carries its own scheme
        return f"{self.backend}:{self.locator}"
