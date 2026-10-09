"""The name of a layer's answers file, in answers_file.py."""

from fnmatch import fnmatchcase

import pytest

from boilerplate.project_state.answers_file import (
    ANSWERS_FILE_GLOB,
    answers_file_name,
    layer_of_answers_file,
)


class TestAnswersFileName:
    def test_names_the_file_copier_writes_for_a_layer(self) -> None:
        """Design 04 §Per-Layer Render Loop gives ``.copier-answers.<layer>.yml``."""
        assert answers_file_name("core") == ".copier-answers.core.yml"

    def test_the_glob_matches_the_name_of_every_layer(self) -> None:
        assert fnmatchcase(answers_file_name("core"), ANSWERS_FILE_GLOB)


class TestLayerOfAnswersFile:
    def test_recovers_the_layer_from_the_file_name(self) -> None:
        assert layer_of_answers_file(".copier-answers.core.yml") == "core"

    @pytest.mark.parametrize("layer", ["core", "my.layer", "a.b.c"])
    def test_keeps_a_layer_name_that_contains_dots(self, layer: str) -> None:
        assert layer_of_answers_file(answers_file_name(layer)) == layer
