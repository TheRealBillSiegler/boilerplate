"""The answer rule of an update: recorded answers over the questionnaire pass's.

The expected values follow the rule's stated order (design 04): ancestors'
recorded answers in topological order, the layer's own on top, under the
questionnaire pass's answers for questions nothing records.
"""

from collections.abc import Collection, Mapping, Sequence
from typing import Any

import pytest

from boilerplate.composition.updating import (
    build_update_data,
    layered_recorded_answers,
)

RECORDED = {
    "core": {"author": "Ada", "port": 80},
    "mid": {"port": 81},
    "service": {"author": "Bo"},
}


class TestLayeredRecordedAnswers:
    """Later layers of the chain win over earlier ones."""

    def test_layers_own_answer_beats_its_ancestors(self) -> None:
        assert layered_recorded_answers(RECORDED, ["core", "service"]) == {
            "author": "Bo",
            "port": 80,
        }

    def test_chain_order_not_mapping_order_decides_the_winner(self) -> None:
        assert (
            layered_recorded_answers(RECORDED, ["service", "core"])["author"] == "Ada"
        )

    def test_layer_outside_the_chain_contributes_nothing(self) -> None:
        assert "port" not in layered_recorded_answers(RECORDED, ["service"])

    def test_layer_with_no_recorded_answers_adds_none(self) -> None:
        assert (
            layered_recorded_answers(RECORDED, ["core", "absent"]) == RECORDED["core"]
        )


class TestBuildUpdateData:
    """The questionnaire pass fills only what the chain has not recorded."""

    def _build(
        self,
        *,
        recorded_by_layer: Mapping[str, Mapping[str, Any]] | None = None,
        chain: Sequence[str] = ("core",),
        asked_hidden: Collection[str] = (),
        view_questions: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_update_data(
            recorded_by_layer=recorded_by_layer or {"core": {"port": 80}},
            chain=chain,
            asked_user={"port": 8080, "license": "MIT"},
            asked_hidden=asked_hidden,
            view_questions=view_questions or {"port": {}, "license": {}},
        )

    def test_unrecorded_question_takes_the_passs_answer(self) -> None:
        assert self._build()["license"] == "MIT"

    def test_recorded_answer_beats_the_passs_answer(self) -> None:
        assert self._build()["port"] == 80

    def test_hidden_question_is_never_taken_from_the_pass(self) -> None:
        assert "license" not in self._build(asked_hidden={"license"})

    def test_question_outside_the_layers_view_is_never_taken_from_the_pass(
        self,
    ) -> None:
        assert "license" not in self._build(view_questions={"port": {}})

    @pytest.mark.parametrize("chain", [["core"], ["core", "service"]])
    def test_answer_recorded_only_by_a_layer_outside_the_chain_is_asked_again(
        self, chain: list[str]
    ) -> None:
        data = self._build(
            recorded_by_layer={"core": {}, "service": {"license": "GPL"}},
            chain=chain,
        )

        assert data["license"] == ("GPL" if "service" in chain else "MIT")
