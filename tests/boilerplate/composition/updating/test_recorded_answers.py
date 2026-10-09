"""Reading a composed project's recorded answers from its answers files."""

from pathlib import Path

from boilerplate.composition.updating import (
    read_recorded_answers,
    read_recorded_answers_by_layer,
)
from boilerplate.project_state.answers_file import answers_file_name


def _record(project: Path, layer: str, text: str) -> None:
    (project / answers_file_name(layer)).write_text(text, encoding="utf-8")


class TestReadRecordedAnswers:
    def test_public_answers_are_returned_without_copier_metadata(
        self, tmp_path: Path
    ) -> None:
        _record(tmp_path, "core", "_commit: v1\n_src_path: /x\nname: demo\nport: 80\n")

        assert read_recorded_answers(tmp_path, "core") == {"name": "demo", "port": 80}

    def test_layer_without_an_answers_file_records_nothing(
        self, tmp_path: Path
    ) -> None:
        assert read_recorded_answers(tmp_path, "absent") == {}

    def test_empty_answers_file_records_nothing(self, tmp_path: Path) -> None:
        _record(tmp_path, "core", "")

        assert read_recorded_answers(tmp_path, "core") == {}


class TestReadRecordedAnswersByLayer:
    def test_each_answers_file_is_keyed_by_its_layer_in_file_name_order(
        self, tmp_path: Path
    ) -> None:
        _record(tmp_path, "service", "port: 81\n")
        _record(tmp_path, "core", "port: 80\n")

        by_layer = read_recorded_answers_by_layer(tmp_path)

        assert list(by_layer.items()) == [
            ("core", {"port": 80}),
            ("service", {"port": 81}),
        ]

    def test_a_layer_name_with_dots_is_kept_whole(self, tmp_path: Path) -> None:
        _record(tmp_path, "my.layer", "port: 80\n")

        assert list(read_recorded_answers_by_layer(tmp_path)) == ["my.layer"]

    def test_project_without_answers_files_gives_no_layers(
        self, tmp_path: Path
    ) -> None:
        assert read_recorded_answers_by_layer(tmp_path) == {}
