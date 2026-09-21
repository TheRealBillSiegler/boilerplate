"""Tests for scripts/mutation_ratchet.py.

``tests/`` has no ``__init__.py`` files anywhere (pytest collects it with
``--import-mode=importlib``), so this module mirrors that: no package init is added
here either.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from mutation_ratchet import compare, main, parse_results, scores

# A literal sample in the real `mutmut results --all` format: one
# "    <dotted.module.path>.x_<func>__mutmut_<n>: <status>" line per mutant, produced by
# mutmut/__main__.py's `results` command (confirmed against the installed mutmut 3.8.0
# source, mutmut/__main__.py and mutmut/stats.py).
_SAMPLE_RESULTS = """
    boilerplate.common.env.x_get_env_var__mutmut_1: killed
    boilerplate.common.env.x_get_env_var__mutmut_2: survived
    boilerplate.composition.composer.x_compose__mutmut_1: no tests
    boilerplate.composition.composer.x_compose__mutmut_2: skipped
    boilerplate.composition.composer.x_compose__mutmut_3: not checked
    boilerplate.composition.composer.x_compose__mutmut_4: timeout
    boilerplate.composition.composer.x_compose__mutmut_5: suspicious
"""


class TestParseResults:
    def test_counts_killed_mutant_toward_killed_and_total(self) -> None:
        assert parse_results(_SAMPLE_RESULTS)["common"][0] == 1

    def test_counts_survived_mutant_toward_total_but_not_killed(self) -> None:
        killed, total = parse_results(_SAMPLE_RESULTS)["common"]
        assert (killed, total) == (1, 2)

    def test_counts_no_tests_timeout_and_suspicious_toward_total_not_killed(
        self,
    ) -> None:
        killed, total = parse_results(_SAMPLE_RESULTS)["composition"]
        assert (killed, total) == (0, 3)

    def test_excludes_skipped_and_not_checked_from_total(self) -> None:
        # composition's total is 3 (no tests, timeout, suspicious), not 5: the skipped
        # and "not checked" lines are dropped entirely.
        _, total = parse_results(_SAMPLE_RESULTS)["composition"]
        assert total == 3

    def test_ignores_blank_lines(self) -> None:
        assert parse_results(
            "\n\n    boilerplate.common.env.x_f__mutmut_1: killed\n\n"
        ) == {"common": (1, 1)}

    def test_raises_on_line_without_colon_separator(self) -> None:
        with pytest.raises(ValueError, match="does not match"):
            parse_results("    boilerplate.common.env.x_f__mutmut_1 killed")

    def test_raises_on_key_not_rooted_at_boilerplate(self) -> None:
        with pytest.raises(ValueError, match="boilerplate"):
            parse_results("    other_package.env.x_f__mutmut_1: killed")


class TestScores:
    def test_computes_killed_over_total(self) -> None:
        assert scores({"common": (3, 4)}) == {"common": 0.75}

    def test_rounds_to_four_decimal_places(self) -> None:
        assert scores({"common": (1, 3)}) == {"common": 0.3333}

    def test_omits_package_with_zero_total(self) -> None:
        assert scores({"common": (3, 4), "empty": (0, 0)}) == {"common": 0.75}


class TestCompare:
    def test_drop_beyond_tolerance_exits_nonzero(self) -> None:
        code, _ = compare({"common": 0.5}, {"common": 0.6})
        assert code == 1

    def test_drop_beyond_tolerance_names_the_package(self) -> None:
        _, message = compare({"common": 0.5}, {"common": 0.6})
        assert "common" in message

    def test_drop_within_tolerance_exits_zero(self) -> None:
        code, _ = compare({"common": 0.59}, {"common": 0.6}, tolerance=0.02)
        assert code == 0

    def test_drop_by_exactly_the_tolerance_exits_zero(self) -> None:
        # 0.59 - 0.6 is -0.010000000000000009 in plain float subtraction, which is
        # < -0.01 and would wrongly fail this boundary without rounding the delta
        # first to the same 4-place precision the scores themselves carry.
        code, _ = compare({"common": 0.59}, {"common": 0.6}, tolerance=0.01)
        assert code == 0

    def test_rise_exits_zero(self) -> None:
        code, _ = compare({"common": 0.7}, {"common": 0.6})
        assert code == 0

    def test_rise_shows_positive_delta_in_message(self) -> None:
        _, message = compare({"common": 0.7}, {"common": 0.6})
        assert "delta=+0.1000" in message

    def test_package_missing_from_baseline_is_reported_as_new(self) -> None:
        _, message = compare({"common": 0.5, "new_pkg": 0.9}, {"common": 0.5})
        assert "new_pkg: new" in message

    def test_package_missing_from_baseline_does_not_fail_the_check(self) -> None:
        code, _ = compare({"common": 0.5, "new_pkg": 0.9}, {"common": 0.5})
        assert code == 0


class TestCheck:
    def test_write_produces_sorted_json_even_when_exit_code_is_one(
        self, tmp_path: Path
    ) -> None:
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(json.dumps({"common": 0.9}), encoding="utf-8")
        results_path = tmp_path / "results.txt"
        results_path.write_text(_SAMPLE_RESULTS, encoding="utf-8")
        write_path = tmp_path / "scores.json"

        exit_code = main(
            [
                "check",
                str(baseline_path),
                "--results",
                str(results_path),
                "--write",
                str(write_path),
            ]
        )

        assert exit_code == 1
        assert write_path.read_text(encoding="utf-8") == (
            json.dumps({"common": 0.5, "composition": 0.0}, indent=2) + "\n"
        )

    def test_empty_baseline_reports_every_package_as_new_and_exits_zero(
        self, tmp_path: Path
    ) -> None:
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text("{}", encoding="utf-8")
        results_path = tmp_path / "results.txt"
        results_path.write_text(_SAMPLE_RESULTS, encoding="utf-8")
        write_path = tmp_path / "scores.json"

        exit_code = main(
            [
                "check",
                str(baseline_path),
                "--results",
                str(results_path),
                "--write",
                str(write_path),
            ]
        )

        assert exit_code == 0


class TestUpdate:
    def test_lower_current_value_leaves_baseline_untouched(
        self, tmp_path: Path
    ) -> None:
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(
            json.dumps({"common": 0.8, "composition": 0.9}), encoding="utf-8"
        )
        results_path = tmp_path / "results.txt"
        results_path.write_text(_SAMPLE_RESULTS, encoding="utf-8")

        exit_code = main(["update", str(baseline_path), "--results", str(results_path)])

        assert exit_code == 0
        assert json.loads(baseline_path.read_text(encoding="utf-8")) == {
            "common": 0.8,
            "composition": 0.9,
        }

    def test_allow_lower_overwrites_baseline_with_current(self, tmp_path: Path) -> None:
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(
            json.dumps({"common": 0.8, "composition": 0.9, "extra": 0.99}),
            encoding="utf-8",
        )
        results_path = tmp_path / "results.txt"
        results_path.write_text(_SAMPLE_RESULTS, encoding="utf-8")

        main(
            [
                "update",
                str(baseline_path),
                "--results",
                str(results_path),
                "--allow-lower",
            ]
        )

        assert json.loads(baseline_path.read_text(encoding="utf-8")) == {
            "common": 0.5,
            "composition": 0.0,
        }

    def test_missing_baseline_file_is_treated_as_empty(self, tmp_path: Path) -> None:
        baseline_path = tmp_path / "does-not-exist.json"
        results_path = tmp_path / "results.txt"
        results_path.write_text(
            "    boilerplate.common.env.x_get_env_var__mutmut_1: killed\n"
            "    boilerplate.common.env.x_get_env_var__mutmut_2: survived\n",
            encoding="utf-8",
        )

        exit_code = main(["update", str(baseline_path), "--results", str(results_path)])

        assert exit_code == 0
        assert json.loads(baseline_path.read_text(encoding="utf-8")) == {"common": 0.5}
