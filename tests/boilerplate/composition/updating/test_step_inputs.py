"""Tests for the values an update step takes, in step_inputs.py."""

import pytest
from pydantic import ValidationError

from boilerplate.composition.updating import StepInputs


class TestTheWalkStartAnswers:
    """Design 04: the old copy fills from the records read when the walk began."""

    def test_a_step_without_them_is_refused(self) -> None:
        """Read at step start instead, an ancestor's change enters the merge base."""
        with pytest.raises(ValidationError):
            StepInputs(supplied={})

    def test_a_step_given_them_keeps_them(self) -> None:
        walk_answers = {"core": {"project_name": "Demo"}}

        assert StepInputs(walk_answers=walk_answers).walk_answers == walk_answers
