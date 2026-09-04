"""Guard tests for the copier-internals import shim.

The module-level import below is itself the primary guard: if a copier upgrade
relocates the private ``Template`` or ``Worker`` symbols the shim re-exports,
collection fails loudly here during CI rather than at render time for a user.
"""

from __future__ import annotations

import inspect

from boilerplate.integrations.copier_types import (
    Template,
    Worker,
    template_public_attr_names,
)


class TestCopierTypesShim:
    """The shim re-exports the copier internals boilerplate depends on."""

    def test_template_is_a_class(self) -> None:
        assert inspect.isclass(Template)

    def test_worker_is_a_class(self) -> None:
        assert inspect.isclass(Worker)

    def test_symbols_originate_from_copier(self) -> None:
        assert Template.__module__.startswith("copier")
        assert Worker.__module__.startswith("copier")

    def test_template_public_attr_names_reflects_public_fields(self) -> None:
        names = template_public_attr_names(Template)
        assert "questions_data" in names
        assert "migration_tasks" not in names  # method: callable, excluded
        assert not any(n.startswith("_") for n in names)

    def test_init_only_dataclass_fields_included(self) -> None:
        # Regression: fields with no class-level default (e.g. ``url``) are
        # invisible to dir(cls) and were silently dropped from extracted
        # configs and the merger's layer-local set.
        assert "url" in template_public_attr_names(Template)
