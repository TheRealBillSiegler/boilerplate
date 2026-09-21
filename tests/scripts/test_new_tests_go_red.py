import importlib.util
import textwrap
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "new_tests_go_red.py"
)
_SPEC = importlib.util.spec_from_file_location("new_tests_go_red", _MODULE_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
new_tests_go_red = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(new_tests_go_red)


class TestTestFunctions:
    def test_module_level_function_is_its_own_name(self):
        source = "def test_alpha():\n    pass\n"
        assert new_tests_go_red.test_functions(source) == {"test_alpha"}

    def test_class_method_is_qualified_by_class_name(self):
        source = textwrap.dedent(
            """
            class TestThing:
                def test_beta(self):
                    pass
            """
        )
        assert new_tests_go_red.test_functions(source) == {"TestThing::test_beta"}

    def test_non_test_prefixed_names_are_ignored(self):
        source = textwrap.dedent(
            """
            def helper():
                pass

            class Thing:
                def test_gamma(self):
                    pass
            """
        )
        assert new_tests_go_red.test_functions(source) == set()

    def test_nested_function_is_ignored(self):
        source = textwrap.dedent(
            """
            def test_outer():
                def test_inner():
                    pass
            """
        )
        assert new_tests_go_red.test_functions(source) == {"test_outer"}

    def test_async_def_is_included(self):
        source = "async def test_delta():\n    pass\n"
        assert new_tests_go_red.test_functions(source) == {"test_delta"}


class TestAddedTests:
    def test_new_file_counts_every_test(self):
        head = "def test_a():\n    pass\n\ndef test_b():\n    pass\n"
        assert new_tests_go_red.added_tests(None, head) == {"test_a", "test_b"}

    def test_only_the_new_names_count_as_added(self):
        base = "def test_a():\n    pass\n"
        head = "def test_a():\n    pass\n\ndef test_b():\n    pass\n"
        assert new_tests_go_red.added_tests(base, head) == {"test_b"}

    def test_no_new_names_is_empty(self):
        base = "def test_a():\n    pass\n"
        head = "def test_a():\n    pass\n"
        assert new_tests_go_red.added_tests(base, head) == set()


class TestVerdict:
    def test_src_unchanged_reports_nothing_to_discriminate(self):
        code, message = new_tests_go_red.verdict(
            {"t.py::test_a": "failed"}, src_changed=False
        )
        assert (code, "nothing to discriminate" in message.lower()) == (0, True)

    def test_empty_results_reports_nothing_to_discriminate(self):
        code, message = new_tests_go_red.verdict({}, src_changed=True)
        assert (code, "nothing to discriminate" in message.lower()) == (0, True)

    def test_all_passed_exits_1_and_lists_every_added_test(self):
        results = {"t.py::test_a": "passed", "t.py::test_b": "passed"}
        code, message = new_tests_go_red.verdict(results, src_changed=True)
        assert (code, "t.py::test_a" in message, "t.py::test_b" in message) == (
            1,
            True,
            True,
        )

    def test_one_failed_names_the_passed_one_as_a_warning(self):
        results = {"t.py::test_a": "passed", "t.py::test_b": "failed"}
        code, message = new_tests_go_red.verdict(results, src_changed=True)
        assert (code, "WARNING" in message, "t.py::test_a" in message) == (
            0,
            True,
            True,
        )

    def test_only_skipped_is_neither_red_nor_a_pass_and_exits_0(self):
        results = {"t.py::test_a": "skipped"}
        code, message = new_tests_go_red.verdict(results, src_changed=True)
        assert (code, "skipped" in message.lower(), "WARNING" in message) == (
            0,
            True,
            False,
        )

    def test_skipped_alongside_a_passed_test_still_exits_1(self):
        results = {"t.py::test_a": "passed", "t.py::test_b": "skipped"}
        code, message = new_tests_go_red.verdict(results, src_changed=True)
        assert (code, "t.py::test_a" in message) == (1, True)

    def test_skipped_alongside_a_failed_test_exits_0_without_a_warning(self):
        results = {"t.py::test_a": "skipped", "t.py::test_b": "failed"}
        code, message = new_tests_go_red.verdict(results, src_changed=True)
        assert (code, "WARNING" in message) == (0, False)


class TestJunitOutcomes:
    _XML = textwrap.dedent(
        """
        <?xml version="1.0" encoding="utf-8"?>
        <testsuites>
          <testsuite name="pytest">
            <testcase classname="tests.scripts.test_probe" name="test_thing[1]" />
            <testcase classname="tests.scripts.test_probe" name="test_thing[2]">
              <failure message="boom">boom</failure>
            </testcase>
            <testcase classname="tests.scripts.test_probe" name="test_thing[3]">
              <error message="boom">boom</error>
            </testcase>
          </testsuite>
        </testsuites>
        """
    ).strip()

    _SKIPPED_XML = textwrap.dedent(
        """
        <?xml version="1.0" encoding="utf-8"?>
        <testsuites>
          <testsuite name="pytest">
            <testcase classname="tests.scripts.test_probe" name="test_skipped">
              <skipped message="no such module" />
            </testcase>
          </testsuite>
        </testsuites>
        """
    ).strip()

    def test_parametrized_instances_fold_to_the_worst_outcome(self):
        outcomes = new_tests_go_red.parse_junit_outcomes(self._XML)
        assert outcomes == {"tests.scripts.test_probe::test_thing": "error"}

    def test_skipped_testcase_reports_skipped_not_passed(self):
        outcomes = new_tests_go_red.parse_junit_outcomes(self._SKIPPED_XML)
        assert outcomes == {"tests.scripts.test_probe::test_skipped": "skipped"}

    def test_resolve_outcomes_maps_a_module_level_node_id(self):
        junit_outcomes = {"tests.scripts.test_probe::test_thing": "error"}
        resolved = new_tests_go_red.resolve_outcomes(
            {"tests/scripts/test_probe.py::test_thing"}, junit_outcomes
        )
        assert resolved == {"tests/scripts/test_probe.py::test_thing": "error"}

    def test_resolve_outcomes_maps_a_class_method_node_id(self):
        junit_outcomes = {"tests.scripts.test_probe.TestThing::test_method": "passed"}
        resolved = new_tests_go_red.resolve_outcomes(
            {"tests/scripts/test_probe.py::TestThing::test_method"}, junit_outcomes
        )
        assert resolved == {
            "tests/scripts/test_probe.py::TestThing::test_method": "passed"
        }

    def test_resolve_outcomes_defaults_a_missing_node_id_to_error(self):
        resolved = new_tests_go_red.resolve_outcomes(
            {"tests/scripts/test_probe.py::test_missing"}, {}
        )
        assert resolved == {"tests/scripts/test_probe.py::test_missing": "error"}
