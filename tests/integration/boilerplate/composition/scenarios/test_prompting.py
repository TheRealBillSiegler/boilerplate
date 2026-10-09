"""Whether the unified questionnaire can be driven interactively in-process.

S17 asks the family's diamond merged view with ``defaults=False`` through the
first layer's Worker, feeding keystrokes through prompt_toolkit's pipe input
with a dummy output, so no console is needed: clear the prefilled project
name and type a new one, then accept every other default. A spy on the
prompt function Copier calls records each question's default and whether it
was shown.
"""

from collections.abc import Iterator
from typing import Any

import pytest

from tests.boilerplate.templates.conftest import ask_merged_questionnaire
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    templates_at,
)
from tests.integration.boilerplate.composition.scenarios.prompt_session import (
    PromptSession,
    drive_prompts,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

# Core 1.1.0 asks `license`, which app 1.1.0 overrides; service overrides core's
# Python version.
PROMPTED = {"core": "1.1.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.1.0"}


@pytest.fixture(scope="module")
def session(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[PromptSession[dict[str, Any]]]:
    """Drive the unified questionnaire from pipe input, typing a new project name."""
    root = tmp_path_factory.mktemp("prompting")
    templates = templates_at(family, root, PROMPTED)
    with temp_dir_inside(root):
        yield drive_prompts(
            lambda: dict(
                ask_merged_questionnaire("app", {}, templates, defaults=False).user
            ),
            {"project_name": "Typed App"},
        )


@pytest.mark.xdist_group("S17")
class TestInteractivePrompting:
    """S17: the unified questionnaire under pipe input."""

    def test_pass_finishes_and_takes_the_typed_answer(
        self, session: PromptSession[dict[str, Any]]
    ) -> None:
        """S17: the pass runs without a console and returns the typed name."""
        answers = session.result or {}

        assert (session.error, answers.get("project_name")) == (None, "Typed App")

    def test_hidden_questions_are_never_shown(
        self, session: PromptSession[dict[str, Any]]
    ) -> None:
        """S17: the `when: false` question reaches the prompt but is not shown."""
        hidden = [p.name for p in session.prompts if not p.shown]

        assert hidden == ["package_name"]

    def test_prompt_defaults_carry_the_descendants_overrides(
        self, session: PromptSession[dict[str, Any]]
    ) -> None:
        """S17: service's and app's overrides are the defaults the prompts show."""
        defaults = {
            p.name: p.default
            for p in session.prompts
            if p.name in ("python_version", "license")
        }

        assert defaults == {"python_version": "3.13", "license": "Apache-2.0"}

    def test_folder_name_default_comes_from_the_scratch_destination(
        self, session: PromptSession[dict[str, Any]]
    ) -> None:
        """S17: project_name defaults to the pass's temp directory, not the project.

        `{{ _folder_name }}` resolves against the Worker's destination, which
        for the unified pass is a throwaway `tmp...` directory.
        """
        default = next(p.default for p in session.prompts if p.name == "project_name")

        assert str(default).startswith("tmp")
