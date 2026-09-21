"""Implements a directory-based template repository for Boilerplate.

Provides DirectoryTemplateRepository, which scans directories for templates
and provides them through the TemplateRepository interface. Handles template
discovery, validation, and loading.

Limitations:
    - Only supports a single version (latest) for each template name in the
      scanned directory.
    - Skips directories that don't contain both a boilerplate.yml and a
      copier.yml.
    - Does not support historical or multiple versions per template name.
"""
# Spec: docs/design/03-template-system.md §Discovery Algorithm

from logging import getLogger
from pathlib import Path

from pydantic import ValidationError

from boilerplate.common.exceptions import (
    InvalidTemplateSpecifierError,
    MetadataValidationError,
)
from boilerplate.integrations.copier_types import Template as CopierTemplate
from boilerplate.models.template_info import TemplateInfo, TemplateMeta
from boilerplate.repository.template_repository import TemplateRepository
from boilerplate.types.template_specifier import TemplateSpecifier

_logger = getLogger(__name__)


class DirectoryTemplateRepository(TemplateRepository):
    """Directory-based template repository implementing TemplateRepository.

    Scans the specified directory for templates, validates their metadata,
    and loads them for use by coordinators such as TemplateCatalog.

    Limitations:
        - Only one version per template name is supported at a time.
        - Overwriting a template directory replaces the previous version.
    """

    def __init__(self, templates_dir: Path) -> None:
        """Initialize the repository with a templates directory.

        Args:
            templates_dir: Root directory containing template subdirectories.
        """
        self.templates_dir = templates_dir
        self._templates: dict[str, TemplateInfo] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load all templates from the directory into memory.

        A candidate directory with unreadable or invalid metadata is skipped
        with a warning naming the failing file; it does not abort discovery
        of the other templates in this directory. See
        docs/design/03-template-system.md §Discovery Algorithm.
        """
        if not self.templates_dir.exists() or not self.templates_dir.is_dir():
            return

        for sub in self.templates_dir.iterdir():
            if not sub.is_dir():
                continue

            boilerplate_yml = sub / "boilerplate.yml"
            copier_yml = sub / "copier.yml"

            if not (boilerplate_yml.exists() and copier_yml.exists()):
                continue

            try:
                meta = TemplateMeta.load(sub)
                copier_template = CopierTemplate(str(sub))

                # Validate template specifier format
                tag = f"{meta.name}@{meta.version}"
                try:
                    parsed = TemplateSpecifier.from_string(tag)
                except InvalidTemplateSpecifierError as e:
                    raise MetadataValidationError(
                        f"Invalid template specifier format at {boilerplate_yml}: {tag}"
                    ) from e

                if parsed.name != meta.name or parsed.version != meta.version:
                    raise MetadataValidationError(
                        f"Metadata mismatch at {boilerplate_yml}: tag {tag} disagrees with meta."
                    )

                tpl = TemplateInfo(
                    name=meta.name,
                    location=sub,
                    meta=meta,
                    copier_template=copier_template,
                )

                # Keep only the highest version for each template name
                existing = self._templates.get(meta.name)
                if existing is None or tpl.meta.version > existing.meta.version:
                    self._templates[meta.name] = tpl

            except FileNotFoundError as e:
                _logger.warning(
                    "Skipping template candidate, metadata file missing: %s (%s)",
                    boilerplate_yml,
                    e,
                )
            except ValidationError as e:
                err = MetadataValidationError(
                    f"Invalid template metadata in {boilerplate_yml}: {e}"
                )
                _logger.warning(
                    "Skipping template candidate [%s]: %s", err.error_code, err
                )
            except MetadataValidationError as e:
                _logger.warning("Skipping template candidate [%s]: %s", e.error_code, e)

    def load_templates(self) -> list[TemplateInfo]:
        """Return the templates discovered when this repository was constructed.

        Discovery runs once, in ``__init__``; this method only hands back the
        result, so repeated calls cost nothing and see no filesystem changes.

        Returns:
            All available templates.
        """
        return list(self._templates.values())
