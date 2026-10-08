"""Run one ``ScopedWorker``, one place for the guards a compose adds around it.

A render and the questionnaire pass before it both drive the Worker subclass an
update uses: UTF-8 subprocess output, the ancestors' extension files loaded, and
Copier's prompt failures turned into Boilerplate's own errors.
"""
# Spec: docs/design/04-composition-engine.md §Copier Worker Interface

import contextlib
import os
from collections.abc import Generator, Sequence
from logging import getLogger

from copier.errors import CopierAnswersInterrupt, InteractiveSessionError

from boilerplate.common.exceptions import (
    InteractiveRenderFailedError,
    UserCancelledError,
)
from boilerplate.composition.models.json_types import JSON
from boilerplate.composition.rendering.scoped_worker import ScopedWorker
from boilerplate.composition.rendering.worker_options import WorkerOptions
from boilerplate.composition.views import LayerView, registered_ancestor_extensions

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
    options: WorkerOptions,
    view: LayerView,
    *,
    tasks: Sequence[JSON] = (),
    fallback_version: str | None = None,
) -> Generator[ScopedWorker]:
    """Open a ``ScopedWorker`` that renders under `view`, as a compose does.

    The Worker renders one view for every copy, and a forced render clears the
    template's own ``_skip_if_exists``. A compose supplies every answer as data,
    so the Worker checks no recorded answer; only an update's own Worker does.

    Args:
        options: Keyword arguments for `copier.Worker`.
        view: The view the Worker renders under; its ancestors' extension files
            are importable for the block.
        tasks: The tasks the Worker runs after rendering, in Copier's shapes.
        fallback_version: The layer's ``boilerplate.yml`` version, reported as
            the template version when the layer is not a git repository.

    Yields:
        The Worker, entered.

    Raises:
        UserCancelledError: If the user cancels a prompt.
        InteractiveRenderFailedError: If the environment cannot host the prompt.
    """
    source = options.get("src_path", "unknown")
    destination = options.get("dst_path", "unknown")
    _logger.debug("Starting file generation: %s to %s", source, destination)
    try:
        with (
            _utf8_env(),
            registered_ancestor_extensions(view.ancestor_extensions),
            # pydantic's @dataclass decorator erases the Worker's type, hiding
            # the constructor signature that it implements at runtime.
            ScopedWorker(  # pyright: ignore[reportCallIssue]
                **options,
                target_view=view,
                tasks=tuple(tasks),
                honor_skip_if_exists=False,
                check_recorded=False,
                fallback_version=fallback_version,
            ) as worker,
        ):
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
