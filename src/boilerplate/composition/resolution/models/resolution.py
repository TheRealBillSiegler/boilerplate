"""Result model for dependency resolution."""

from pydantic import BaseModel, ConfigDict

from boilerplate.composition.graph import DependencyMap
from boilerplate.composition.graph.topology import toposort_dependencies
from boilerplate.models.template_info import TemplateInfo


class Resolution(BaseModel):
    """Result of dependency resolution.

    Contains both the dependency graph structure and the resolved template information.
    """

    model_config = ConfigDict(frozen=True)

    deps: DependencyMap
    """Dependency map showing relationships between templates by specifier."""

    templates: dict[str, TemplateInfo]
    """Template information keyed by template specifier string."""

    @property
    def execution_sequence(self) -> list[str]:
        """Sequence to apply templates (dependencies first)."""
        return toposort_dependencies(self.deps)


__all__ = [
    "Resolution",
]
