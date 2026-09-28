"""RenderEngine: orchestrate Copier runs over a composed template.

This module runs each composition layer through Copier using a `MergedTemplate`
so merged questions and (optionally) tasks are visible to the Worker without
mutating the on-disk template.

All behavior is deterministic and side-effect free except for file I/O
performed by Copier.
"""
# Spec: docs/design/04-composition-engine.md §Stage 4 — RenderEngine

import contextlib
import os
from collections.abc import Generator
from logging import getLogger
from pathlib import Path
from typing import TypedDict

from copier.errors import CopierAnswersInterrupt, InteractiveSessionError

from boilerplate.common.exceptions import (
    InteractiveRenderFailedError,
    MissingRequiredAnswersError,
    UserCancelledError,
)
from boilerplate.composition.models.composition import Composition
from boilerplate.composition.models.json_types import JSON
from boilerplate.composition.rendering.models.execution_context import ExecutionContext
from boilerplate.composition.rendering.models.merged_template import MergedTemplate
from boilerplate.composition.tasks import normalize_tasks
from boilerplate.integrations.copier_types import (
    DEFAULT_EXCLUDE,
    Template,  # For test compatibility
    Worker,
)
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


def _is_layer_local_extension(spec: str) -> bool:
    """Return whether a ``_jinja_extensions`` entry only works in its own layer.

    ``copier_template_extensions`` accepts filepath-style loader specs
    (``_extensions/context.py:ContextUpdater``) that it resolves relative to
    the rendering template's directory — such a spec cannot be shared with a
    sibling layer whose tree lacks the file. Importable specs (a dotted
    module path, with or without a ``:ClassName`` suffix) resolve identically
    from any layer and are safe to share.

    Args:
        spec: One ``_jinja_extensions`` list entry.

    Returns:
        True when the module portion is not a plain dotted import path.

    Examples:
        >>> _is_layer_local_extension("_extensions/context.py:ContextUpdater")
        True
        >>> _is_layer_local_extension(
        ...     "copier_template_extensions.TemplateExtensionLoader"
        ... )
        False
        >>> _is_layer_local_extension("pkg.module.slugify:SlugifyExtension")
        False
    """
    module_part = spec.split(":", 1)[0]
    return not all(part.isidentifier() for part in module_part.split("."))


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
        # No `ref`, matching `_build_merged_template`: this description of
        # "the template" must name the same revision the render wrote.
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
    exclude: tuple[str, ...]


