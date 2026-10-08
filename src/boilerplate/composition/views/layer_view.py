"""The questionnaire and extensions one layer renders under."""

from collections.abc import Mapping
from typing import Any, NamedTuple


class LayerView(NamedTuple):
    """The questionnaire and extensions one layer renders under.

    Attributes:
        questions: The merged question schema, keyed by question name.
        extensions: Importable ``_jinja_extensions`` specs, in merge order.
            Filepath-style specs resolve inside the declaring layer's own
            tree, so they stay layer-local and never appear here; Copier
            still loads them from the layer's own ``copier.yml``.
    """

    questions: Mapping[str, Any]
    extensions: tuple[str, ...]
