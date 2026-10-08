"""The layer release an update moves a project to."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class LayerRelease(BaseModel):
    """One layer of a composed project and the release to update it to.

    Attributes:
        layer: The layer to update; names its ``.copier-answers.<layer>.yml``.
        source: The layer's git-backed template source, a local path or a URL; a
            string stays as written, where a path would rewrite a URL's slashes.
        ref: The git ref of the target template version.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    layer: str
    source: Path | str
    ref: str
