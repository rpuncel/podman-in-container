"""Credential references, and fetching their values on the host (ADR-0006).

A *credential reference* names where a secret lives in whatever store the user
already runs -- it is never the secret itself, so a workspace config is safe to
keep in a dotfiles repo. Resolution runs on the host, at machine launch, and
triggers the user's normal interactive unlock (GPG pinentry, `op signin`) when the
store is locked. That is the whole point of ADR-0006: the master key stays on the host and
only the resolved values ever reach the machine.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass


class CredentialError(Exception):
    """A reference could not be understood, or its value could not be fetched."""


def _run(*command: str) -> str:
    """Run a secret-store command on the host and return the value it prints.

    Only stdout is captured. A locked store prompts on the terminal -- GPG pinentry,
    `op signin` -- and those prompts go to stderr, so swallowing stderr would turn an
    unlock into an apparent hang. For the same reason there is no timeout: the wait
    here is a human typing a passphrase.
    """
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, text=True)
    except FileNotFoundError:
        raise CredentialError(f"{command[0]} is not installed on this host") from None
    if result.returncode != 0:
        raise CredentialError(f"`{' '.join(command)}` failed (exit {result.returncode})")
    return result.stdout.splitlines()[0] if result.stdout else ""


def _fetch_env(locator: str) -> str:
    try:
        return os.environ[locator]
    except KeyError:
        raise CredentialError(f"environment variable {locator} is not set") from None


def _fetch_pass(locator: str) -> str:
    # `pass show` prints the password on the first line; anything after it is the
    # entry's free-form notes, which are not part of the credential.
    return _run("pass", "show", locator)


def _fetch_op(locator: str) -> str:
    return _run("op", "read", f"op://{locator}")


def _fetch_gh(locator: str) -> str:
    return _run("gh", "auth", "token")


def _fetch_keychain(locator: str) -> str:
    service, _, account = locator.partition("/")
    command = ["security", "find-generic-password", "-s", service]
    if account:
        command += ["-a", account]
    return _run(*command, "-w")


@dataclass(frozen=True)
class _Backend:
    """One secret store: how its references are written, and how to read one.

    `prefix` is both halves of the syntax -- what `parse` strips off and what
    `Reference.__str__` puts back -- so a store's spelling lives in one place.
    """

    name: str
    prefix: str
    fetch: Callable[[str], str]
    takes_locator: bool = True


# `gh` is the odd one out: it takes no locator, because `gh auth token` already knows
# which token it means. No prefix here is a prefix of another, so match order is free.
_BACKENDS = (
    _Backend("env", "env:", _fetch_env),
    _Backend("pass", "pass:", _fetch_pass),
    _Backend("op", "op://", _fetch_op),
    _Backend("keychain", "keychain:", _fetch_keychain),
    _Backend("gh", "gh", _fetch_gh, takes_locator=False),
)

_BY_NAME = {backend.name: backend for backend in _BACKENDS}

_SYNTAX = "env:NAME, pass:PATH, op://VAULT/ITEM/FIELD, keychain:SERVICE[/ACCOUNT], gh"


@dataclass(frozen=True)
class Reference:
    """Where one credential lives: a backend, and a locator within it.

    The locator is what follows the backend's prefix -- `work/github-pat` for
    `pass:work/github-pat` -- and is empty for `gh`, which locates nothing.
    """

    backend: str
    locator: str

    @classmethod
    def parse(cls, text: str) -> Reference:
        """Read a reference as written in a secret manifest, e.g. `pass:work/pat`."""
        for backend in _BACKENDS:
            if not text.startswith(backend.prefix):
                continue
            locator = text[len(backend.prefix) :]
            if bool(locator) != backend.takes_locator:
                break  # a bare `pass:` locates nothing; a `gh` with a locator is a typo
            return cls(backend.name, locator)
        raise CredentialError(
            f"{text!r} is not a credential reference: expected one of {_SYNTAX}"
        )

    def resolve(self) -> str:
        """Fetch the referenced value on the host, unlocking the store if it asks."""
        value = _BY_NAME[self.backend].fetch(self.locator)
        if not value:
            # A store that answers with nothing has not given us a credential. Saying
            # so here beats injecting an empty string that authenticates nowhere and
            # fails obscurely inside the machine.
            raise CredentialError(f"{self} resolved to an empty value")
        return value

    def __str__(self) -> str:
        """The reference as a secret manifest would write it."""
        return _BY_NAME[self.backend].prefix + self.locator
