"""A Copier ``Worker`` that renders every copy of an update under its own view."""

from dataclasses import field
from functools import cached_property
from pathlib import Path

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass

from boilerplate.composition.rendering.models.merged_template import MergedTemplate
from boilerplate.composition.updating.render_role import RenderRole, render_role
from boilerplate.composition.views import LayerView, view_config
from boilerplate.integrations.copier_types import Template, Worker


# pydantic's @dataclass erases the Worker base class's type (hence the
# untyped-base and general-type suppressions on the line below).
@dataclass(config=ConfigDict(extra="forbid"))
class ScopedWorker(Worker):  # pyright: ignore[reportUntypedBaseClass, reportGeneralTypeIssues]
    """A Copier Worker that renders its layer under the view of the render it makes.

    Copier's update renders an old copy at the recorded release, the project in
    place and a new copy at the target release, rebuilding a worker for each
    with ``dataclasses.replace``; a template primed on one worker instance never
    reaches those renders. Views held in fields travel with ``replace``, and
    each rebuilt worker picks the view for the render it makes from its
    destination. Its template ref cannot tell them apart: when only an ancestor
    moves, the layer's own ref is the same in all three renders, yet the old
    copy must render the questionnaire and extensions of the recorded
    ancestors and the other two those of the targets.

    Attributes:
        old_view: The view the old copy renders under.
        target_view: The view the in-place render and the new copy render under.
    """

    old_view: LayerView = field(kw_only=True)
    target_view: LayerView = field(kw_only=True)

    def view_for_render(self) -> LayerView:
        """Return the view for the render this worker makes.

        Returns:
            The old view when the destination is the old copy's, else the
            target view.
        """
        if render_role(Path(self.dst_path)) is RenderRole.OLD_COPY:
            return self.old_view
        return self.target_view

    # Copier declares `template` as a cached_property on its own Worker; the
    # override swaps in the view-built template, which pyright reads as an
    # incompatible variable override.
    @cached_property
    def template(self) -> Template:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Build the template from the view of the render this worker makes."""
        url = self.src_path
        if not url:
            assert self.subproject.template is not None
            url = str(self.subproject.template.url)
        ref = self.resolved_vcs_ref
        view = self.view_for_render()
        result = MergedTemplate(
            url, dict(view.questions), view_config(view) or None, ref=ref
        )
        # Copier registers a template's cleanup only for the template it
        # builds itself; this one it never sees, and a VCS template clones
        # into a temp directory that only `_cleanup` removes.
        self._cleanup_hooks.append(result._cleanup)  # pyright: ignore[reportPrivateUsage]
        return result
