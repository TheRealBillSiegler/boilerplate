"""One layer's update step on the made-up template family.

A step updates one layer through ``update_layer``: the answers it takes from
the layers that declare them, the question definitions its views carry, how it
prompts, and what it does with a recorded answer the target release rejects.
These scenarios cross layers, so they live here; the pieces they exercise are
tested beside their source modules.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.boilerplate.templates.conftest import recorded_answers
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    AUTHOR,
    compose_family,
    lines,
    update_family_layer,
)
from tests.integration.boilerplate.composition.scenarios.prompt_session import (
    PromptSession,
    drive_prompts,
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


PROMPT_BEFORE = {"core": "2.0.0", "service": "1.0.0"}
PROMPT_AFTER = {"core": "2.1.0", "service": "1.0.0"}


class TestInteractivePrompting:
    """Each layer's step asks its own questions, as ``copier update`` does."""

    def _update_core(
        self,
        family: Family,
        tmp_path: Path,
        *,
        before: dict[str, str],
        after: dict[str, str],
        answers: dict[str, Any],
        skip_answered: bool = False,
    ) -> PromptSession[None]:
        project = compose_family(family, tmp_path, "service", before, answers)
        return drive_prompts(
            lambda: update_family_layer(
                family,
                project,
                root="service",
                layer="core",
                before=before,
                after=after,
                work=tmp_path,
                data={},
                step_views=True,
                interactive=True,
                skip_answered=skip_answered,
            )
        )

    def test_core_step_asks_its_own_questions_with_the_migrated_answers(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Offer the recorded answer, or the one a migration wrote, as the default.

        Core 2.1.0's migration rewrites a recorded Python 3.11 to 3.12 before
        the step asks, so the prompt for it offers 3.12, and the recorded
        maintainer is offered as it stands.
        """
        session = self._update_core(
            family,
            tmp_path,
            before=PROMPT_BEFORE,
            after=PROMPT_AFTER,
            answers={"python_version": "3.11", "maintainer_name": AUTHOR},
        )

        assert (
            session.finished,
            session.shown,
            session.default_of("maintainer_name"),
            session.default_of("python_version"),
        ) == (
            True,
            [
                "project_name",
                "maintainer_name",
                "python_version",
                "use_tests",
                "api_token",
                "license",
            ],
            AUTHOR,
            "3.12",
        )

    def test_skip_answered_asks_only_what_no_answers_file_records(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Ask `license`, which core 1.1.0 adds, and the never-recorded secret."""
        session = self._update_core(
            family,
            tmp_path,
            before={"core": "1.0.0", "service": "1.0.0"},
            after={"core": "1.1.0", "service": "1.0.0"},
            answers={"author_name": AUTHOR},
            skip_answered=True,
        )

        assert (session.finished, session.shown) == (True, ["api_token", "license"])
