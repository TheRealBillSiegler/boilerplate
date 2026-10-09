"""A Copier ``Worker`` that renders each copy of a compose or update under its view."""

import logging
from collections.abc import Mapping
from dataclasses import field
from functools import cached_property
from pathlib import Path
from typing import Any

from copier.errors import InvalidTypeError
from pydantic import ConfigDict
from pydantic.dataclasses import dataclass

from boilerplate.common.exceptions import RecordedAnswerRejectedError
from boilerplate.composition.rendering.hidden_questions import (
    RENDER_ERRORS,
    hidden_questions,
)
from boilerplate.composition.rendering.models.merged_template import MergedTemplate
from boilerplate.composition.rendering.render_role import RenderRole, render_role
from boilerplate.composition.views import (
    LayerView,
    registered_ancestor_extensions,
    view_config,
)
from boilerplate.integrations.copier_types import (
    MISSING,
    AnswersMap,
    CopierOperation,
    Question,
    Template,
    Worker,
    copier_operation,
    tasks_phase,
)

_logger = logging.getLogger(__name__)


# pydantic's @dataclass erases the Worker base class's type (hence the
# untyped-base and general-type suppressions on the line below).
@dataclass(config=ConfigDict(extra="forbid"))
class ScopedWorker(Worker):  # pyright: ignore[reportUntypedBaseClass, reportGeneralTypeIssues]
    """A Copier Worker that renders its layer under the view of the render it makes.

    Compose and update share it: compose renders each layer once, in place, under
    one view, so it gives no old view; an update gives the old and the target
    view.

    Copier's update renders an old copy at the recorded release, the project in
    place and a new copy at the target release, rebuilding a worker for each
    with ``dataclasses.replace``; a template primed on one worker instance never
    reaches those renders. Views held in fields travel with ``replace``, and
    each rebuilt worker picks the view for the render it makes from its
    destination. Its template ref cannot tell them apart: when only an ancestor
    moves, the layer's own ref is the same in all three renders, yet the old
    copy must render the questionnaire and extensions of the recorded
    ancestors and the other two those of the targets.

    The in-place render also checks, before Copier asks its questions, that the
    target view's questions still accept the answers the layer's answers file
    records. Copier itself silently drops a recorded answer its question
    rejects and records the new default. The check walks the questions in
    Copier's order and gives each later question the answers the earlier ones
    would have, so a ``when`` that reads a question the target adds sees its
    default.

    Copier builds the old copy from the layer's own answers file alone. The old
    copy fills each key that file lacks, as a hand-run vanilla update leaves
    it, from the answers the declaring layers recorded when the walk began, so
    it renders as the layer was last rendered and not at the questions'
    defaults. A key the file records keeps its own value, and a question the
    old view hides is not filled.

    Attributes:
        old_view: The view the old copy renders under; the target view when
            absent, as at compose.
        target_view: The view the in-place render and the new copy render under.
        layer: The layer being updated; names it in a rejected-answer error.
        old_copy_fill: The answers the declaring ancestors recorded when the
            walk began, for the questions of the old view they declare; the
            old copy takes those its own answers file lacks.
        tasks: The tasks the template runs, in Copier's shapes: for the
            post-walk task run (``run_tasks``) or for the final layer of a
            compose; empty for a layer's own update.
        honor_skip_if_exists: Whether the render keeps the template's own
            ``_skip_if_exists`` list. A compose clears it, because a forced
            render overwrites every file; an add and an update keep it.
        check_recorded: Whether the in-place render rejects a recorded answer
            the target view's question cannot take. A compose turns it off through
            ``worker_session``, since it supplies every answer as data; an
            update keeps it.
        fallback_version: The layer's ``boilerplate.yml`` version, reported as
            the template version when the layer is not a git repository; a
            git-derived version takes precedence. Unset for an update, whose
            layers are git-backed.
    """

    old_view: LayerView | None = field(default=None, kw_only=True)
    target_view: LayerView = field(kw_only=True)
    layer: str = field(default="", kw_only=True)
    old_copy_fill: Mapping[str, Any] = field(default_factory=dict, kw_only=True)
    tasks: tuple[Any, ...] = field(default=(), kw_only=True)
    honor_skip_if_exists: bool = field(default=True, kw_only=True)
    check_recorded: bool = field(default=True, kw_only=True)
    fallback_version: str | None = field(default=None, kw_only=True)

    def view_for_render(self) -> LayerView:
        """Return the view for the render this worker makes.

        Returns:
            The old view when the destination is the old copy's, else the
            target view.
        """
        if render_role(Path(self.dst_path)) is RenderRole.OLD_COPY:
            return self.old_view or self.target_view
        return self.target_view

    @cached_property
    def render_view(self) -> LayerView:
        """The view this worker renders under, chosen once from its destination."""
        return self.view_for_render()

    def run_copy(self) -> None:
        """Render with the ancestors' extension files of this render's view loaded.

        The old copy registers the recorded releases' files and the renders at
        the target the target releases', each under its own module names and
        only while it renders.
        """
        with registered_ancestor_extensions(self.render_view.ancestor_extensions):
            super().run_copy()

    def run_update(self) -> None:
        """Update with the target releases' extension files loaded.

        The update worker itself builds a Jinja environment, with the target
        view's extensions, outside any of the three renders.
        """
        with registered_ancestor_extensions(self.render_view.ancestor_extensions):
            super().run_update()

    def run_tasks(self, operation: CopierOperation = "update") -> None:
        """Run the template's tasks against the finished project as an update's.

        The project is the composed whole by now, so the tasks run once against
        it, as at creation, but under Copier's `operation`: a task's ``when:``
        sees ``_copier_operation`` as ``"update"`` after an update, where a
        template may guard a creation-only task, and as ``"copy"`` after an add,
        which a by-hand copy of the layer runs its tasks under. The tasks run
        in Copier's tasks phase too, so ``_copier_phase`` reads ``"tasks"`` as
        it does under Copier's own task run. Only ``run_copy``, ``run_recopy``
        and ``run_update`` set the operation and the phase, and this run is none
        of them, so the shim sets both. The questions are asked first, outside
        the tasks phase, as the task conditions and commands render against the
        answers; the project's recorded answers and the data the worker holds
        answer them all.

        Args:
            operation: The operation the tasks run under.

        Raises:
            TaskError: If a task exits non-zero; it names the command.
        """
        with (
            registered_ancestor_extensions(self.render_view.ancestor_extensions),
            copier_operation(operation),
        ):
            super()._ask()
            with tasks_phase():
                self._execute_tasks(self.template.tasks)

    def _ask(self) -> None:
        """Ask the questions, after rejecting a recorded answer the target cannot take.

        Copier calls this once per render, in the in-place render after the
        before-migrations have run and the answers file has been re-read. The
        old copy and the new copy render recorded releases and forced data, so
        only the in-place render checks. The old copy, whose data Copier sets
        to the layer's own recorded answers, first takes the keys they lack
        from ``old_copy_fill``.
        """
        role = render_role(Path(self.dst_path))
        if role is RenderRole.OLD_COPY:
            self.data = self.old_copy_data()
        elif self.check_recorded and role is RenderRole.IN_PLACE:
            self.check_recorded_answers()
        super()._ask()

    def old_copy_data(self) -> dict[str, Any]:
        """Return the old copy's data, the layer's own answers filled from ancestors.

        Copier records no answer for a question its ``when`` hides, yet data
        given for one still reaches the render, so only a question the old
        view shows under those answers is filled (``hidden_questions``); a
        hidden one keeps Copier's default, as when the layer was last
        rendered.

        Returns:
            The layer's own recorded answers, which Copier set as the old
            copy's data, with each key they lack taken from ``old_copy_fill``.
        """
        answers = {**self.old_copy_fill, **self.data}
        view = self.old_view or self.target_view
        hidden = hidden_questions(view.questions, answers, jinja_env=self.jinja_env)
        fill = {k: v for k, v in self.old_copy_fill.items() if k not in hidden}
        return {**fill, **self.data}

    def check_recorded_answers(self) -> None:
        """Check the layer's recorded answers against the target view's questions.

        Walk the questions in Copier's order, as ``Worker._ask`` does. For each
        one, a recorded answer is cast, narrowed to the question's choices and
        validated through Copier's own ``Question``; then its ``when`` is
        evaluated; then the answer Copier would see is filled in, so a later
        question's ``when``, choices and validator render against the earlier
        answers. That answer is the recorded or forced value when there is one
        and the question's rendered default otherwise; a question with neither
        fills nothing. An answer that data replaces is not checked as recorded;
        the data is parsed and validated as Copier does, for a secret too, and
        the walk ends there if it fails. The walk works on a copy of the
        recorded answers, so Copier's own pass starts from the file as it was.

        An interactive step cannot know what the prompt will take, so a later
        question sees the default there.

        The walk ends at the first question whose default fails, hidden or
        asked and interactive or not: the default cannot render, or it fails
        the question's validator or choices against the earlier answers the walk
        assumed. Copier fails there with its own error, or in an interactive
        step prompts earlier questions for answers that let the default pass.
        A non-interactive step also ends it at the first asked question with
        no default. It ends too at a ``when`` that cannot render, and treats a
        recorded answer the question cannot check, for want of a supported
        type or choices that render, as not rejected: Copier reports the
        template error, not a rejection.

        The walk assumes the worker has no ``ask`` patterns. Copier prompts a
        question one matches even under defaults, so with patterns set the
        walk would raise a rejection, or stop, where Copier asks.

        Raises:
            RecordedAnswerRejectedError: If a non-interactive step finds a
                recorded answer the target view's question rejects.
        """
        self.answers = AnswersMap(
            user_defaults=self.user_defaults,
            init=self.data,
            last=dict(self.subproject.last_answers),
            metadata=self.template.metadata,
            external=self._external_data(),
        )
        for name, details in self.template.questions_data.items():
            question = Question(
                answers=self.answers,
                context=self._render_context(),
                jinja_env=self.jinja_env,
                settings=self.settings,
                var_name=name,
                **details,
            )
            rejected = self._drop_rejected_recorded_answer(question)
            try:
                asked = question.get_when()
            except RENDER_ERRORS:
                return
            if asked and rejected is not None:
                self._handle_rejection(name, *rejected)
            if not asked:
                self.answers.hide(name)
                self.answers.last.pop(name, None)
            if self.skip_answered and self._recorded_and_not_replaced(name):
                continue
            try:
                answer = self._answer_copier_stores(question)
            except Exception:
                return
            if answer is not MISSING:
                self.answers.user[name] = answer
            elif asked and self.defaults:
                return

    def _recorded_and_not_replaced(self, name: str) -> bool:
        """Report whether the answers file records a question that data leaves alone.

        Args:
            name: The question's variable name.

        Returns:
            Whether the walk's recorded answers hold the question while the
            data passed to the update leaves it alone.
        """
        return name in self.answers.last and name not in self.answers.init

    def _drop_rejected_recorded_answer(
        self, question: Question
    ) -> tuple[object, str] | None:
        """Drop the question's recorded answer from the walk's copy if it is rejected.

        Copier drops such an answer too, before it evaluates the question's
        ``when``. It also drops one it cannot check because the question's
        type is unsupported or a part of the question fails to render, and
        then fails on the question itself. That answer is dropped here without
        a rejection, and the walk meets the error where Copier does.

        Args:
            question: The question, built against the walk's answers.

        Returns:
            The recorded answer and why it is rejected, or ``None`` when the
            question has no recorded answer, data replaces it, it passes, or
            the question cannot check it.
        """
        name = question.var_name
        if not self._recorded_and_not_replaced(name):
            return None
        value = self.answers.last[name]
        try:
            question.get_type_name()
        except (InvalidTypeError, *RENDER_ERRORS):
            reason = None
        else:
            try:
                question.validate_answer(question.parse_answer(value))
            except RENDER_ERRORS:
                reason = None
            except Exception as error:
                reason = str(error)
            else:
                return None
        del self.answers.last[name]
        return None if reason is None else (value, reason)

    def _answer_copier_stores(self, question: Question) -> object:
        """Return the answer Copier stores for a question it does not prompt.

        Data passed to the update is parsed and validated, whatever the
        question's type or whether it is a secret, which ``get_default`` does
        not check for a secret. Any other question gets its default.

        Args:
            question: The question, built against the walk's answers.

        Returns:
            The data's value or the default, parsed to the question's type, or
            ``MISSING`` when the question has neither.

        Raises:
            Exception: Whatever Copier raises for a value that cannot parse or
                validate, or a default that cannot render.
        """
        name = question.var_name
        if name in self.answers.init:
            answer = question.parse_answer(self.answers.init[name])
            question.validate_answer(answer)
            return answer
        return question.get_default()

    def _handle_rejection(self, question: str, value: object, reason: str) -> None:
        """Stop a non-interactive step, or warn before the prompt asks again.

        Args:
            question: The question whose recorded answer is rejected.
            value: The recorded answer.
            reason: Why the target view's question rejects it.

        Raises:
            RecordedAnswerRejectedError: If the step does not prompt.
        """
        message = (
            f"Layer '{self.layer}': the recorded answer {value!r} for "
            f"'{question}' is rejected by the target version: {reason}"
        )
        if self.defaults:
            raise RecordedAnswerRejectedError(
                message,
                layer=self.layer,
                question=question,
                value=value,
                reason=reason,
            )
        _logger.warning("%s; asking for a valid one.", message)

    # Copier declares `template` as a cached_property on its own Worker; the
    # override swaps in the view-built template, which pyright reads as an
    # incompatible variable override.
    @cached_property
    def template(self) -> Template:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Build the template from the view of the render this worker makes.

        Raises:
            TypeError: If the worker has no source and the project records no
                template to take one from.
        """
        url = self.src_path
        if not url:
            if self.subproject.template is None:
                raise TypeError("Template not found")
            url = str(self.subproject.template.url)
        ref = self.resolved_vcs_ref
        view = self.render_view
        config = view_config(
            view,
            **({"tasks": list(self.tasks)} if self.tasks else {}),
            **({} if self.honor_skip_if_exists else {"skip_if_exists": []}),
        )
        result = MergedTemplate(
            url,
            dict(view.questions),
            config or None,
            ref=ref,
            fallback_version=self.fallback_version,
        )
        # Copier registers a template's cleanup only for the template it
        # builds itself; this one it never sees, and a VCS template clones
        # into a temp directory that only `_cleanup` removes.
        self._cleanup_hooks.append(result._cleanup)  # pyright: ignore[reportPrivateUsage]
        return result
