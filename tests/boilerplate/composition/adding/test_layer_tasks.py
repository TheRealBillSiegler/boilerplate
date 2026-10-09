"""The tasks a layer declares for itself, read from its template checkout."""

from pathlib import Path

import pytest

from boilerplate.composition.adding.layer_tasks import own_tasks

TASKS = "_tasks:\n  - echo hi\n  - [git, init]\n  - {command: make, when: '{{ x }}'}\n"
EXPECTED = ["echo hi", ["git", "init"], {"command": "make", "when": "{{ x }}"}]


class TestOwnTasks:
    @pytest.mark.parametrize("config_name", ["copier.yml", "copier.yaml"])
    def test_reads_the_tasks_from_either_config_file_name(
        self, tmp_path: Path, config_name: str
    ) -> None:
        """Read the file Copier reads, under either of its two extensions."""
        (tmp_path / config_name).write_text(TASKS, encoding="utf-8")

        assert own_tasks(tmp_path) == EXPECTED

    def test_a_template_without_a_config_file_has_no_tasks(
        self, tmp_path: Path
    ) -> None:
        assert own_tasks(tmp_path) == []

    def test_a_config_that_declares_no_tasks_has_none(self, tmp_path: Path) -> None:
        (tmp_path / "copier.yml").write_text("project_name: str\n", encoding="utf-8")

        assert own_tasks(tmp_path) == []
