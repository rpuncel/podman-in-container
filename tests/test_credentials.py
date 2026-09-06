"""Seam 2, half one: credential references and their host-side resolution.

ADR-0006 puts resolution on the host so that master keys never enter the machine.
Only the `env:` backend is exercised end to end here -- the others shell out to the
user's real secret store, which a test has no business unlocking.
"""

from __future__ import annotations

import pytest

from pic.credentials import CredentialError, Reference


@pytest.mark.parametrize(
    ("text", "backend", "locator"),
    [
        ("env:ANTHROPIC_API_KEY", "env", "ANTHROPIC_API_KEY"),
        ("pass:work/github-pat", "pass", "work/github-pat"),
        ("op://Private/registry/password", "op", "Private/registry/password"),
        ("gh", "gh", ""),
        ("keychain:pic-registry", "keychain", "pic-registry"),
        ("keychain:pic-registry/robot", "keychain", "pic-registry/robot"),
    ],
)
def test_parses_a_reference_in_each_supported_store(text, backend, locator):
    """The locator is whatever follows the store's prefix -- nothing, for `gh`."""
    reference = Reference.parse(text)
    assert (reference.backend, reference.locator) == (backend, locator)


@pytest.mark.parametrize(
    "text", ["pass:work/github-pat", "op://Private/registry/password", "gh"]
)
def test_a_reference_renders_back_to_what_the_config_said(text):
    assert str(Reference.parse(text)) == text


@pytest.mark.parametrize(
    "text",
    ["ANTHROPIC_API_KEY", "vault:secret/token", "env", "", "pass:", "op://", "gh:acme"],
)
def test_anything_but_a_supported_store_is_rejected(text):
    with pytest.raises(CredentialError, match="reference"):
        Reference.parse(text)


def test_an_env_reference_resolves_to_the_referenced_value(monkeypatch):
    monkeypatch.setenv("PIC_TEST_TOKEN", "s3cret")
    assert Reference.parse("env:PIC_TEST_TOKEN").resolve() == "s3cret"


def test_an_env_reference_to_an_unset_variable_is_an_error(monkeypatch):
    monkeypatch.delenv("PIC_TEST_TOKEN", raising=False)
    with pytest.raises(CredentialError, match="PIC_TEST_TOKEN"):
        Reference.parse("env:PIC_TEST_TOKEN").resolve()


def test_a_store_that_answers_with_nothing_is_an_error(monkeypatch):
    """An empty credential authenticates nowhere; say so here, not inside the machine."""
    monkeypatch.setenv("PIC_TEST_TOKEN", "")

    with pytest.raises(CredentialError, match="empty"):
        Reference.parse("env:PIC_TEST_TOKEN").resolve()
