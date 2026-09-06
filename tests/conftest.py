from __future__ import annotations

import pytest

from pic import machine as machine_mod

TEST_WORKSPACE = "test"


@pytest.fixture(scope="session")
def machine():
    """A real machine booted from the pic machine image: seam 1 for acceptance tests.

    Session-scoped because booting one costs a build plus a boot, and every
    acceptance test only reads state the machine established at boot.
    """
    try:
        yield machine_mod.launch(TEST_WORKSPACE)
    finally:
        machine_mod.teardown(TEST_WORKSPACE)
