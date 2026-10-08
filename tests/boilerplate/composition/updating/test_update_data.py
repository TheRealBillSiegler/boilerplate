"""The answer rule of an update step: where each question's data comes from.

The expected values follow design 04 §Safe Update. A question declared by an
ancestor arrives as data from the answers file of the layer that declares it. The
layer's own recorded answers are never data: Copier reads them from the layer's
own file after its migrations. Supplied values and the secrets asked earlier in
the update are data for the questions in the layer's scope.
"""

from collections.abc import Mapping
from typing import Any

from boilerplate.composition.updating import build_step_data

DECLARED_BY = {"author": "core", "port": "service", "python": "core"}
RECORDED = {
    "core": {"author": "Ada", "python": "3.12"},
    "service": {"author": "Stale", "port": 8000, "python": "3.11"},
}


def _build(
    *,
    layer: str = "service",
    declared_by: Mapping[str, str] = DECLARED_BY,
    recorded_by_layer: Mapping[str, Mapping[str, Any]] = RECORDED,
    supplied: Mapping[str, Any] | None = None,
    secrets: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_step_data(
        layer=layer,
        declared_by=declared_by,
        recorded_by_layer=recorded_by_layer,
        supplied=supplied or {},
        secrets=secrets or {},
    )


class TestAncestorsAnswers:
    """An ancestor's question is data from the file of the layer that declares it."""

    def test_the_declaring_ancestors_answer_beats_the_layers_stale_copy(
        self,
    ) -> None:
        assert _build()["author"] == "Ada"

    def test_every_question_an_ancestor_declares_is_data(self) -> None:
        assert _build() == {"author": "Ada", "python": "3.12"}

    def test_the_layers_own_questions_are_never_data(self) -> None:
        assert "port" not in _build()

    def test_a_question_the_declaring_ancestor_has_not_recorded_is_not_data(
        self,
    ) -> None:
        data = _build(recorded_by_layer={"core": {"author": "Ada"}, "service": {}})

        assert "python" not in data

    def test_a_layer_with_no_answers_file_adds_nothing(self) -> None:
        assert _build(recorded_by_layer={"service": RECORDED["service"]}) == {}


class TestSuppliedValues:
    """Values the user supplies are data for questions in the layer's scope."""

    def test_a_supplied_value_beats_the_ancestors_recorded_answer(self) -> None:
        assert _build(supplied={"author": "Bo"})["author"] == "Bo"

    def test_a_supplied_value_is_data_for_the_layers_own_question(self) -> None:
        assert _build(supplied={"port": 9000})["port"] == 9000

    def test_a_supplied_value_outside_the_layers_scope_is_dropped(self) -> None:
        assert "license" not in _build(supplied={"license": "MIT"})


class TestSecrets:
    """Secrets asked earlier in the update are data for later steps."""

    def test_a_secret_asked_earlier_is_data(self) -> None:
        declared_by = {**DECLARED_BY, "token": "core"}

        assert _build(declared_by=declared_by, secrets={"token": "s3"})["token"] == "s3"

    def test_a_secret_outside_the_layers_scope_is_dropped(self) -> None:
        assert "token" not in _build(secrets={"token": "s3"})
