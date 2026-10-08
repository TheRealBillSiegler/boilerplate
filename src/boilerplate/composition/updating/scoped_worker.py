"""A Copier ``Worker`` that renders every copy of an update under its own view."""

from dataclasses import field
from functools import cached_property

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass

from boilerplate.composition.rendering.models.merged_template import MergedTemplate
from boilerplate.composition.views import LayerView, view_config
from boilerplate.integrations.copier_types import Template, Worker


# pydantic's @dataclass erases the Worker base class's type (hence the
# untyped-base and general-type suppressions on the line below).
@dataclass(config=ConfigDict(extra="forbid"))
class ScopedWorker(Worker):  # pyright: ignore[reportUntypedBaseClass, reportGeneralTypeIssues]
    """A Copier Worker that renders its layer under the view of the ref it renders.

    Copier's update renders an old copy at the recorded ref, the project in
    place and a new copy at the target ref, rebuilding a worker for each with
    ``dataclasses.replace``; a template primed on one worker instance never
    reaches those renders. Views held in a field travel with ``replace``, and
    each rebuilt worker builds its template from the view keyed by the
    ``vcs_ref`` Copier sets on it, so the old copy renders the questionnaire
    of the release it reconstructs and the new copy that of the target.

    Attributes:
        views_by_ref: The view to render under, keyed by template ref.
    """

    views_by_ref: dict[str, LayerView] = field(default_factory=dict)

    def view_for(self, ref: str | None) -> LayerView:
        """Return the view this worker renders under at `ref`.

        Args:
            ref: The template ref Copier set on this worker.

        Returns:
            The view keyed by `ref`.

        Raises:
            KeyError: If no view is keyed by `ref`.
        """
        if ref is None or ref not in self.views_by_ref:
            raise KeyError(f"no view for ref {ref!r}; have {sorted(self.views_by_ref)}")
        return self.views_by_ref[ref]

    # Copier declares `template` as a cached_property on its own Worker; the
    # override swaps in the view-built template, which pyright reads as an
    # incompatible variable override.
    @cached_property
    def template(self) -> Template:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Build the template from the view keyed by this worker's ref."""
        url = self.src_path
        if not url:
            assert self.subproject.template is not None
            url = str(self.subproject.template.url)
        ref = self.resolved_vcs_ref
        view = self.view_for(ref)
        result = MergedTemplate(
            url, dict(view.questions), view_config(view) or None, ref=ref
        )
        # Copier registers a template's cleanup only for the template it
        # builds itself; this one it never sees, and a VCS template clones
        # into a temp directory that only `_cleanup` removes.
        self._cleanup_hooks.append(result._cleanup)  # pyright: ignore[reportPrivateUsage]
        return result
