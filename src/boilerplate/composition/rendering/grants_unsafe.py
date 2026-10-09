"""Decide whether a layer's Worker needs Copier's ``unsafe`` grant for extensions."""

from boilerplate.composition.models.composition_layer import CompositionLayer
from boilerplate.composition.views import LayerView


def grants_unsafe(layer: CompositionLayer, view: LayerView) -> bool:
    """Return whether `layer`'s Worker loads Jinja extensions under `view`.

    Copier refuses to load an extension without the grant, and the grant also
    switches off Copier's check that a render stays inside the project, so it
    goes to a Worker that loads one and to no other. The Worker loads the
    view's importable extensions, the ancestors' registered files and the
    layer's own declarations. The tasks a Worker runs are decided apart from
    this, where the Worker is built.

    Args:
        layer: The layer the Worker renders.
        view: The view the Worker renders under.

    Returns:
        True when the Worker loads any extension.
    """
    return view.loads_extensions or bool(layer.values.get("_jinja_extensions"))
