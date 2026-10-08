"""The questionnaire and extensions one layer renders under."""

from collections.abc import Mapping
from typing import Any, NamedTuple

from boilerplate.composition.views.ancestor_extension import AncestorExtension


class LayerView(NamedTuple):
    """The questionnaire and extensions one layer renders under.

    Attributes:
        questions: The merged question schema, keyed by question name.
        extensions: Importable ``_jinja_extensions`` specs, in merge order.
            Filepath-style specs resolve inside the declaring layer's own
            tree, so the layer's own never appear here; Copier still loads
            them from the layer's own ``copier.yml``.
        ancestor_extensions: The filepath-style specs the layer's ancestors
            declare, each as the file at the release the view was built for.
            A render registers them as modules for its duration.
    """

    questions: Mapping[str, Any]
    extensions: tuple[str, ...]
    ancestor_extensions: tuple[AncestorExtension, ...] = ()
