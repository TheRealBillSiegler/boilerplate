"""The data an update step of one layer passes to Copier.

The rule is pure: it takes the answers the project records, the layer that
declares each question and the values the user and earlier steps supply, and does
no I/O of its own.
"""

from collections.abc import Mapping
from typing import Any


def build_step_data(
    *,
    layer: str,
    declared_by: Mapping[str, str],
    recorded_by_layer: Mapping[str, Mapping[str, Any]],
    supplied: Mapping[str, Any],
    secrets: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the data a layer's update step passes to Copier.

    Copier reads the layer's own questions from the layer's own answers file,
    after the layer's before-migrations have run, and data outranks that file;
    so the layer's own recorded answers are never data. A question an ancestor
    declares arrives as data from the answers file of the layer that declares
    it, never from the layer's own, possibly stale, copy.

    Args:
        layer: The layer being updated.
        declared_by: The layer that declares each question in the layer's
            scope, keyed by question name.
        recorded_by_layer: Each layer's recorded answers, keyed by layer name.
        supplied: Values the user supplies; data for questions in the scope.
        secrets: Secret answers already given earlier in the same update; data
            for questions in the scope.

    Returns:
        The data for the step: the declaring ancestors' recorded answers, then
        the earlier secrets, then the supplied values on top.

    Examples:
        The ancestor's answer beats the layer's stale copy; the layer's own
        question is left to Copier:

        >>> build_step_data(
        ...     layer="service",
        ...     declared_by={"author": "core", "port": "service"},
        ...     recorded_by_layer={
        ...         "core": {"author": "Ada"},
        ...         "service": {"author": "Stale", "port": 80},
        ...     },
        ...     supplied={},
        ...     secrets={},
        ... )
        {'author': 'Ada'}
    """
    data: dict[str, Any] = {}
    for question, declarer in declared_by.items():
        recorded = recorded_by_layer.get(declarer, {})
        if declarer != layer and question in recorded:
            data[question] = recorded[question]
    for given in (secrets, supplied):
        data.update({k: v for k, v in given.items() if k in declared_by})
    return data
