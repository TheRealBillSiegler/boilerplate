# Migrated from engine/graph tests to composition/graph public API

import pytest

from boilerplate.composition.graph import (
    DependencyMap,
    normalize_dependencies,
    toposort_dependencies,
)
from boilerplate.composition.graph.exceptions import DependencyCycleError


class TestDependencyMapShape:
    def test_single_node_no_deps(self):
        graph: DependencyMap = {"A": []}
        assert graph == {"A": []}

    def test_chain_dependencies(self):
        graph: DependencyMap = {"A": ["B"], "B": ["C"], "C": []}
        expected = {"A": ["B"], "B": ["C"], "C": []}
        assert graph == expected

    def test_diamond_dependencies(self):
        graph: DependencyMap = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        expected = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        assert graph == expected

    def test_missing_dependency_included(self):
        graph: DependencyMap = {"A": ["B"], "B": []}
        assert graph == {"A": ["B"], "B": []}


class TestNormalizeDependencies:
    def test_empty_map(self):
        result = normalize_dependencies({})
        assert result == {}

    def test_single_node_no_changes(self):
        deps: DependencyMap = {"A": []}
        result = normalize_dependencies(deps)
        assert result == {"A": []}

    def test_deduplicate_dependencies(self):
        deps: DependencyMap = {"A": ["B", "C", "B", "D", "C"]}
        result = normalize_dependencies(deps)
        assert result == {"A": ["B", "C", "D"], "B": [], "C": [], "D": []}

    def test_add_missing_keys(self):
        deps: DependencyMap = {"A": ["B", "C"], "B": ["D"]}
        result = normalize_dependencies(deps)
        expected = {"A": ["B", "C"], "B": ["D"], "C": [], "D": []}
        assert result == expected

    def test_self_dependency_raises_error(self):
        deps: DependencyMap = {"A": ["A"]}
        with pytest.raises(
            DependencyCycleError,
            match="Self-dependency detected: 'A' depends on itself",
        ):
            normalize_dependencies(deps)

    def test_multiple_self_dependencies_raises_error(self):
        deps: DependencyMap = {"A": ["A"], "B": ["B"]}
        with pytest.raises(DependencyCycleError, match="Self-dependency detected:"):
            normalize_dependencies(deps)

    def test_self_dependency_with_other_deps_raises_error(self):
        deps: DependencyMap = {"A": ["B", "A", "C"]}
        with pytest.raises(
            DependencyCycleError,
            match="Self-dependency detected: 'A' depends on itself",
        ):
            normalize_dependencies(deps)

    def test_complex_normalization(self):
        deps: DependencyMap = {
            "A": ["C", "B", "C", "D"],
            "B": ["E", "D", "E"],
            "D": ["F"],
        }
        result = normalize_dependencies(deps)
        expected = {
            "A": ["C", "B", "D"],
            "B": ["E", "D"],
            "D": ["F"],
            "C": [],
            "E": [],
            "F": [],
        }
        assert result == expected

    def test_declaration_order_preserved(self):
        deps: DependencyMap = {"A": ["Z", "B", "Y", "C"]}
        result = normalize_dependencies(deps)
        assert result["A"] == ["Z", "B", "Y", "C"]

    def test_missing_keys_inserted_in_sorted_order(self):
        result = normalize_dependencies({"A": ["Z", "B", "M"]})
        assert list(result) == ["A", "B", "M", "Z"]

    def test_preserves_existing_empty_lists(self):
        deps: DependencyMap = {"A": ["B"], "B": [], "C": []}
        result = normalize_dependencies(deps)
        expected = {"A": ["B"], "B": [], "C": []}
        assert result == expected


