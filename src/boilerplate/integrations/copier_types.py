"""Single, audited import point for the copier internals boilerplate depends on.

copier does not expose ``Template`` or ``Worker`` in its public API
(``copier.__all__`` is ``load_settings``, ``run_copy``, ``run_recopy``,
``run_update``, ``Phase``, ``Settings``, ``VcsRef``). boilerplate's
template-merging architecture is built on these internal classes: it subclasses
``Template`` to expose a consolidated question schema and drives ``Worker``
directly to render the merged result.

``load_template_config`` is the loader Copier itself applies to ``copier.yml``
(it understands the ``!include`` tag and multi-document files). ``boilerplate
validate`` reuses it so validation accepts exactly what Copier accepts, per the
delegation rule in docs/design/03-template-system.md (YAML Parsing Rules). It
loads configuration only; ``_tasks``/``_migrations`` entries are read as plain
data and never executed.

``load_answersfile_data`` is the reader Copier applies to a project's answers
file; reading recorded answers through it reads them the way Copier does.

``Question`` and ``AnswersMap`` are the classes ``Worker._ask`` builds for each
question; checking a recorded answer through them casts, narrows and validates
it the way Copier will.

``SandboxedEnvironment`` is the Jinja sandbox Copier renders with; ``Question``
accepts no other environment class, so a ``when`` judged outside a worker
renders through it.

``MISSING`` is the sentinel ``Question.get_default`` returns for a question with
no default; the answer walk of an update tells such a question by it. A test
pins it against ``get_default``.

``get_git`` is the git command Copier runs its own git calls through (with a
fixed commit identity); the staging worktree runs its git calls through it too.

``ProcessExecutionError`` is the error plumbum raises when the git command that
Copier runs exits non-zero. Plumbum arrives only through Copier, so the source
imports it from here rather than from plumbum directly.

``update_operation`` sets Copier's private ``_operation`` ContextVar to
``"update"`` for a block. Only ``run_copy``, ``run_recopy`` and ``run_update``
set it, and Copier's task runner reads it to give a task ``_copier_operation``;
the post-walk task run of an update calls the task runner outside those three, so
it sets the variable itself. ``TaskError`` is what the task runner raises when a
task exits non-zero.

``OLD_COPY_DIR_PREFIX`` and ``NEW_COPY_DIR_PREFIX`` are the name prefixes of the
temporary directories Copier's update renders its old copy and its new copy
into (``Worker._apply_update``); a destination below one of them identifies
which render of an update a worker is making. A test pins both against
Copier's source.

Importing them here, from the modules where copier actually defines them, keeps
that coupling localized to one place. When a copier upgrade relocates these
symbols, this module is the only thing that needs to change. The dependency is
pinned to a tested copier range in ``pyproject.toml`` for the same reason --
these are private symbols copier may move without a deprecation cycle.
"""

import dataclasses
import functools
from collections.abc import Generator
from contextlib import contextmanager

from copier._jinja_ext import SandboxedEnvironment
from copier._main import Worker, _operation  # pyright: ignore[reportPrivateUsage]
from copier._template import DEFAULT_EXCLUDE, Template, load_template_config
from copier._types import MISSING
from copier._user_data import AnswersMap, Question, load_answersfile_data
from copier._vcs import get_git
from copier.errors import TaskError
from packaging.version import Version
from plumbum.commands.processes import ProcessExecutionError

OLD_COPY_DIR_PREFIX = f"{Worker.__module__}.old_copy."
NEW_COPY_DIR_PREFIX = f"{Worker.__module__}.new_copy."


@functools.cache
def template_public_attr_names(cls: type[Template]) -> frozenset[str]:
    """Collect public, non-callable attribute names of a ``Template`` class.

    Inspects unevaluated descriptors: properties are property objects
    (non-callable, so included) while methods are plain functions
    (callable, so excluded). Dataclass fields are unioned in explicitly —
    a field with no class-level default (e.g. ``url``) never appears in
    ``dir(cls)``, only on instances. The result is a process constant per
    class, hence the cache.

    Args:
        cls: The ``Template`` class (or a subclass).

    Returns:
        Attribute names without a leading underscore that
        are dataclass fields or non-callable class attributes.

    Examples:
        Question data and init-only fields are included; methods are not:

        >>> "questions_data" in template_public_attr_names(Template)
        True
        >>> "url" in template_public_attr_names(Template)
        True
        >>> "migration_tasks" in template_public_attr_names(Template)
        False
    """
    names = {
        a for a in dir(cls) if not a.startswith("_") and not callable(getattr(cls, a))
    }
    names |= {f.name for f in dataclasses.fields(cls) if not f.name.startswith("_")}
    return frozenset(names)


def recorded_commit_version(src_path: str, commit: str) -> Version | None:
    """Read a recorded ``_commit`` as the version Copier reads it as.

    Copier records ``git describe --tags --always`` of the template in
    ``_commit``: a bare tag at a release, ``<tag>-<n>-g<hash>`` past one.
    ``Template.version`` turns that into a PEP 440 version, so a version read
    here compares the way Copier's own update compares them. Reading it checks
    the commit out of the template's repository, which clones it.

    Args:
        src_path: The template source the answers file records in ``_src_path``.
        commit: The answers file's ``_commit`` value.

    Returns:
        The version, or ``None`` when the source is not a git repository or the
        commit reads as no version.

    Raises:
        plumbum.commands.processes.ProcessExecutionError: If the source cannot
            check the commit out, as when its history was rewritten.
    """
    template = Template(url=src_path, ref=commit)
    try:
        return template.version
    finally:
        template._cleanup()  # pyright: ignore[reportPrivateUsage]


@contextmanager
def update_operation() -> Generator[None]:
    """Run a block under Copier's ``update`` operation.

    Inside the block Copier's task runner gives each task
    ``_copier_operation == "update"``, as it does during ``run_update``, so a
    template may guard a creation-only task. The variable is restored on the
    way out, also when the block raises.

    Yields:
        Nothing; the operation is set for the duration of the block.
    """
    token = _operation.set("update")
    try:
        yield
    finally:
        _operation.reset(token)


__all__ = [
    "DEFAULT_EXCLUDE",
    "MISSING",
    "NEW_COPY_DIR_PREFIX",
    "OLD_COPY_DIR_PREFIX",
    "AnswersMap",
    "ProcessExecutionError",
    "Question",
    "SandboxedEnvironment",
    "TaskError",
    "Template",
    "Worker",
    "get_git",
    "load_answersfile_data",
    "load_template_config",
    "recorded_commit_version",
    "template_public_attr_names",
    "update_operation",
]
