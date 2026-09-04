"""Tests for CopierConfigMerger."""

from boilerplate.composition.merging import CopierConfigMerger


def test_copier_config_merger_core() -> None:
    merger = CopierConfigMerger()
    result = merger.merge(
        [
            {"_tasks": [{"task": "a"}], "_jinja_extensions": ["e1"], "q1": "a"},
            {
                "_tasks": [{"task": "b"}],
                "_jinja_extensions": ["e2"],
                "q1": "b",
                "q2": 2,
            },
        ]
    )
    assert result["_tasks"] == [{"task": "a"}, {"task": "b"}]
    assert result["_jinja_extensions"] == ["e1", "e2"]
    assert result["q1"] == "b" and result["q2"] == 2


def test_layer_local_keys_excluded_from_merge() -> None:
    """Copier directive keys stay layer-local; only coordination keys merge."""
    result = CopierConfigMerger().merge(
        [
            {"_envops": {"block_start_string": "[%"}, "_tasks": ["t1"], "q": "x"},
            {"_tasks": ["t2"], "_unknown_meta": 1},
        ]
    )
    assert "_envops" not in result
    assert "_unknown_meta" not in result
    assert result["_tasks"] == ["t1", "t2"]
    assert result["q"] == "x"


def test_layer_local_key_set_semantics() -> None:
    keys = CopierConfigMerger.get_layer_local_keys()
    assert "_envops" in keys
    assert CopierConfigMerger.mergeable_keys.isdisjoint(keys)
    assert "_questions_data" not in keys
