"""Defines TemplateCatalog as a canonical, in-memory index for Boilerplate templates.

Handles lookup, registration, and listing by canonical tag, name, and version.
"""
# Spec: docs/design/03-template-system.md §Template Discovery and Catalog Sources

from collections.abc import Iterator
from logging import getLogger

from packaging.version import Version

from boilerplate.models.template_info import TemplateInfo

_logger = getLogger(__name__)


class TemplateCatalog:
    """Represents an in-memory catalog of canonical templates.

    Indexed by tag and name/version.
    """

    def __init__(self) -> None:
        """Initializes an empty catalog."""
        self._by_tag: dict[str, TemplateInfo] = {}
        self._by_name: dict[str, dict[Version, TemplateInfo]] = {}

    def register(self, template: TemplateInfo) -> None:
        """Registers a single TemplateInfo with the catalog.

        Uses "first one wins" policy - if a template with the same name@version
        already exists, the existing one is kept and the new one is ignored.

        Args:
            template: Template to register.
        """
        tag = f"{template.name}@{template.meta.version}"

        # First one wins - don't overwrite existing templates
        if tag in self._by_tag:
            existing_template = self._by_tag[tag]
            _logger.debug(
                "Template %s already registered from %s, ignoring duplicate from %s",
                tag,
                existing_template.location,
                template.location,
            )
            return

        _logger.debug("Registering template %s from %s", tag, template.location)
        self._by_tag[tag] = template
        if template.name not in self._by_name:
            self._by_name[template.name] = {}
        self._by_name[template.name][template.meta.version] = template

    def register_many(self, templates: list[TemplateInfo]) -> None:
        """Registers multiple TemplateInfo objects with the catalog.

        Args:
            templates: Templates to register.
        """
        for tpl in templates:
            self.register(tpl)

    def get_by_tag(self, tag: str) -> TemplateInfo | None:
        """Looks up a template by canonical tag.

        Args:
            tag: Canonical template tag (e.g., 'project@1.2.3').

        Returns:
            The template if found, else None.
        """
        return self._by_tag.get(tag)

    def _normalize_version(self, version: Version | str | None) -> Version | None:
        """Converts version parameter to Version object if needed.

        Args:
            version: Version object, version string, or None.

        Returns:
            Version object or None if input was None.

        Raises:
            ValueError: If version string is invalid.
        """
        if version is None or isinstance(version, Version):
            return version
        return Version(version)

    def resolve(
        self, name: str, version: Version | str | None = None
    ) -> TemplateInfo | None:
        """Resolves a template by name and optional version.

        Args:
            name: Canonical template name.
            version: Specific version, version string, or None for latest.

        Returns:
            The template if found, else None.

        Raises:
            ValueError: If version string is invalid.
        """
        versions = self._by_name.get(name, {})
        if not versions:
            return None

        normalized_version = self._normalize_version(version)

        if normalized_version is None:
            # Return latest version
            latest_version = max(versions.keys())
            return versions[latest_version]

        # Return specific version
        return versions.get(normalized_version)

    def resolve_latest(self, name: str) -> TemplateInfo | None:
        """Returns the highest-versioned template for a name per PEP 440.

        Args:
            name: Canonical template name.

        Returns:
            The template with the highest version if found, else None.
        """
        return self.resolve(name, None)

    def list_all(self) -> list[TemplateInfo]:
        """Returns all registered templates.

        Returns:
            All registered templates.
        """
        return list(self._by_tag.values())

    def list_tags(self) -> list[str]:
        """Returns all registered canonical tags.

        Returns:
            All tags.
        """
        return list(self._by_tag.keys())

    def __len__(self) -> int:
        """Returns the number of unique registered templates (by tag).

        Returns:
            Number of registered templates.
        """
        return len(self._by_tag)

    def __iter__(self) -> Iterator[TemplateInfo]:
        """Iterates over all registered TemplateInfo.

        Returns:
            Iterator of templates.
        """
        return iter(self._by_tag.values())
