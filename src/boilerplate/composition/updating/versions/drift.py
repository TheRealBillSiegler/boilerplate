"""Find the layers whose recorded versions disagree with the lock."""
# Spec: docs/design/04-composition-engine.md §Safe Update

from collections.abc import Sequence

from boilerplate.common.exceptions import UpdateLayerDriftError
from boilerplate.composition.updating.versions.drift_warning import DriftWarning
from boilerplate.composition.updating.versions.layer_versions import LayerVersions

__all__ = ["check_drift"]


def check_drift(layers: Sequence[LayerVersions]) -> tuple[DriftWarning, ...]:
    """Stop on a layer and an ancestor that both disagree with the lock.

    Run this only when no pending ``conflict`` record binds. The walk could not
    tell which versions such a layer's files were last rendered against, as
    after a hand-run update of each. Any other disagreement, such as a hand-run
    update of one layer, is returned as a warning.

    Args:
        layers: Every layer of the project, in the lock's walk order.

    Returns:
        A warning for each disagreeing layer, in walk order; empty when every
        layer matches the lock.

    Raises:
        UpdateLayerDriftError: If a layer and one of its ancestors both
            disagree with the lock. The message names each such layer's
            ``_commit`` and the lock's version.
    """
    disagreeing = {layer.name: layer for layer in layers if layer.disagrees_with_lock}
    stopped = [
        layer
        for layer in disagreeing.values()
        if any(ancestor in disagreeing for ancestor in layer.ancestors)
        or any(layer.name in other.ancestors for other in disagreeing.values())
    ]
    if stopped:
        lines = "\n".join(
            f"  {layer.name}: _commit {layer.commit}, boilerplate.lock {layer.lock_version}"
            for layer in stopped
        )
        raise UpdateLayerDriftError(
            "A layer and one of its ancestors both disagree with boilerplate.lock, "
            f"as after a hand-run update of each:\n{lines}",
            layers=[layer.name for layer in stopped],
        )
    return tuple(
        DriftWarning(
            layer=layer.name, commit=layer.commit or "", lock_version=layer.lock_version
        )
        for layer in disagreeing.values()
    )
