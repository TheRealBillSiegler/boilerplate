"""RenderEngine: orchestrate Copier runs over a composed template.

The merged questionnaire is asked once; each composition layer then renders
through Copier under its own scoped view, as a `MergedTemplate`, so the view's
questions and (on the final layer) the merged tasks are visible to the Worker
without mutating the on-disk template.

All behavior is deterministic and side-effect free except for file I/O
performed by Copier.
"""
# Spec: docs/design/04-composition-engine.md §Stage 4 — RenderEngine

from logging import getLogger
from pathlib import Path

from boilerplate import __version__
from boilerplate.common.exceptions import (
    DestinationNotEmptyError,
    MissingRequiredAnswersError,
)
from boilerplate.composition.models.composition import Composition
from boilerplate.composition.models.composition_layer import CompositionLayer
from boilerplate.composition.rendering.creation_lock import write_creation_lock
from boilerplate.composition.rendering.grants_unsafe import grants_unsafe
from boilerplate.composition.rendering.models.execution_context import ExecutionContext
from boilerplate.composition.rendering.questionnaire import ask_questionnaire
from boilerplate.composition.rendering.worker_options import WorkerOptions
from boilerplate.composition.rendering.worker_session import worker_session
from boilerplate.composition.tasks import normalize_tasks
from boilerplate.composition.views import (
    LayerView,
    build_layer_view,
    scope_composition,
)
from boilerplate.integrations.copier_types import DEFAULT_EXCLUDE
from boilerplate.integrations.copier_types import Template as CopierTemplate
from boilerplate.models.template_info import TemplateInfo
from boilerplate.models.template_meta import TemplateMeta

_logger = getLogger(__name__)

# Template-authoring files that must never survive into a rendered project,
# regardless of what a layer's own `copier.yml` declares under `_exclude`.
# `boilerplate.yml` is never covered by Copier's own default exclusions.
# Passed via `Worker.exclude`, these merge additively with each layer's own
# `_exclude` (`Worker.all_exclusions = template.exclude + worker.exclude`),
# per docs/design/04-composition-engine.md §Per-Layer Render Loop. Leading
# `/` anchors each pattern to the destination root under copier's
# gitignore-style matcher, so a template that legitimately ships a nested
# file with one of these names (e.g. `docs/copier.yml`) is left alone — only
# the layer-root metadata file is stripped.
_AUTHORING_METADATA_EXCLUDES: tuple[str, ...] = ("/boilerplate.yml", "/copier.yml")

# Copier's own DEFAULT_EXCLUDE (`.git`, `__pycache__`, `~*`, etc.) is only
# applied when a layer's `copier.yml` leaves `_exclude` unset; a layer that
# declares its own `_exclude` (e.g. `templates/project/copier.yml`'s
# `_exclude: [_extensions]`) replaces Copier's default outright rather than
# extending it, forfeiting its protection against template-authoring
# artifacts leaking into rendered output. Folding it into the worker-level
# excludes reinstates it unconditionally, since `Worker.exclude` is always
# additive with a layer's own `_exclude` regardless of what that layer
# declares. `copier.yaml`/`copier.yml` are dropped from the fold-in: Copier
# ships those two unanchored (matching at any depth), which would strip a
# template's legitimate nested `docs/copier.yml`; `_AUTHORING_METADATA_EXCLUDES`
# already covers the root-level file, root-anchored.
_WORKER_EXCLUDES: tuple[str, ...] = (
    *_AUTHORING_METADATA_EXCLUDES,
    *(p for p in DEFAULT_EXCLUDE if p not in {"copier.yaml", "copier.yml"}),
)


def _is_non_empty_directory(path: Path) -> bool:
    """Report whether `path` is a directory holding at least one entry.

    Args:
        path: The render destination.

    Returns:
        Whether the directory exists and lists any file or folder, hidden
        ones included.
    """
    return path.is_dir() and any(path.iterdir())


