from typing import Any, cast

from boilerplate.composition.serialization import dump_json


def test_json_dump_preserves_insertion_order():
    data = {
        "description": "Example template",
        "dependencies": ["base", "addon"],
        "project_name": "demo",
    }

    content = dump_json(cast(Any, data))

    # JSON should preserve insertion order as emitted by the writer
    idx_desc = content.find('"description"')
    idx_deps = content.find('"dependencies"')
    idx_proj = content.find('"project_name"')

    assert idx_desc != -1 and idx_deps != -1 and idx_proj != -1
    assert idx_desc < idx_deps < idx_proj
