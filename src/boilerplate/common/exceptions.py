"""Canonical exceptions for the Boilerplate ecosystem.

This module defines the package-wide exception hierarchy. Import exceptions
from this module to ensure consistent behavior across the codebase and tests.
"""
# Spec: docs/design/02-data-models.md §Error Hierarchy

from collections.abc import Mapping, Sequence


class BoilerplateError(Exception):
    """Base error for the Boilerplate ecosystem.

    Every concrete subclass carries a stable ``BP_{PHASE}_{DESCRIPTOR}`` code
    registered in docs/design/07-operational-quality.md §Error Code Registry,
    plus that registry's severity and retryable metadata.

    Attributes:
        severity: Registry severity classification for this error.
        retryable: Whether the failed operation may be retried, per
            docs/design/07-operational-quality.md §Retry Policy. Validation,
            not-found, and conflict errors are never retryable.

    Args:
        message: Human-readable error description.
        error_code: Machine-readable error code
            (e.g. "BP_RESOLVE_TEMPLATE_NOT_FOUND").
        remediation: Suggested fix for the user.
    """

    severity: str = "error"
    retryable: bool = False

    def __init__(
        self,
        message: str = "",
        *,
        error_code: str | None = None,
        remediation: str | None = None,
    ) -> None:
        """Initialize with optional error code and remediation."""
        super().__init__(message)
        self.error_code = error_code
        self.remediation = remediation


class ActionRequiredError(BoilerplateError):
    """Base for recoverable workflow pauses that require user intervention.

    Routed to exit code 4 (ACTION_REQUIRED) by the CLI error boundary, per
    docs/design/02-data-models.md §Exit Codes: the operation cannot complete
    until the user acts (e.g. resolving update merge conflicts and running the
    update again), which is distinct from a hard failure (exit 1).
    Concrete pause conditions subclass this with their own error code.
    """


class DirectoryValidationError(BoilerplateError):
    """Raised when a directory path fails validation (missing, not a dir, etc.)."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_CONFIG_DIR_INVALID."""
        super().__init__(message, error_code="BP_CONFIG_DIR_INVALID", **kwargs)


class TemplateNotFoundError(BoilerplateError):
    """Raised when a requested template cannot be located in any catalog path."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_RESOLVE_TEMPLATE_NOT_FOUND."""
        super().__init__(
            message,
            error_code="BP_RESOLVE_TEMPLATE_NOT_FOUND",
            remediation=kwargs.pop(
                "remediation",
                "Run 'boilerplate list' to see available templates.",
            ),
            **kwargs,
        )


class InvalidVersionError(BoilerplateError):
    """Raised when a provided version string is not PEP 440 compliant."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_VERSION_INVALID."""
        super().__init__(message, error_code="BP_VERSION_INVALID", **kwargs)


class DestinationNotEmptyError(BoilerplateError):
    """Raised when the destination directory exists and is not empty without force."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_RENDER_DEST_NOT_EMPTY."""
        super().__init__(
            message,
            error_code="BP_RENDER_DEST_NOT_EMPTY",
            remediation=kwargs.pop("remediation", "Use --force to overwrite."),
            **kwargs,
        )


