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

Importing them here, from the modules where copier actually defines them, keeps
that coupling localized to one place. When a copier upgrade relocates these
symbols, this module is the only thing that needs to change. The dependency is
pinned to a tested copier range in ``pyproject.toml`` for the same reason --
these are private symbols copier may move without a deprecation cycle.
"""

import dataclasses
import functools

from copier._main import Worker
from copier._template import DEFAULT_EXCLUDE, Template, load_template_config
from copier._user_data import load_answersfile_data


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


__all__ = [
    "DEFAULT_EXCLUDE",
    "Template",
    "Worker",
    "load_answersfile_data",
    "load_template_config",
    "template_public_attr_names",
]
