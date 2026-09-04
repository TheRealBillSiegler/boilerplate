"""Unit tests for the hardened YAML loader."""

import io

import pytest
import yaml

from boilerplate.common.yaml_loading import MAX_ALIAS_NODES, load_yaml


class TestHappyPath:
    """Plain safe_load semantics are preserved for well-formed documents."""

    def test_loads_plain_mapping(self) -> None:
        assert load_yaml("name: project\nversion: 1.0.0") == {
            "name": "project",
            "version": "1.0.0",
        }

    def test_loads_from_text_stream(self) -> None:
        assert load_yaml(io.StringIO("extends: [base]")) == {"extends": ["base"]}

    def test_empty_document_returns_none(self) -> None:
        assert load_yaml("") is None

    def test_nested_structures(self) -> None:
        data = load_yaml("a:\n  b: [1, 2]\n  c:\n    d: true")
        assert data == {"a": {"b": [1, 2], "c": {"d": True}}}

    def test_benign_alias_resolves(self) -> None:
        assert load_yaml("x: &a 1\ny: *a") == {"x": 1, "y": 1}

    def test_unsafe_python_tags_still_rejected(self) -> None:
        with pytest.raises(yaml.YAMLError):
            load_yaml("!!python/object/apply:os.system ['echo pwned']")


class TestDuplicateKeys:
    """Duplicate keys at the same mapping level are an error (design 03)."""

    def test_top_level_duplicate_rejected(self) -> None:
        with pytest.raises(yaml.YAMLError, match="duplicate key 'name'"):
            load_yaml("name: a\nname: b")

    def test_nested_duplicate_rejected(self) -> None:
        with pytest.raises(yaml.YAMLError, match="duplicate key"):
            load_yaml("outer:\n  k: 1\n  k: 2")

    def test_same_key_at_different_levels_allowed(self) -> None:
        assert load_yaml("k: 1\nouter:\n  k: 2") == {"k": 1, "outer": {"k": 2}}

    def test_equal_non_string_keys_rejected(self) -> None:
        with pytest.raises(yaml.YAMLError, match="duplicate key"):
            load_yaml("1: a\n1: b")


class TestAliasExpansionCap:
    """Total alias expansion is capped at MAX_ALIAS_NODES (billion-laughs guard)."""

    def test_billion_laughs_rejected(self) -> None:
        levels = 9
        doc = "a0: &a0 [x, x, x, x, x, x, x, x, x, x]\n"
        for i in range(1, levels):
            refs = ", ".join(f"*a{i - 1}" for _ in range(10))
            doc += f"a{i}: &a{i} [{refs}]\n"
        with pytest.raises(yaml.YAMLError, match="alias expansion exceeds"):
            load_yaml(doc)

    def test_flat_alias_flood_rejected(self) -> None:
        doc = "x: &a 1\n" + "".join(f"k{i}: *a\n" for i in range(MAX_ALIAS_NODES + 1))
        with pytest.raises(yaml.YAMLError, match="alias expansion exceeds"):
            load_yaml(doc)

    def test_exactly_at_cap_allowed(self) -> None:
        doc = "x: &a 1\n" + "".join(f"k{i}: *a\n" for i in range(MAX_ALIAS_NODES))
        data = load_yaml(doc)
        assert data[f"k{MAX_ALIAS_NODES - 1}"] == 1

    def test_recursive_alias_rejected(self) -> None:
        # A self-referential anchor cannot expand to anything finite; the
        # budget walk exhausts and fails instead of looping.
        with pytest.raises(yaml.YAMLError, match="alias expansion exceeds"):
            load_yaml("a: &a\n  b: *a\nc: *a")
