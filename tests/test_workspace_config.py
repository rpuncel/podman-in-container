"""Seam 2, half two: the workspace config loader and its layering merge.

Asserts the merged result for given inputs -- the merged egress allow-list, the
merged secret manifest, the resolved values -- without booting a machine. The merge
rules are the point: tightening egress is easy, widening has to be stated
explicitly, and a workspace can swap one credential without redefining the rest.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pic import workspace_config
from pic.workspace_config import ConfigError


@pytest.fixture
def config_home(tmp_path: Path) -> Path:
    return tmp_path / "pic"


def write(config_home: Path, kind: str, name: str, body: str) -> None:
    directory = config_home / kind
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.yaml").write_text(textwrap.dedent(body))


def workspace(config_home: Path, name: str, body: str) -> None:
    write(config_home, "workspaces", name, body)


def base(config_home: Path, name: str, body: str) -> None:
    write(config_home, "bases", name, body)


def test_loads_a_workspace_that_extends_nothing(config_home):
    workspace(
        config_home,
        "solo",
        """
        egress:
          allow:
            - api.anthropic.com
        secrets:
          anthropic_api_key: env:ANTHROPIC_API_KEY
        """,
    )

    config = workspace_config.load("solo", config_home=config_home)

    assert config.name == "solo"
    assert config.egress_allow == ("api.anthropic.com",)
    assert str(config.secrets["anthropic_api_key"]) == "env:ANTHROPIC_API_KEY"


def test_a_workspace_inherits_the_base_it_extends(config_home):
    base(
        config_home,
        "work",
        """
        egress:
          allow:
            - api.anthropic.com
            - "*.pythonhosted.org"
        secrets:
          anthropic_api_key: env:ANTHROPIC_API_KEY
        """,
    )
    workspace(config_home, "acme", "extends: work\n")

    config = workspace_config.load("acme", config_home=config_home)

    assert config.egress_allow == ("api.anthropic.com", "*.pythonhosted.org")
    assert str(config.secrets["anthropic_api_key"]) == "env:ANTHROPIC_API_KEY"


def test_workspace_adds_widen_the_base_allow_list(config_home):
    base(config_home, "work", "egress:\n  allow: [api.anthropic.com]\n")
    workspace(
        config_home,
        "acme",
        """
        extends: work
        egress:
          allow:
            - registry.acme.example
        """,
    )

    config = workspace_config.load("acme", config_home=config_home)

    assert config.egress_allow == ("api.anthropic.com", "registry.acme.example")


def test_workspace_excludes_tighten_the_base_allow_list(config_home):
    base(config_home, "work", "egress:\n  allow: [api.anthropic.com, ghcr.io]\n")
    workspace(
        config_home,
        "acme",
        """
        extends: work
        egress:
          exclude:
            - ghcr.io
        """,
    )

    assert workspace_config.load("acme", config_home=config_home).egress_allow == (
        "api.anthropic.com",
    )


def test_an_exclude_beats_an_add_of_the_same_endpoint(config_home):
    base(config_home, "work", "egress:\n  allow: [api.anthropic.com]\n")
    workspace(
        config_home,
        "acme",
        """
        extends: work
        egress:
          allow: [ghcr.io]
          exclude: [ghcr.io]
        """,
    )

    assert workspace_config.load("acme", config_home=config_home).egress_allow == (
        "api.anthropic.com",
    )


def test_an_endpoint_in_both_base_and_workspace_is_allowed_once(config_home):
    base(config_home, "work", "egress:\n  allow: [api.anthropic.com]\n")
    workspace(
        config_home,
        "acme",
        "extends: work\negress:\n  allow: [api.anthropic.com, ghcr.io]\n",
    )

    assert workspace_config.load("acme", config_home=config_home).egress_allow == (
        "api.anthropic.com",
        "ghcr.io",
    )


def test_a_workspace_swaps_one_base_credential_and_keeps_the_rest(config_home):
    base(
        config_home,
        "work",
        """
        secrets:
          anthropic_api_key: env:ANTHROPIC_API_KEY
          git_token: gh
        """,
    )
    workspace(
        config_home,
        "acme",
        """
        extends: work
        secrets:
          git_token: pass:acme/github-pat
        """,
    )

    secrets = workspace_config.load("acme", config_home=config_home).secrets

    assert {key: str(value) for key, value in secrets.items()} == {
        "anthropic_api_key": "env:ANTHROPIC_API_KEY",
        "git_token": "pass:acme/github-pat",
    }


def test_resolving_the_manifest_yields_the_referenced_values(config_home, monkeypatch):
    monkeypatch.setenv("PIC_TEST_ANTHROPIC_KEY", "sk-test")
    monkeypatch.setenv("PIC_TEST_GIT_TOKEN", "ghp-test")
    workspace(
        config_home,
        "acme",
        """
        secrets:
          anthropic_api_key: env:PIC_TEST_ANTHROPIC_KEY
          git_token: env:PIC_TEST_GIT_TOKEN
        """,
    )

    resolved = workspace_config.load("acme", config_home=config_home).resolve_secrets()

    assert resolved == {"anthropic_api_key": "sk-test", "git_token": "ghp-test"}


def test_a_workspace_declaring_neither_section_resolves_to_nothing(config_home):
    workspace(config_home, "bare", "{}\n")

    config = workspace_config.load("bare", config_home=config_home)

    assert config.egress_allow == ()
    assert config.resolve_secrets() == {}


def test_a_missing_workspace_names_the_file_it_looked_for(config_home):
    with pytest.raises(ConfigError, match="workspaces/absent.yaml"):
        workspace_config.load("absent", config_home=config_home)


def test_a_missing_base_names_the_file_it_looked_for(config_home):
    workspace(config_home, "acme", "extends: absent\n")

    with pytest.raises(ConfigError, match="bases/absent.yaml"):
        workspace_config.load("acme", config_home=config_home)


def test_a_base_may_not_itself_extend(config_home):
    base(config_home, "work", "extends: deeper\n")
    base(config_home, "deeper", "{}\n")
    workspace(config_home, "acme", "extends: work\n")

    with pytest.raises(ConfigError, match="extend"):
        workspace_config.load("acme", config_home=config_home)


@pytest.mark.parametrize(
    "body",
    [
        "egres:\n  allow: [ghcr.io]\n",
        "egress:\n  allowed: [ghcr.io]\n",
        "secret:\n  git_token: gh\n",
    ],
)
def test_a_mistyped_key_is_rejected_rather_than_silently_ignored(config_home, body):
    """A typo that quietly dropped an exclude would silently widen egress."""
    workspace(config_home, "acme", body)

    with pytest.raises(ConfigError, match="unknown"):
        workspace_config.load("acme", config_home=config_home)


def test_an_unparseable_credential_reference_fails_at_load(config_home):
    workspace(config_home, "acme", "secrets:\n  git_token: vault:secret/token\n")

    with pytest.raises(ConfigError, match="git_token"):
        workspace_config.load("acme", config_home=config_home)


def test_configs_live_under_the_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert workspace_config.default_config_home() == tmp_path / "pic"


def test_configs_default_to_dot_config_in_the_home_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert workspace_config.default_config_home() == tmp_path / ".config" / "pic"


def test_a_section_left_empty_is_the_same_as_not_writing_it(config_home):
    workspace(config_home, "acme", "egress:\nsecrets:\n")

    config = workspace_config.load("acme", config_home=config_home)

    assert config.egress_allow == ()
    assert config.secrets == {}


@pytest.mark.parametrize("body", ["egress: [ghcr.io]\n", "secrets: [git_token]\n", "- a\n"])
def test_a_section_of_the_wrong_shape_is_rejected(config_home, body):
    workspace(config_home, "acme", body)

    with pytest.raises(ConfigError, match="mapping"):
        workspace_config.load("acme", config_home=config_home)


def test_a_base_is_validated_the_same_way_a_workspace_is(config_home):
    base(config_home, "work", "egress:\n  allowed: [ghcr.io]\n")
    workspace(config_home, "acme", "extends: work\n")

    with pytest.raises(ConfigError, match="bases/work.yaml"):
        workspace_config.load("acme", config_home=config_home)


def test_an_egress_list_written_as_a_bare_string_is_rejected(config_home):
    """`allow: ghcr.io` would otherwise allow-list one hostname's letters."""
    workspace(config_home, "acme", "egress:\n  allow: ghcr.io\n")

    with pytest.raises(ConfigError, match="list of endpoints"):
        workspace_config.load("acme", config_home=config_home)