class TestTopoOrder:
    def test_single_node(self):
        graph: DependencyMap = {"A": []}
        result = toposort_dependencies(graph)
        assert result == ["A"]

    def test_chain_order(self):
        graph: DependencyMap = {"A": ["B"], "B": ["C"], "C": []}
        result = toposort_dependencies(graph)
        assert result == ["C", "B", "A"]

    def test_diamond_order(self):
        graph: DependencyMap = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        result = toposort_dependencies(graph)
        # Ordering among siblings B/C is not deterministic beyond constraints:
        a_idx = result.index("A")
        b_idx = result.index("B")
        c_idx = result.index("C")
        d_idx = result.index("D")
        assert d_idx < b_idx < a_idx
        assert d_idx < c_idx < a_idx

    def test_self_cycle_detected(self):
        graph: DependencyMap = {"A": ["A"]}
        with pytest.raises(DependencyCycleError):
            toposort_dependencies(graph)

    def test_two_node_cycle_detected(self):
        graph: DependencyMap = {"A": ["B"], "B": ["A"]}
        with pytest.raises(DependencyCycleError):
            toposort_dependencies(graph)

    def test_multi_node_cycle_detected(self):
        graph: DependencyMap = {"A": ["B"], "B": ["C"], "C": ["A"]}
        with pytest.raises(DependencyCycleError):
            toposort_dependencies(graph)

    def test_complex_cycle_detected(self):
        graph: DependencyMap = {
            "A": ["B", "C"],
            "B": ["D"],
            "C": ["D"],
            "D": ["E"],
            "E": ["B"],
        }
        with pytest.raises(DependencyCycleError):
            toposort_dependencies(graph)


class TestFixedOrder:
    """Pins the design 04 Stage 2 ordering contract.

    Independent roots process in lexicographic order; within a root's
    reachable subgraph, extends declaration order governs sibling precedence;
    a shared dependency is emitted once, at its first occurrence.
    """

    def test_independent_roots_emit_lexicographically(self):
        graph: DependencyMap = {"B": [], "Z": [], "A": []}
        assert toposort_dependencies(graph) == ["A", "B", "Z"]

    def test_siblings_follow_declaration_order(self):
        graph: DependencyMap = {"A": ["Z", "B", "M"]}
        assert toposort_dependencies(graph) == ["Z", "B", "M", "A"]

    def test_diamond_follows_declaration_order(self):
        graph: DependencyMap = {"A": ["C", "B"], "B": ["D"], "C": ["D"], "D": []}
        assert toposort_dependencies(graph) == ["D", "C", "B", "A"]

    def test_design_04_diamond_example(self):
        graph: DependencyMap = {
            "C": ["A", "B"],
            "A": ["Base"],
            "B": ["Base"],
            "Base": [],
        }
        assert toposort_dependencies(graph) == ["Base", "A", "B", "C"]

    def test_multi_root_mixed_contract(self):
        graph: DependencyMap = {
            "app": ["web", "db"],
            "web": ["base"],
            "db": ["base"],
            "cli": ["base"],
            "base": [],
        }
        # Roots app < cli lexicographically; within app, declaration order;
        # base emitted at its first occurrence (under web).
        assert toposort_dependencies(graph) == ["base", "web", "db", "app", "cli"]

    def test_sibling_precedence_survives_rename(self):
        # Same shape twice: lexicographic order agrees with declaration in
        # one graph and opposes it in the other. Declaration governs both;
        # renaming a template never flips precedence.
        agrees: DependencyMap = {"root": ["alpha", "beta"]}
        opposes: DependencyMap = {"root": ["zzz_alpha", "aaa_beta"]}
        assert toposort_dependencies(agrees) == ["alpha", "beta", "root"]
        assert toposort_dependencies(opposes) == ["zzz_alpha", "aaa_beta", "root"]


class TestIntegration:
    def test_chain_build_and_order(self):
        graph: DependencyMap = {"A": ["B"], "B": ["C"], "C": []}
        result = toposort_dependencies(graph)
        assert result == ["C", "B", "A"]

    def test_diamond_build_and_order(self):
        graph: DependencyMap = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        result = toposort_dependencies(graph)
        assert set(result) == {"A", "B", "C", "D"}
        a_idx = result.index("A")
        b_idx = result.index("B")
        c_idx = result.index("C")
        d_idx = result.index("D")
        assert d_idx < b_idx < a_idx
        assert d_idx < c_idx < a_idx

    def test_sequence_with_duplicates_and_missing_keys(self):
        graph: DependencyMap = {
            "A": ["B", "C", "B"],
            "B": ["D", "D"],
        }
        result = toposort_dependencies(graph)
        assert set(result) == {"A", "B", "C", "D"}
        a_idx = result.index("A")
        b_idx = result.index("B")
        c_idx = result.index("C")
        d_idx = result.index("D")
        assert d_idx < b_idx < a_idx
        assert c_idx < a_idx

    def test_sequence_handles_self_cycle_early(self):
        graph: DependencyMap = {"A": ["A"]}
        with pytest.raises(DependencyCycleError, match="Self-dependency detected"):
            toposort_dependencies(graph)
