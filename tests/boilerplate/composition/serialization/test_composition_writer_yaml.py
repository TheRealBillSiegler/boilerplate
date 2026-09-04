from typing import Any, cast

from boilerplate.composition.serialization import dump_yaml


def test_yaml_dump_preserves_insertion_order():
    # Given a mapping with a specific insertion order
    data = {
        "description": "Example template",
        "dependencies": ["base", "addon"],
        "project_name": "demo",
    }

    # Satisfy strict typing invariance by passing as Any
    content = dump_yaml(cast(Any, data))

    # Then the YAML should emit keys in the same order
    idx_desc = content.find("description:")
    idx_deps = content.find("dependencies:")
    idx_proj = content.find("project_name:")

    assert idx_desc != -1 and idx_deps != -1 and idx_proj != -1
    assert idx_desc < idx_deps < idx_proj
