"""Run one Copier ``Worker`` against a merged template, one place for its guards.

A render and the questionnaire pass before it both drive a ``Worker`` the same
way: UTF-8 subprocess output, the ancestors' extension files loaded, the merged
template primed in place of the one Copier would read, and Copier's prompt
failures turned into Boilerplate's own errors.
"""
# Spec: docs/design/04-composition-engine.md §Copier Worker Interface

import contextlib
import os
from collections.abc import Generator
from logging import getLogger

from copier.errors import CopierAnswersInterrupt, InteractiveSessionError

from boilerplate.common.exceptions import (
    InteractiveRenderFailedError,
    UserCancelledError,
)
from boilerplate.composition.rendering.worker_options import WorkerOptions
from boilerplate.composition.views import LayerView, registered_ancestor_extensions
from boilerplate.integrations.copier_types import Template, Worker

_logger = getLogger(__name__)


@contextlib.contextmanager
def _utf8_env() -> Generator[None]:
    """Force UTF-8 for the block, to avoid encoding glitches in subprocess tasks."""
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


@contextlib.contextmanager
def worker_session(
    options: WorkerOptions, template: Template, view: LayerView
) -> Generator[Worker]:
    """Open a Copier Worker that reads `template` and renders under `view`.

    Args:
        options: Keyword arguments for `copier.Worker`.
        template: A `MergedTemplate` carrying the view's questions and config.
        view: The view the Worker renders under; its ancestors' extension files
            are importable for the block.

    Yields:
        The Worker, entered, with `template` in place of the one it would read
        and its cleanup registered.

    Raises:
        UserCancelledError: If the user cancels a prompt.
        InteractiveRenderFailedError: If the environment cannot host the prompt.
    """
    source = options.get("src_path", "unknown")
    destination = options.get("dst_path", "unknown")
    _logger.debug("Starting file generation: %s to %s", source, destination)
    try:
        # pyright: ignore — pydantic's @dataclass decorator erases
        # Worker's type to PydanticDataclass, hiding the constructor
        # signature and context-manager protocol that copier.Worker
        # correctly implements at runtime.
        with (
            _utf8_env(),
            registered_ancestor_extensions(view.ancestor_extensions),
            Worker(**options) as worker,  # pyright: ignore[reportCallIssue, reportGeneralTypeIssues]
        ):
            # Inject the merged template so Worker uses our view (no disk mutation).
            # Priming the `template` cached_property bypasses the Worker
            # code that would otherwise register the template's cleanup,
            # so register it here: rendering a VCS template clones it into
            # a temp directory that only `_cleanup` removes.
            object.__setattr__(worker, "template", template)
            worker._cleanup_hooks.append(template._cleanup)  # pyright: ignore[reportPrivateUsage]
            yield worker
    except CopierAnswersInterrupt as e:
        # Must precede the generic Exception handler -- CopierAnswersInterrupt
        # is also an Exception; see UserCancelledError for the payload-leak
        # rationale.
        _logger.debug("User cancelled interactive prompt for %s", source)
        raise UserCancelledError() from e
    except Exception as e:
        if _is_interactive_prompt_failure(e):
            _logger.debug(
                "Translating prompt_toolkit/questionary failure for %s", source
            )
            raise InteractiveRenderFailedError(
                "Copier attempted to prompt but this environment does not "
                "support interactive prompts. This typically happens in "
                "Git Bash pseudo-TTYs, Windows CI runners without a console "
                "buffer, Docker entrypoints without -it, or editor-embedded "
                "shells."
            ) from e
        _logger.exception("File generation failed for %s: %s", source, e)
        raise  # Re-raise for CLI error handling


__all__ = ["worker_session"]