def final_template_info(*, final_path: Path, fallback_name: str) -> TemplateInfo:
    """Build the TemplateInfo for a rendered final layer.

    Args:
        final_path: Filesystem path of the final (root) template.
        fallback_name: Name to use if metadata is missing.

    Returns:
        TemplateInfo describing the final layer and a Copier Template instance.
    """
    try:
        meta = TemplateMeta.load(final_path)
        name = meta.name
    except Exception as e:
        _logger.exception(
            "Template metadata load failed, using fallback for %s: %s",
            final_path,
            e,
        )
        meta = TemplateMeta.model_construct(
            schema_version=TemplateMeta.model_fields["schema_version"].default,
            name=fallback_name,
            description="",
            version="0.0.0",
            extends=[],
        )
        name = fallback_name

    try:
        # No ref, matching the compose render: the engine hands the Worker no
        # vcs_ref, so ScopedWorker.template builds the MergedTemplate at
        # Copier's default resolution (latest tag for a git-backed layer, plain
        # copy otherwise), the provenance contract of
        # docs/design/adr-015-idiomatic-artifacts.md; this description of "the
        # template" must name the same revision the render wrote.
        copier_template = CopierTemplate(url=str(final_path))
        return TemplateInfo(
            name=name,
            meta=meta,
            location=final_path,
            copier_template=copier_template,
        )
    except Exception as e:
        _logger.exception("Copier template creation failed for %s: %s", final_path, e)
        _logger.warning("Template %s will render without copier integration", name)
        return TemplateInfo.model_construct(
            name=name, meta=meta, location=final_path, copier_template=None
        )


