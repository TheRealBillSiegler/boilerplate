"""Tests for the merge strategy functions."""

import pytest

from boilerplate.composition.merging import (
    accumulate,
    intersect_versions,
    merge_questions,
    override,
    union,
)
from boilerplate.composition.merging.exceptions import MergeConflictError


class TestMergeStrategiesIntegration:
    def test_template_composition_workflow(self) -> None:
        project_names: list[object] = ["base-project", "extended-project"]
        assert override(project_names, "project_name") == "extended-project"

        base_tasks: list[object] = [{"cmd": "pip install -r requirements.txt"}]
        ext_tasks: list[object] = [{"cmd": "npm install"}, {"cmd": "pytest"}]
        assert accumulate([base_tasks, ext_tasks], "_tasks") == [
            {"cmd": "pip install -r requirements.txt"},
            {"cmd": "npm install"},
            {"cmd": "pytest"},
        ]

        copier_versions: list[object] = ["9.0.0", "9.5.0", "9.2.1"]
        assert intersect_versions(copier_versions, "_min_copier_version") == "9.5.0"

        extensions: list[object] = [
            ["jinja2-time"],
            ["jinja2-time", "copier-templates"],
            "custom-ext",
        ]
        assert union(extensions, "_jinja_extensions") == [
            "jinja2-time",
            "copier-templates",
            "custom-ext",
        ]

    def test_merge_questions_composition_scenarios(self) -> None:
        env_configs: list[object] = [
            {"DEBUG": False, "PORT": 8000},
            {"DEBUG": True, "API_KEY": "dev"},
        ]
        assert merge_questions(env_configs, "environment") == {
            "DEBUG": True,
            "PORT": 8000,
            "API_KEY": "dev",
        }

        dependencies: list[object] = [["fastapi", "uvicorn"], ["pytest", "black"]]
        assert merge_questions(dependencies, "dependencies") == [
            "fastapi",
            "uvicorn",
            "pytest",
            "black",
        ]

        assert (
            merge_questions(["Base Author", "Extension Author"], "author")
            == "Extension Author"
        )

    def test_merge_conflict_scenarios(self) -> None:
        with pytest.raises(MergeConflictError, match="Incompatible types"):
            merge_questions([{"config": True}, "string_config"], "mixed_config")

    def test_edge_cases_and_empty_inputs(self) -> None:
        assert accumulate([], "empty") == []
        assert union([], "empty") == []
        assert override(["single"], "key") == "single"
        assert accumulate([["single"]], "key") == ["single"]

        mixed_values: list[object] = [["list_item"], "string_item", ["another_list"]]
        assert accumulate(mixed_values, "mixed") == [
            "list_item",
            "string_item",
            "another_list",
        ]
