"""One entry of the ``.boilerplate/migrations.yml`` audit log."""
# Spec: docs/design/02-data-models.md §MigrationRecord

from collections.abc import Mapping
from typing import Self

from packaging.version import InvalidVersion, Version
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from boilerplate.models.change_classification import ChangeClassification
from boilerplate.models.migration_status import MigrationStatus

__all__ = ["MigrationRecord"]


class MigrationRecord(BaseModel):
    """One operation Boilerplate recorded: its versions, outcome and, if paused, plan.

    A ``conflict`` record is what a paused update resumes from: ``targets`` names
    the version the walk was updating each layer to, and ``finished`` the
    layers whose steps the walk completed.

    Attributes:
        id: A positive integer, sequential from ``"1"``, stored as a string.
        from_version: The root template specifier before the operation;
            ``None`` where there was no prior state.
        to_version: The root template specifier after the operation; for an
            ``add`` record, the added layer's specifier.
        timestamp: When the record was written (UTC).
        status: How the operation stands.
        error: The error message when the status is not a success-shaped one.
        classification: The update's size; ``None`` where no prior-version
            comparison applies.
        targets: On a ``conflict`` record, each layer's target version keyed by
            layer name; ``None`` on every other record.
        finished: On a ``conflict`` record, the layers the paused walk
            finished, in walk order; ``None`` on every other record.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(pattern=r"^[1-9][0-9]*$")
    from_version: str | None = None
    to_version: str
    timestamp: AwareDatetime
    status: MigrationStatus
    error: str | None = None
    classification: ChangeClassification | None = None
    targets: Mapping[str, str] | None = None
    finished: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _check_resume_fields(self) -> Self:
        """Require ``targets`` and ``finished`` on a conflict record and only there.

        Returns:
            The validated record.

        Raises:
            ValueError: If a ``conflict`` record lacks either field, another
                record carries one, a finished layer has no target, or a target
                is not a PEP 440 version.
        """
        if self.status is not MigrationStatus.CONFLICT:
            for name in ("targets", "finished"):
                if getattr(self, name) is not None:
                    raise ValueError(f"{name} belongs to a conflict record only")
            return self
        if self.targets is None:
            raise ValueError("a conflict record needs targets")
        if self.finished is None:
            raise ValueError("a conflict record needs finished")
        for layer, version in self.targets.items():
            try:
                Version(version)
            except InvalidVersion as error:
                raise ValueError(
                    f"target for {layer!r} is not a PEP 440 version: {version!r}"
                ) from error
        unknown = [layer for layer in self.finished if layer not in self.targets]
        if unknown:
            raise ValueError(f"finished layer(s) {unknown} have no target")
        return self