class RenderEngine:
    """Ask the merged questionnaire once, then render each layer under its view."""

    def __init__(self, boilerplate_version: str = __version__) -> None:
        """Prepare an engine that stamps the locks it writes with a tool version.

        Args:
            boilerplate_version: The version of the tool, recorded in the lock.
        """
        self._boilerplate_version = boilerplate_version

    def render(self, composition: Composition, ctx: ExecutionContext) -> TemplateInfo:
        """Render all layers of `composition` into `ctx.destination`.

        One questionnaire pass over the full merged schema answers every
        question; each layer then renders, in topological order, under its
        scoped view with those answers as data, so its answers file records
        only its own and its ancestors' questions. The merged tasks run once, on
        the last layer. A successful render ends with ``boilerplate.lock``.

        Args:
            composition: Computed composition (layers and final merged schema).
            ctx: Execution parameters including destination path and base context.

        Returns:
            Information about the final (root) template after render.

        Raises:
            DestinationNotEmptyError: If the destination already holds files and
                ``ctx.overwrite`` does not consent to writing over them.
            MissingRequiredAnswersError: If a non-interactive render leaves a
                question without a default or a supplied value.
        """
        # Pre-flight: every layer after the first renders with overwrite
        # forced, so a destination that already holds files would have them
        # replaced unasked. Refuse it before anything is asked or written,
        # unless --force consents (docs/design/06-project-lifecycle.md,
        # Acceptance Criteria).
        if not ctx.overwrite and _is_non_empty_directory(ctx.destination):
            raise DestinationNotEmptyError(
                f"Destination '{ctx.destination}' is not empty.",
                remediation=(
                    "Choose a new or empty directory, or add --force to "
                    "overwrite the files in this one."
                ),
            )

        # Build the canonical questionnaire once from the merged schema
        questions_schema: dict[str, object] = dict(composition.merged_questions_schema)

        # Forced answers (Copier `data`) vs overridable pre-fills
        # (Copier `user_defaults`). Both come from ExecutionContext.
        base_context: dict[str, object] = dict(ctx.context_data or {})
        profile_answers: dict[str, object] = dict(ctx.profile or {})

        # Pre-flight: in non-interactive mode, fail fast with a named-fields
        # error when required questions have no default and no supplied
        # value. Without this check, Copier would fall through to
        # questionary, which constructs a prompt_toolkit PromptSession that
        # crashes in non-TTY environments (Git Bash pseudo-TTY, Windows CI
        # without a console buffer). The named-fields error is strictly
        # better UX regardless of TTY status. A profile default satisfies a
        # question too (Copier falls back to it under `defaults=True`).
        if not ctx.interactive:
            missing = self._find_missing_required_answers(
                questions=questions_schema,
                supplied={**profile_answers, **base_context},
            )
            if missing:
                raise MissingRequiredAnswersError(
                    "Non-interactive render cannot proceed — these questions "
                    f"have no default and no supplied value: {', '.join(missing)}."
                )

        asked = ask_questionnaire(
            composition,
            destination=ctx.destination,
            data=base_context,
            user_defaults=profile_answers,
            defaults=not ctx.interactive,
        )
        answers: dict[str, object] = {**asked.user, **asked.metadata}
        tasks_value = normalize_tasks(composition.final)

        for idx, layer in enumerate(composition.layers):
            is_first_layer = idx == 0
            is_final_layer = idx == len(composition.layers) - 1
            layer_tasks_value = tasks_value if is_final_layer else []
            view = self._scoped_view(composition, layer, is_final_layer=is_final_layer)

            skip_tasks_flag = (not is_final_layer) or bool(ctx.skip_tasks)

            # `unsafe` bypasses Copier's own consent gate for jinja_extensions
            # and task execution (Worker._check_unsafe), and also switches off
            # its check that a render stays inside the project; scope it to
            # exactly what Copier's check would flag for *this* layer's Worker
            # invocation: the extensions of its scoped view, or the tasks it
            # runs. A layer whose scoped view declares no extension keeps
            # unsafe=False when it runs no tasks, the permissive posture of
            # docs/design/adr-003-permissive-execution.md.
            layer_needs_unsafe = grants_unsafe(layer, view) or (
                bool(layer_tasks_value) and not skip_tasks_flag
            )

            # Non-first layers always overwrite: composition is defined as
            # layers overlaying the previous output. User's --force only
            # governs the first layer (writing into a pre-existing
            # destination); subsequent layers are orchestrated writes, not
            # conflicting ones.
            worker_opts: WorkerOptions = {
                "src_path": str(layer.path),
                "dst_path": ctx.destination,
                "data": answers,
                "user_defaults": profile_answers,
                "unsafe": layer_needs_unsafe,
                "overwrite": bool(ctx.overwrite) if is_first_layer else True,
                # Every answer is in `data`; no layer prompts.
                "defaults": True,
                "skip_tasks": skip_tasks_flag,
                "exclude": _WORKER_EXCLUDES,
            }

            with worker_session(
                worker_opts,
                view,
                tasks=layer_tasks_value,
                fallback_version=layer.version,
            ) as worker:
                worker.run_copy()  # Critical operation that can fail silently

        write_creation_lock(
            ctx.destination,
            composition,
            boilerplate_version=self._boilerplate_version,
        )
        final_layer = composition.layers[-1]
        return final_template_info(
            final_path=final_layer.path, fallback_name=final_layer.name
        )

    @staticmethod
    def _scoped_view(
        composition: Composition, layer: CompositionLayer, *, is_final_layer: bool
    ) -> LayerView:
        """Return the view `layer` renders under: its own and its ancestors' scope.

        Args:
            composition: The full composition.
            layer: The layer about to render.
            is_final_layer: Whether `layer` is the composition's last, whose
                scope is the whole composition.

        Returns:
            The layer's scoped view.
        """
        scoped = (
            composition
            if is_final_layer
            else scope_composition(composition, layer.name)
        )
        return build_layer_view(scoped)

    @staticmethod
    def _find_missing_required_answers(
        *,
        questions: dict[str, object],
        supplied: dict[str, object],
    ) -> list[str]:
        """Return names of required questions that have no supplied value.

        A question is "required" when it lacks both a ``default`` and a
        statically-false ``when`` (``when: false``, meaning "never ask;
        value is derived elsewhere"). A ``when`` given as a Jinja expression
        string (e.g. ``when: "{{ enable_docker }}"``) can only be resolved
        by Copier itself — it depends on other answers' runtime values,
        which this pre-flight does not simulate — so such questions are
        never reported as missing here. Copier's own non-interactive
        ``--defaults`` path already skips a question whose ``when``
        evaluates false at render time regardless of whether it has a
        default; treating an unresolvable ``when`` as blocking would
        false-positive a non-interactive render that Copier would have
        completed. Directive keys (``_``-prefixed, e.g. ``_tasks``,
        ``_exclude``) are not questions and are skipped. A question is
        satisfied when its name appears in ``supplied``.

        Args:
            questions: Merged question schema (name -> question dict).
            supplied: Pre-populated answers (e.g., from CLI flags).

        Returns:
            Question names that need answers but have none; empty when all
            required questions are satisfied.
        """
        missing: list[str] = []
        for name, raw in questions.items():
            if name.startswith("_"):
                continue  # directive, not a question
            if name in supplied:
                continue
            if not isinstance(raw, dict):
                continue  # malformed entry; leave for Copier to surface
            q: dict[str, object] = raw
            when = q.get("when", True)
            if when is False or isinstance(when, str):
                continue  # statically false, or only Copier can evaluate it
            if "default" in q:
                continue  # has a default Copier will use
            missing.append(name)
        return missing


__all__ = ["RenderEngine", "final_template_info"]
