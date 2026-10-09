"""The layer release an update moves a project to."""

from typing import Self

from boilerplate.composition.updating.release_ref import ReleaseRef


class LayerRelease(ReleaseRef):
    """One layer of a composed project and the release to update it to.

    The release is a `ReleaseRef`: the source stays the string the layer's
    answers file records, where a path would rewrite a URL's slashes. The class
    subclasses `ReleaseRef` rather than holding one, so a `LayerRelease` is
    accepted wherever a `ReleaseRef` is, such as the mapping passed to
    `ReleaseViews`.

    Attributes:
        layer: The layer to update; names its ``.copier-answers.<layer>.yml``.
    """

    layer: str

    @classmethod
    def from_release(cls, layer: str, release: ReleaseRef) -> Self:
        """Build the release of `layer` from the release its template moves to.

        Args:
            layer: The layer to update.
            release: The layer's template source and the ref of its target.

        Returns:
            The layer's release.

        Examples:
            >>> release = ReleaseRef(source="https://example.com/core.git", ref="v2")
            >>> LayerRelease.from_release("core", release).layer
            'core'
        """
        return cls(layer=layer, source=release.source, ref=release.ref)
