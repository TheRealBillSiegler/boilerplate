"""The prompt harness ends a run at once when the prompt cannot take an answer.

``drive_prompts`` hands each of Copier's prompt calls exactly the keystrokes of
the questions that call shows, then end of input. A typed answer a validator
rejects therefore ends the run with Copier's ``InteractiveSessionError`` for
end of input during prompting, where a pipe that stays open would leave the
prompt waiting for a correction nobody types.
"""

from pathlib import Path

from copier.errors import InteractiveSessionError

from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    compose_family,
    update_family_layer,
)
from tests.integration.boilerplate.composition.scenarios.prompt_session import (
    drive_prompts,
)

BASE = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}
AFTER = {**BASE, "docs": "1.1.0"}


class TestRejectedTypedAnswer:
    """Docs 1.1.0 rejects an empty `docs_site_name`; the harness types one."""

    def test_the_run_ends_with_the_end_of_input_error(
        self, family: Family, tmp_path: Path
    ) -> None:
        """Fail the run at once instead of waiting for a retyped answer."""
        project = compose_family(family, tmp_path, "app", BASE, {"docs_site_name": ""})

        session = drive_prompts(
            lambda: update_family_layer(
                family,
                project,
                root="app",
                layer="docs",
                before=BASE,
                after=AFTER,
                work=tmp_path,
                data={},
                step_views=True,
                interactive=True,
            ),
            {"docs_site_name": ""},
        )

        assert isinstance(session.error, InteractiveSessionError)
