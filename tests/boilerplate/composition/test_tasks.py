"""Tests for the shared ``_tasks`` semantics helpers."""

import logging

import pytest

from boilerplate.composition.models.json_types import JSON
from boilerplate.composition.tasks import coerce_task, normalize_tasks


class TestNormalizeTasks:
    @pytest.mark.parametrize(
        ("final_schema", "expected"),
        [
            pytest.param({}, [], id="missing-key"),
            pytest.param({"_tasks": "echo hi"}, [], id="non-list-value"),
            pytest.param(
                {"_tasks": ["echo hi && git init"]},
                ["echo hi && git init"],
                id="string-command-keeps-shell-semantics",
            ),
            pytest.param(
                {"_tasks": [["git", "init"]]}, [["git", "init"]], id="list-command"
            ),
            pytest.param(
                {"_tasks": [["echo", 1]]},
                [["echo", "1"]],
                id="stringifies-list-elements",
            ),
            pytest.param(
                {"_tasks": [{"command": "rm -rf build", "when": "{{ cleanup }}"}]},
                [{"command": "rm -rf build", "when": "{{ cleanup }}"}],
                id="mapping-keeps-when-condition",
            ),
            pytest.param(
                {
                    "_tasks": [
                        {
                            "command": ["invoke", "setup"],
                            "working_directory": "sub",
                        }
                    ]
                },
                [{"command": ["invoke", "setup"], "working_directory": "sub"}],
                id="mapping-keeps-working-directory",
            ),
        ],
    )
    def test_shapes_pass_through(
        self, final_schema: dict[str, JSON], expected: list[JSON]
    ) -> None:
        assert normalize_tasks(final_schema) == expected

    def test_invalid_entries_dropped_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Regression: malformed entries used to vanish silently; a mapping
        # without "command" and a bare None are dropped audibly.
        schema: dict[str, JSON] = {"_tasks": [{"cmd": "x"}, None, "echo ok"]}
        with caplog.at_level(logging.WARNING, logger="boilerplate.composition.tasks"):
            assert normalize_tasks(schema) == ["echo ok"]
        assert (
            sum("Dropping malformed _tasks entry" in r.message for r in caplog.records)
            == 2
        )


class TestCoerceTask:
    def test_cmd_becomes_command_list(self) -> None:
        class Task:
            cmd = ("git", "init")

        assert coerce_task(Task()) == ["git", "init"]

    def test_string_cmd_stays_a_string(self) -> None:
        """Regression: a shell-string command is not split into characters."""

        class Task:
            cmd = "git init"

        assert coerce_task(Task()) == "git init"

    def test_condition_survives_as_when(self) -> None:
        # Regression: a guarded task used to lose its condition and run
        # unconditionally after the round trip.
        class Task:
            cmd = "rm -rf build"
            condition = "{{ cleanup }}"

        assert coerce_task(Task()) == {
            "command": "rm -rf build",
            "when": "{{ cleanup }}",
        }

    def test_false_condition_survives(self) -> None:
        class Task:
            cmd = "echo never"
            condition = False

        assert coerce_task(Task()) == {"command": "echo never", "when": False}

    def test_working_directory_survives(self) -> None:
        class Task:
            cmd = ("invoke", "setup")
            working_directory = "sub/dir"

        assert coerce_task(Task()) == {
            "command": ["invoke", "setup"],
            "working_directory": "sub/dir",
        }

    def test_default_condition_and_cwd_yield_bare_command(self) -> None:
        class Task:
            cmd = ("git", "init")
            condition = "true"
            working_directory = "."

        assert coerce_task(Task()) == ["git", "init"]

    def test_unreadable_cmd_falls_back_to_str(self) -> None:
        class Task:
            cmd = 7  # not iterable

            def __str__(self) -> str:
                return "task-7"

        assert coerce_task(Task()) == "task-7"

    def test_missing_cmd_falls_back_to_str(self) -> None:
        class NotATask:
            def __str__(self) -> str:
                return "not-a-task"

        assert coerce_task(NotATask()) == "not-a-task"
