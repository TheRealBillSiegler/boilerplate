"""Settings for the Boilerplate CLI."""
# Spec: docs/design/02-data-models.md §Settings

from functools import cached_property
from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration for the Boilerplate CLI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BOILERPLATE_",
        case_sensitive=False,
        extra="ignore",
        validate_assignment=True,
    )

    default_templates_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "templates",
        description="Default directory containing project templates.",
    )
    # Treat JSON null in env as [] using a small pre-validator.
    extra_template_dirs: Annotated[
        list[Path], BeforeValidator(lambda v: [] if v is None else v)
    ] = Field(
        default_factory=list,
        description="Additional directories to search for templates.",
    )

    @cached_property
    def template_dirs(self) -> list[Path]:
        """All configured template directories in resolution order."""
        return [self.default_templates_dir, *self.extra_template_dirs]

    log_dir: Path = Field(
        default_factory=lambda: Path.home() / ".boilerplate" / "logs",
        description="Directory to store log files.",
    )
    file_logging_enabled: bool = Field(
        default=False,
        description="Enable logging to a file.",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug logging mode.",
    )
