"""Defines TemplateInfo: template metadata plus name, location, and Copier template."""
# Spec: docs/design/02-data-models.md §TemplateInfo

from pathlib import Path

from pydantic import BaseModel, Field, computed_field

from boilerplate.integrations.copier_types import Template as CopierTemplate
from boilerplate.models.template_meta import TemplateMeta
from boilerplate.types.template_specifier import TemplateSpecifier


class TemplateInfo(BaseModel):
    """Holds the resolved metadata, name, and location of a discovered template.

    Attributes:
        name: The unique name of the template (usually the directory name).
        meta: Parsed metadata from the template's config file.
        location: Filesystem path to the root of the template.
        copier_template: The Copier template instance for this template.
        specifier: Computed template specifier combining name and version.
    """

    name: str = Field(...)
    meta: TemplateMeta = Field(...)
    location: Path = Field(...)
    copier_template: CopierTemplate = Field(...)

    @computed_field
    @property
    def specifier(self) -> TemplateSpecifier:
        """Gets the template specifier for this template.

        Returns:
            A specifier combining the template name and version.

        Example:
            >>> # Assuming template_info is a TemplateInfo instance
            >>> # template_info.specifier
            >>> # TemplateSpecifier(name='mytemplate', version='1.2.3')
            >>> from boilerplate.types.template_specifier import TemplateSpecifier
            >>> specifier = TemplateSpecifier("example", "1.0.0")
            >>> str(specifier)
            'example@1.0.0'
        """
        return TemplateSpecifier(self.name, self.meta.version)