class RenderEngine:
    """Runs Copier across composition layers using a merged question schema."""

    def render(self, composition: Composition, ctx: ExecutionContext) -> TemplateInfo:
        """Render all layers of `composition` into `ctx.destination`.

        Args:
            composition: Computed composition (layers and final merged schema).
            ctx: Execution parameters including destination path and base context.

        Returns:
            Information about the final (root) template after render.
        """
        # Build the canonical questionnaire once from the merged schema
        questions_schema: dict[str, object] = dict(composition.merged_questions_schema)

        # Forced answers (Copier `data`) vs overridable pre-fills (Copier
        # `user_defaults`). Both come from ExecutionContext.
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

        tasks_value = normalize_tasks(composition.final)

        # The merged questionnaire is asked by the first layer's Worker, so a
        # question default may reference a filter provided by a sibling
        # layer's Jinja extension. Every layer therefore renders under the
        # union of all layers' _jinja_extensions (computed by the merger) in
        # addition to its own declarations. Filepath-style loader specs
        # (e.g. `_extensions/file.py:Class`) are excluded: they resolve
        # relative to the declaring layer's own tree and cannot work from a
        # sibling layer, so they stay layer-local by construction.
        raw_extensions = composition.final.get("_jinja_extensions")
        extensions_value: list[str] = (
            [
                str(ext)
                for ext in raw_extensions
                if not _is_layer_local_extension(str(ext))
            ]
            if isinstance(raw_extensions, list)
            else []
        )

        collected_answers = base_context

        # Process all layers uniformly
        for idx, layer in enumerate(composition.layers):
            is_first_layer = idx == 0
            is_final_layer = idx == len(composition.layers) - 1
            layer_tasks_value = tasks_value if is_final_layer else []

            merged_template = self._build_merged_template(
                template_path=layer.path,
                merged_questions=questions_schema,
                tasks_value=layer_tasks_value,
                extensions_value=extensions_value,
                is_first_layer=is_first_layer,
                fallback_version=layer.version,
            )

            skip_tasks_flag = (not is_final_layer) or bool(ctx.skip_tasks)

            # `unsafe` bypasses Copier's own consent gate for jinja_extensions
            # and task execution (Worker._check_unsafe); scope it to what
            # *this* layer's Worker invocation actually needs instead of
            # granting it unconditionally. Because the merged-extension union
            # above is injected into every layer, any composition declaring
            # extensions anywhere runs all its layers with unsafe=True — the
            # permissive posture of
            # docs/design/adr-003-permissive-execution.md. Extension-free
            # compositions keep unsafe=False on layers that contribute no
            # tasks this invocation.
            layer_needs_unsafe = bool(merged_template.jinja_extensions) or (
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
                "data": collected_answers,
                "user_defaults": profile_answers,
                "unsafe": layer_needs_unsafe,
                "overwrite": bool(ctx.overwrite) if is_first_layer else True,
                "defaults": not bool(ctx.interactive) if is_first_layer else True,
                "skip_tasks": skip_tasks_flag,
                "exclude": _WORKER_EXCLUDES,
            }

            # First layer collects answers, subsequent layers use collected answers
            collected_answers = self._render_with_worker(
                worker_opts=worker_opts,
                merged_template=merged_template,
            )

        final_layer = composition.layers[-1]
        return final_template_info(
            final_path=final_layer.path, fallback_name=final_layer.name
        )

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

    @staticmethod
    def _build_merged_template(
        *,
        template_path: Path,
        merged_questions: dict[str, object],
        tasks_value: list[JSON],
        extensions_value: list[str],
        is_first_layer: bool,
        fallback_version: str | None = None,
    ) -> CopierTemplate:
        """Construct a `MergedTemplate` with questions, tasks, and extensions.

        Args:
            template_path: Path to the template layer on disk.
            merged_questions: The merged questionnaire (directive keys removed).
            tasks_value: Optional Copier tasks to expose via config.
            extensions_value: Union of every layer's ``_jinja_extensions``;
                injected so this layer's Worker can render merged questions
                and tasks that use sibling layers' filters.
            is_first_layer: Whether this is the composition's first layer.
                A non-first layer's own declared `_skip_if_exists` is cleared
                for this render — later layers overlay this render's own
                output (docs/design/04-composition-engine.md §Per-Layer
                Render Loop) — and continues to govern only that layer's own
                `copier update`.
            fallback_version: The layer's ``boilerplate.yml`` version, reported
                as the template version when the layer is not a git
                repository; a git-derived version takes precedence.

        Returns:
            A template object suitable for `copier.Worker`.
        """
        cfg: dict[str, object] = {}
        if tasks_value:
            cfg["tasks"] = tasks_value
        if extensions_value:
            cfg["jinja_extensions"] = extensions_value
        # A later layer overlays this render's own output (design 04 §Per-Layer
        # Render Loop); its declared list still governs its own `copier update`.
        if not is_first_layer:
            cfg["skip_if_exists"] = []
        # No `ref`: Copier's default resolution (latest tag for a git-backed
        # layer, plain copy otherwise) is the provenance contract of
        # docs/design/adr-015-idiomatic-artifacts.md — a render must record a
        # `_commit` that stays resolvable, and `HEAD` on a dirty template
        # records a hash that only ever existed inside Copier's throwaway
        # clone. `MergedTemplate` still accepts a ref so an explicit
        # author-loop opt-in can supply one; nothing does today.
        return MergedTemplate(
            str(template_path),
            dict(merged_questions),
            cfg or None,
            fallback_version=fallback_version,
        )

    @staticmethod
    @contextlib.contextmanager
    def _utf8_env() -> Generator[None, None, None]:
        """Temporarily forces UTF-8 to avoid encoding glitches in subprocess tasks."""
        prev_pyio = os.environ.get("PYTHONIOENCODING")

        # Only log when overriding non-UTF8 environment
        if prev_pyio and prev_pyio != "utf-8":
            _logger.debug("Overriding PYTHONIOENCODING: %s to utf-8", prev_pyio)

        os.environ["PYTHONIOENCODING"] = "utf-8"
        try:
            yield
        finally:
            if prev_pyio is None:
                with contextlib.suppress(KeyError):
                    del os.environ["PYTHONIOENCODING"]
            else:
                os.environ["PYTHONIOENCODING"] = prev_pyio

    def _render_with_worker(
        self,
        *,
        worker_opts: WorkerOptions,
        merged_template: CopierTemplate,
    ) -> dict[str, object]:
        """Run a Copier Worker with the provided merged template.

        Args:
            worker_opts: Keyword arguments for `copier.Worker`.
            merged_template: A `MergedTemplate` carrying questions/config.

        Returns:
            Answers dict combining `user` and `metadata` sections.
        """
        template_name = worker_opts.get("src_path", "unknown")
        destination = worker_opts.get("dst_path", "unknown")

        _logger.debug("Starting file generation: %s to %s", template_name, destination)

        try:
            # pyright: ignore — pydantic's @dataclass decorator erases
            # Worker's type to PydanticDataclass, hiding the constructor
            # signature and context-manager protocol that copier.Worker
            # correctly implements at runtime.
            with self._utf8_env(), Worker(**worker_opts) as worker:  # pyright: ignore[reportCallIssue, reportGeneralTypeIssues]
                # Inject the merged template so Worker uses our view (no disk mutation).
                # Priming the `template` cached_property bypasses the Worker
                # code that would otherwise register the template's cleanup,
                # so register it here: rendering a VCS template clones it into
                # a temp directory that only `_cleanup` removes.
                object.__setattr__(worker, "template", merged_template)
                worker._cleanup_hooks.append(  # pyright: ignore[reportPrivateUsage]
                    merged_template._cleanup  # pyright: ignore[reportPrivateUsage]
                )
                worker.run_copy()  # Critical operation that can fail silently
                user = dict(getattr(worker.answers, "user", {}) or {})
                metadata = dict(getattr(worker.answers, "metadata", {}) or {})
                user.update(metadata)
                return {str(k): v for k, v in user.items()}
        except CopierAnswersInterrupt as e:
            # Must precede the generic Exception handler -- CopierAnswersInterrupt
            # is also an Exception; see UserCancelledError for the payload-leak
            # rationale.
            _logger.debug("User cancelled interactive prompt for %s", template_name)
            raise UserCancelledError() from e
        except Exception as e:
            if self._is_interactive_prompt_failure(e):
                _logger.debug(
                    "Translating prompt_toolkit/questionary failure for %s",
                    template_name,
                )
                raise InteractiveRenderFailedError(
                    "Copier attempted to prompt but this environment does not "
                    "support interactive prompts. This typically happens in "
                    "Git Bash pseudo-TTYs, Windows CI runners without a console "
                    "buffer, Docker entrypoints without -it, or editor-embedded "
                    "shells."
                ) from e
            _logger.exception("File generation failed for %s: %s", template_name, e)
            raise  # Re-raise for CLI error handling

    @staticmethod
    def _is_interactive_prompt_failure(exc: BaseException) -> bool:
        """Return True if ``exc`` (or any cause/context) is a prompt-layer failure.

        Walks the ``__cause__`` / ``__context__`` chain looking for an
        exception whose type is defined in ``prompt_toolkit`` or
        ``questionary``, or Copier's own ``InteractiveSessionError`` (its
        wrapper for EOF during prompting, which carries a ``builtins``
        cause and would evade the module-prefix check). This catches the
        Windows ``NoConsoleScreenBufferError`` path as well as any other
        prompt-layer failure that bubbles up from ``Worker.run_copy()``.
        """
        seen: set[int] = set()
        cursor: BaseException | None = exc
        while cursor is not None and id(cursor) not in seen:
            seen.add(id(cursor))
            if isinstance(cursor, InteractiveSessionError):
                return True
            module = getattr(type(cursor), "__module__", "") or ""
            if module.startswith(("prompt_toolkit", "questionary")):
                return True
            cursor = cursor.__cause__ or cursor.__context__
        return False


__all__ = ["RenderEngine", "Template", "final_template_info"]