class NonInteractiveRequiresForceError(BoilerplateError):
    """Raised when a multi-layer render in non-interactive mode requires --force."""

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_FORCE_REQUIRED."""
        super().__init__(
            message,
            error_code="BP_INPUT_FORCE_REQUIRED",
            remediation=kwargs.pop("remediation", "Add --force to proceed."),
            **kwargs,
        )


class InvalidTemplateSpecifierError(BoilerplateError):
    """Raised when a template specifier (name@version) fails validation.

    This includes invalid template names, malformed specifier strings, or
    unsupported value types when converting to a TemplateSpecifier.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_SPECIFIER_INVALID."""
        super().__init__(
            message,
            error_code="BP_INPUT_SPECIFIER_INVALID",
            remediation=kwargs.pop("remediation", "Use format: name or name@version."),
            **kwargs,
        )


class MetadataValidationError(BoilerplateError):
    """Raised when template metadata is invalid or inconsistent.

    For example, an invalid ``boilerplate.yml``.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_RESOLVE_METADATA_INVALID."""
        super().__init__(message, error_code="BP_RESOLVE_METADATA_INVALID", **kwargs)


class MissingRequiredAnswersError(BoilerplateError):
    """Raised when required answers are missing for non-interactive render.

    Emitted before Copier is invoked. A question is "required" when it has
    no ``default`` and no ``when: false``; in interactive mode Copier would
    prompt, but in ``--ci`` / ``--non-interactive`` mode there is no one to
    answer, so the render must fail fast with a clear enumeration of the
    unanswered fields.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_ANSWERS_MISSING."""
        super().__init__(
            message,
            error_code="BP_INPUT_ANSWERS_MISSING",
            remediation=kwargs.pop(
                "remediation",
                "Supply the missing values with --data key=value or "
                "--data-file <path> (a YAML mapping), add defaults for these "
                "questions in the template's copier.yml, or run without "
                "--ci / --non-interactive to prompt interactively.",
            ),
            **kwargs,
        )


class InvalidDataError(BoilerplateError):
    """Raised when ``--data`` or ``--data-file`` input cannot be parsed.

    Emitted before Copier is invoked, covering the parse failures ahead of
    any render attempt: a ``--data`` entry with no ``=`` separator, a
    ``--data-file`` path that cannot be read (including as UTF-8) or whose
    YAML is malformed, data-file content that is not a YAML mapping, and a
    key (from either source) that is empty, starts with an underscore
    (Copier's reserved-directive namespace), or — for ``--data-file`` — is
    not a string.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_DATA_INVALID."""
        super().__init__(
            message,
            error_code="BP_INPUT_DATA_INVALID",
            remediation=kwargs.pop(
                "remediation",
                "Use --data key=value (repeatable) for individual answers, "
                "or --data-file <path> for a UTF-8 YAML mapping of question "
                "name to answer.",
            ),
            **kwargs,
        )


class RecordedAnswerRejectedError(BoilerplateError):
    """Raised when a layer's update step finds a recorded answer its target rejects.

    The check runs inside the layer's step, after the layer's migrations and
    Copier's re-read of the answers file, so a migration that repairs a
    recorded answer clears it first. The target view's question rejects the
    answer by type, choices or validator; Copier would otherwise drop it and
    record the new default without a word.

    Attributes:
        layer: The layer whose answers file records the answer.
        question: The question the answer is for.
        value: The recorded answer.
        reason: Why the target view's question rejects it.
    """

    def __init__(
        self,
        message: str = "",
        *,
        layer: str = "",
        question: str = "",
        value: object = None,
        reason: str = "",
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_INPUT_ANSWER_REJECTED."""
        super().__init__(
            message,
            error_code="BP_INPUT_ANSWER_REJECTED",
            remediation=kwargs.pop(
                "remediation",
                f"Pass a valid value with --set {question or '<question>'}=<value>.",
            ),
            **kwargs,
        )
        self.layer = layer
        self.question = question
        self.value = value
        self.reason = reason


class InteractiveModeRequiresTtyError(BoilerplateError):
    """Raised when an interactive render is requested but stdin is not a TTY.

    Raised by the ``new`` command's pre-flight, before its Copier
    invocation. Without this pre-flight, Copier's
    prompt layer (questionary/prompt_toolkit) can retry-loop on EOF instead
    of raising, growing memory without bound in environments that can never
    answer a prompt (CI pipelines, piped input, sessions without a console).
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_TTY_REQUIRED."""
        super().__init__(
            message,
            error_code="BP_INPUT_TTY_REQUIRED",
            remediation=kwargs.pop(
                "remediation",
                "Pass --non-interactive to render with defaults "
                "(or use the global flag: boilerplate --ci new ...), or "
                "run from an interactive terminal; --data/--data-file "
                "answers are preserved and used under --non-interactive.",
            ),
            **kwargs,
        )


class DestinationRequiredError(BoilerplateError):
    """Raised when a non-interactive render names no destination.

    Raised by the ``new`` command before its Copier invocation. With no
    prompt to ask, the only fallback would be the current directory, and a
    render into whatever directory a pipeline happens to run in is the
    outcome docs/design/05-cli-reference.md (Destination behavior) rules out.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_INPUT_DEST_REQUIRED."""
        super().__init__(
            message,
            error_code="BP_INPUT_DEST_REQUIRED",
            remediation=kwargs.pop(
                "remediation",
                "Pass the destination directory as the second argument: "
                "boilerplate new <template> <destination>.",
            ),
            **kwargs,
        )


class InteractiveRenderFailedError(BoilerplateError):
    """Raised when Copier's prompt machinery failed because prompting is impossible.

    Emitted as a translation of prompt_toolkit / questionary failures during
    rendering (e.g., Windows ``NoConsoleScreenBufferError`` under a Git Bash
    pseudo-TTY). The underlying cause is a terminal that cannot host
    prompt_toolkit's output backend; the user's options are to switch to a
    real terminal or supply the missing answers up front.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_RENDER_PROMPT_FAILED."""
        super().__init__(
            message,
            error_code="BP_RENDER_PROMPT_FAILED",
            remediation=kwargs.pop(
                "remediation",
                "Re-run with --ci (implies --non-interactive) "
                "from a shell where all required answers have defaults, or use "
                "a terminal that supports interactive prompts (e.g., PowerShell "
                "on Windows, a real tty on Unix).",
            ),
            **kwargs,
        )


class UserCancelledError(BoilerplateError):
    """Raised when the user cancels an interactive render (e.g. Ctrl+C at a prompt).

    Translated from Copier's ``CopierAnswersInterrupt``, which subclasses both
    ``CopierError`` and ``KeyboardInterrupt`` and carries the full
    ``(AnswersMap, Question, Template)`` tuple as its args; stringifying it
    directly would leak collected answers and absolute template paths to the
    terminal. Never retryable: retrying would override the user's explicit
    choice to stop.
    """

    def __init__(self, message: str = "Aborted.", **kwargs: str | None) -> None:
        """Initialize with default error code BP_RENDER_USER_CANCELLED."""
        super().__init__(message, error_code="BP_RENDER_USER_CANCELLED", **kwargs)


class LockReadFailedError(BoilerplateError):
    """Raised when ``boilerplate.lock`` cannot be read as a lock file.

    Covers unparseable YAML, a truncated file and a body that does not match the
    lock schema. Boilerplate never repairs the file, because it records
    provenance the project alone cannot reconstruct.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_LOCK_READ_FAILED."""
        super().__init__(
            message,
            error_code="BP_LOCK_READ_FAILED",
            remediation=kwargs.pop(
                "remediation",
                "Lock file is corrupted. To recreate: delete boilerplate.lock and "
                "run 'boilerplate new <template> . --force' to regenerate from "
                "the current project state.",
            ),
            **kwargs,
        )


class LockSchemaUnsupportedError(BoilerplateError):
    """Raised when a lock file's schema major is newer than this tool supports.

    The tool fails closed: it neither reads nor mutates a lock written by a
    newer generation of Boilerplate.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_LOCK_SCHEMA_UNSUPPORTED."""
        super().__init__(
            message,
            error_code="BP_LOCK_SCHEMA_UNSUPPORTED",
            remediation=kwargs.pop(
                "remediation",
                "This project was created with a newer version of Boilerplate. "
                "Please upgrade.",
            ),
            **kwargs,
        )


_SET_ASIDE_REMEDIATION = (
    "Run 'git stash --include-untracked' to set the partial update aside, "
    "then run 'boilerplate update' again."
)

RESET_THEN_STASH = "'git reset' and then 'git stash --include-untracked'"
"""The commands that set a partial run aside, as every remediation words them.

A paused run leaves its conflicted files as unmerged index entries, which
``git stash`` refuses; ``git reset`` returns the index to HEAD and keeps the
working tree, so it comes first.
"""

_RESET_AND_SET_ASIDE_REMEDIATION = (
    f"Run {RESET_THEN_STASH} to set the partial update aside, then run "
    "'boilerplate update' again."
)


class AnswersFileIncompleteError(BoilerplateError):
    """Raised when no answers file records keys a layer's scoped view asks for.

    A hand-run vanilla update of a child layer leaves its answers file with only
    the layer's own keys, and the walk fills the rest for the old copy from the
    declaring layers' files. A key neither the layer's own file nor its
    declaring layer's records has no answer to fill. The check runs before any
    layer does.

    Attributes:
        missing: The question keys neither the layer's own answers file nor
            its declaring layer's records, keyed by layer name.
    """

    def __init__(
        self,
        message: str = "",
        *,
        missing: Mapping[str, Sequence[str]] | None = None,
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_UPDATE_ANSWERS_INCOMPLETE."""
        super().__init__(
            message,
            error_code="BP_UPDATE_ANSWERS_INCOMPLETE",
            remediation=kwargs.pop(
                "remediation",
                "Undo the hand-run update that trimmed the answers file with "
                "'git revert' of the commit that holds it, then run "
                "'boilerplate update' again.",
            ),
            **kwargs,
        )
        self.missing: Mapping[str, tuple[str, ...]] = {
            layer: tuple(keys) for layer, keys in (missing or {}).items()
        }


class UpdateLayerDriftError(BoilerplateError):
    """Raised when a layer and one of its ancestors both disagree with the lock.

    As after a hand-run update of each, the walk cannot tell which versions the
    layer's files were last rendered against, so it stops before any layer
    runs.

    Attributes:
        layers: The disagreeing layers the stop names.
    """

    def __init__(
        self,
        message: str = "",
        *,
        layers: Sequence[str] = (),
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_UPDATE_LAYER_DRIFT."""
        super().__init__(
            message,
            error_code="BP_UPDATE_LAYER_DRIFT",
            remediation=kwargs.pop("remediation", _SET_ASIDE_REMEDIATION),
            **kwargs,
        )
        self.layers = tuple(layers)


class UpdateTargetMismatchError(BoilerplateError):
    """Raised when an explicit target differs from a paused update's targets.

    Attributes:
        layers: The layers whose requested target differs from the recorded one.
    """

    def __init__(
        self,
        message: str = "",
        *,
        layers: Sequence[str] = (),
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_UPDATE_TARGET_MISMATCH."""
        super().__init__(
            message,
            error_code="BP_UPDATE_TARGET_MISMATCH",
            remediation=kwargs.pop("remediation", _RESET_AND_SET_ASIDE_REMEDIATION),
            **kwargs,
        )
        self.layers = tuple(layers)


class UpdateDowngradeError(BoilerplateError):
    """Raised when an update would move a layer to an older version.

    Also raised when a layer's recorded ``_commit`` yields no version, so no
    comparison can show the target is not older. There is no override: the way
    back from an applied update is reverting the commit that recorded it.

    Attributes:
        layer: The layer whose target is older, or whose version is unknown.
        recorded: The version the layer's answers file records, or an empty
            string when none could be read.
        target: The version the update would move the layer to.
    """

    def __init__(
        self,
        message: str = "",
        *,
        layer: str = "",
        recorded: str = "",
        target: str = "",
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_UPDATE_DOWNGRADE_REJECTED."""
        super().__init__(
            message,
            error_code="BP_UPDATE_DOWNGRADE_REJECTED",
            remediation=kwargs.pop(
                "remediation",
                "Revert the commit that recorded the update to go back to an "
                "earlier version.",
            ),
            **kwargs,
        )
        self.layer = layer
        self.recorded = recorded
        self.target = target


class UpdateProjectNotReadyError(BoilerplateError):
    """Raised when the project cannot be staged: not a repository, or a dirty tree.

    Copier refuses to update a project whose ``git status --porcelain`` is not
    empty, untracked files included, and the staging worktree is a worktree of
    the project's repository.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_UPDATE_PROJECT_NOT_READY."""
        super().__init__(message, error_code="BP_UPDATE_PROJECT_NOT_READY", **kwargs)


class UpdateSubmodulesUnsupportedError(BoilerplateError):
    """Raised when the project has submodules, so no staging worktree is made.

    Git's worktree documentation says multiple checkouts of a superproject are
    not recommended.

    Attributes:
        paths: The submodule paths ``.gitmodules`` declares.
    """

    def __init__(
        self,
        message: str = "",
        *,
        paths: Sequence[str] = (),
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_UPDATE_SUBMODULES_UNSUPPORTED."""
        super().__init__(
            message, error_code="BP_UPDATE_SUBMODULES_UNSUPPORTED", **kwargs
        )
        self.paths = tuple(paths)


class UpdateCheckoutChangedError(BoilerplateError):
    """Raised when the user's checkout changed while the staging worktree lived.

    Copying back would overwrite the user's work, so the worktree is discarded
    and nothing is written.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_UPDATE_CHECKOUT_CHANGED."""
        super().__init__(message, error_code="BP_UPDATE_CHECKOUT_CHANGED", **kwargs)


class UpdatePathObstructedError(BoilerplateError):
    """Raised when a path the walk added already exists in the user's checkout.

    The checkout is at the starting commit with no changes, so a path that
    exists where the walk added one is a file or directory git ignores. Copying
    back would overwrite that file or delete that directory without warning, so
    nothing is written.

    Attributes:
        paths: Every obstructed path, relative to the checkout.
    """

    def __init__(
        self,
        message: str = "",
        *,
        paths: Sequence[str] = (),
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_UPDATE_PATH_OBSTRUCTED."""
        super().__init__(message, error_code="BP_UPDATE_PATH_OBSTRUCTED", **kwargs)
        self.paths = tuple(paths)


class ConcurrencyContentionError(BoilerplateError):
    """Raised when another Boilerplate process holds the project's operation lock.

    Boilerplate does not run two mutating operations on one project at once.
    The lock wait timed out, so the other operation may still be running; once
    it finishes the same command can be run again.

    Attributes:
        retryable: True; the contention clears when the other operation ends.
    """

    retryable = True

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_CONCURRENCY_CONTENTION."""
        super().__init__(message, error_code="BP_CONCURRENCY_CONTENTION", **kwargs)


class UpdateCopyBackFailedError(BoilerplateError):
    """Raised when copying the staging worktree back into the checkout failed partway.

    The checkout was restored to the starting commit, and the staging worktree
    is kept so the walk's result is not lost. When that restore failed too,
    the message says the checkout could not be restored and names both
    failures, and the restore marker stays for the rerun.

    Attributes:
        staging_path: The kept staging worktree, which holds the walk's result.
    """

    def __init__(
        self,
        message: str = "",
        *,
        staging_path: str = "",
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_UPDATE_COPY_BACK_FAILED."""
        super().__init__(message, error_code="BP_UPDATE_COPY_BACK_FAILED", **kwargs)
        self.staging_path = staging_path


class UpdateInterruptedError(BoilerplateError):
    """Raised when a restore marker shows a cut-off run this one cannot finish.

    An earlier update or add was cut off while it restored its result into the
    working tree or finished afterwards: its changes may sit uncommitted in the
    checkout. Each stop words its own remediation, built from
    ``RESET_THEN_STASH`` or naming the command to rerun.

    Attributes:
        targets: Each layer's target version the interrupted run was moving to.
    """

    def __init__(
        self,
        message: str = "",
        *,
        targets: Mapping[str, str] | None = None,
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_UPDATE_INTERRUPTED."""
        super().__init__(message, error_code="BP_UPDATE_INTERRUPTED", **kwargs)
        self.targets = dict(targets or {})


class UpdateTaskFailedError(BoilerplateError):
    """Raised when a task fails after the update's files were copied back.

    The update keeps the files and writes the lock before it raises, so the
    project is updated except for the task, which the user runs by hand.

    Attributes:
        task: The task's command, as Copier ran it.
    """

    def __init__(
        self, message: str = "", *, task: str = "", **kwargs: str | None
    ) -> None:
        """Initialize with default error code BP_UPDATE_TASK_FAILED."""
        super().__init__(message, error_code="BP_UPDATE_TASK_FAILED", **kwargs)
        self.task = task


class UpdateConflictPausedError(ActionRequiredError):
    """Raised when a layer's update left merge conflicts and the walk paused.

    The layers finished so far are in the working tree with Copier's conflict
    markers and no lock is written. The user resolves the conflicts and commits,
    then runs the update again, which resumes from the pause.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_UPDATE_CONFLICT_PAUSED."""
        super().__init__(message, error_code="BP_UPDATE_CONFLICT_PAUSED", **kwargs)


class UpdateUnknownLayerError(BoilerplateError):
    """Raised when an update names a layer the project does not have.

    Attributes:
        layers: The named layers the project's lock does not list.
    """

    def __init__(
        self,
        message: str = "",
        *,
        layers: Sequence[str] = (),
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_UPDATE_LAYER_UNKNOWN."""
        super().__init__(message, error_code="BP_UPDATE_LAYER_UNKNOWN", **kwargs)
        self.layers = tuple(layers)


def _add_first_remediation(layers: Sequence[str]) -> str:
    """Return the remediation that adds each of `layers` before the layer."""
    commands = " and ".join(f"'boilerplate add {layer}'" for layer in layers)
    return f"Run {commands or "'boilerplate add <ancestor>'"} first."


class ProjectNotManagedError(BoilerplateError):
    """Raised when ``add`` finds no ``boilerplate.lock`` in the project.

    The message carries its own advice, so no default remediation repeats it.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_UPDATE_PROJECT_NOT_MANAGED."""
        super().__init__(message, error_code="BP_UPDATE_PROJECT_NOT_MANAGED", **kwargs)


class LayerAlreadyAddedError(BoilerplateError):
    """Raised when ``add`` names a template the project's lock already lists.

    The message carries its own advice, so no default remediation repeats it.
    """

    def __init__(self, message: str = "", **kwargs: str | None) -> None:
        """Initialize with default error code BP_UPDATE_LAYER_ALREADY_ADDED."""
        super().__init__(message, error_code="BP_UPDATE_LAYER_ALREADY_ADDED", **kwargs)


class AddAncestorsMissingError(BoilerplateError):
    """Raised when a layer being added extends layers the project lacks.

    Attributes:
        layers: The missing layers, each one a layer the new layer extends,
            directly or through another layer.
    """

    def __init__(
        self,
        message: str = "",
        *,
        layers: Sequence[str] = (),
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_UPDATE_ANCESTORS_MISSING."""
        super().__init__(
            message,
            error_code="BP_UPDATE_ANCESTORS_MISSING",
            remediation=kwargs.pop("remediation", _add_first_remediation(layers)),
            **kwargs,
        )
        self.layers = tuple(layers)


class AddAncestorVersionError(BoilerplateError):
    """Raised when an ancestor's recorded version fails the new layer's ``extends``.

    Attributes:
        ancestor: The ancestor whose recorded version fails the constraint.
        recorded: The version the lock records for the ancestor.
        constraint: The ``extends`` reference the new layer declares.
    """

    def __init__(
        self,
        message: str = "",
        *,
        ancestor: str = "",
        recorded: str = "",
        constraint: str = "",
        **kwargs: str | None,
    ) -> None:
        """Initialize with default error code BP_UPDATE_ANCESTOR_VERSION_MISMATCH."""
        super().__init__(
            message,
            error_code="BP_UPDATE_ANCESTOR_VERSION_MISMATCH",
            remediation=kwargs.pop("remediation", "Run 'boilerplate update' first."),
            **kwargs,
        )
        self.ancestor = ancestor
        self.recorded = recorded
        self.constraint = constraint
