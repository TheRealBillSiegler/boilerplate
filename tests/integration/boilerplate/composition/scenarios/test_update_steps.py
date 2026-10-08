"""One layer's update step on the made-up template family.

A step updates one layer through ``update_layer``: the answers it takes from
the layers that declare them, the question definitions its views carry, how it
prompts, and what it does with a recorded answer the target release rejects.
These scenarios cross layers, so they live here; the pieces they exercise are
tested beside their source modules.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.boilerplate.templates.conftest import recorded_answers
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    AUTHOR,
    compose_family,
    lines,
    update_family_layer,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

BASE = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}
LICENSE_AFTER = {**BASE, "core": "1.1.0", "app": "1.1.0"}


@pytest.fixture(scope="module")
def license_step(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Path]:
    """Compose the diamond, then run only core's step to 1.1.0, non-interactively."""
    work = tmp_path_factory.mktemp("license-step")
    with temp_dir_inside(work):
        project = compose_family(family, work, "app", BASE, {"author_name": AUTHOR})
        update_family_layer(
            family,
            project,
            root="app",
            layer="core",
            before=BASE,
            after=LICENSE_AFTER,
            work=work,
            data={},
            step_views=True,
        )
        yield project


class TestDescendantOverrideOfANewAncestorQuestion:
    """Core 1.1.0 adds `license` (MIT); app 1.1.0 overrides its default."""

    def test_core_step_records_the_overridden_default(self, license_step: Path) -> None:
        """The ancestor's step takes the default from the full merged schema."""
        assert recorded_answers(license_step, "core")["license"] == "Apache-2.0"

    def test_core_step_renders_the_overridden_default(self, license_step: Path) -> None:
        """The licence file core writes names the overriding default."""
        assert lines(license_step / "LICENSE")[0] == "Apache License, Version 2.0"
