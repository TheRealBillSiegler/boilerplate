"""Read the tasks a template declares for itself."""

from pathlib import Path
from typing import Any

from boilerplate.composition.models.json_types import JSON
from boilerplate.composition.tasks import TASKS_KEY, normalize_tasks
from boilerplate.integrations.copier_types import load_template_config

_CONFIG_NAMES = ("copier.yml", "copier.yaml")


def own_tasks(template: Path) -> list[JSON]:
    """Return the ``_tasks`` of the template at `template`, in Copier's shapes.

    A layer added to a project runs its own tasks only: an ancestor's ran when
    the ancestor was rendered.

    Args:
        template: A checkout of the template.

    Returns:
        The layer's tasks in Copier's native shapes; empty when it declares none
        or has no ``copier.yml``.
    """
    for name in _CONFIG_NAMES:
        config_path = template / name
        if config_path.is_file():
            config: dict[str, Any] = load_template_config(config_path, quiet=True)
            return normalize_tasks({TASKS_KEY: config.get(TASKS_KEY)})
    return []
