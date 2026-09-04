"""Defines the TemplateRepository abstract base class.

Provides template discovery and loading for template sources in Boilerplate.
"""
# Spec: docs/design/02-data-models.md §TemplateRepository

from abc import ABC, abstractmethod

from boilerplate.models.template_info import TemplateInfo


class TemplateRepository(ABC):
    """Defines the abstract interface for template repositories.

    Template repositories discover templates from a source (e.g., a directory,
    a Git remote) and load them for use by coordinators such as TemplateCatalog.
    """

    @abstractmethod
    def load_templates(self) -> list[TemplateInfo]:
        """Loads all available templates from this repository.

        Returns:
            All available templates.
        """
