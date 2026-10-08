"""Type-safe keyword options for the Copier ``Worker`` a render drives."""

from pathlib import Path
from typing import TypedDict


class WorkerOptions(TypedDict, total=False):
    """Type-safe options for copier Worker constructor."""

    src_path: str | None
    dst_path: Path
    data: dict[str, object]  # AnyByStrDict equivalent — forced answers
    user_defaults: dict[str, object]  # overridable prompt pre-fills
    unsafe: bool
    overwrite: bool
    defaults: bool
    skip_tasks: bool
    quiet: bool
    exclude: tuple[str, ...]


__all__ = ["WorkerOptions"]
