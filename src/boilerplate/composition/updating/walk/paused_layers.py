"""Tell which layers a paused walk finished, from their answers files."""
# Spec: docs/design/06-project-lifecycle.md §Interrupted copy back

import logging
from collections.abc import Mapping
from pathlib import Path

import yaml
from packaging.version import InvalidVersion, Version

from boilerplate.integrations.copier_types import load_answersfile_data

__all__ = ["paused_layers"]

_logger = logging.getLogger(__name__)


def paused_layers(project: Path, targets: Mapping[str, str]) -> tuple[str, ...]:
    """Return the layers whose answers file records their target, in walk order.

    A paused walk leaves each layer it finished, the paused one among them,
    recording its target release in ``_commit``; a layer after the paused one
    still records its old release. The restore marker does not name the
    finished layers, so the conflict record of a paused run cut off before its
    record is rebuilt from the answers files.

    Args:
        project: The user's checkout, holding the answers files.
        targets: Each layer of the walk, in walk order, with its target version.

    Returns:
        The layers that record their target; empty when none does.
    """
    finished: list[str] = []
    for layer, target in targets.items():
        try:
            recorded = load_answersfile_data(project, f".copier-answers.{layer}.yml")
            commit = (recorded or {}).get("_commit")
            if commit is not None and Version(str(commit)) == Version(target):
                finished.append(layer)
        except (yaml.YAMLError, InvalidVersion) as error:
            _logger.warning(
                "Layer '%s': cannot read its recorded release: %s", layer, error
            )
    return tuple(finished)
