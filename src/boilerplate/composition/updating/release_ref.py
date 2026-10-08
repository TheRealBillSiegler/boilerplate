"""A layer's template at one release."""

from pydantic import BaseModel, ConfigDict


class ReleaseRef(BaseModel):
    """Where a layer's template is and the ref that names its release.

    Attributes:
        source: The template source, as the layer's answers file records it in
            ``_src_path``.
        ref: The tag, ``git describe`` string or commit of the release.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    ref: str
