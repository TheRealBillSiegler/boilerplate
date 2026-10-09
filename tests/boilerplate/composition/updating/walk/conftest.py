"""Parts the walk's models are built from."""

from datetime import UTC, datetime

import pytest

from boilerplate.composition.updating.layer_release import LayerRelease
from boilerplate.composition.updating.update_views import UpdateViews
from boilerplate.composition.views import LayerView
from boilerplate.models import BoilerplateLock, JoinedVia, LockLayer
from boilerplate.types import SerializableVersion

STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


@pytest.fixture
def two_layer_lock() -> BoilerplateLock:
    """Return a lock whose layers are ``core`` and then ``app``."""
    return BoilerplateLock(
        boilerplate_version="0.3.0",
        copier_version="9.18.1",
        created_at=STAMP,
        updated_at=STAMP,
        root_template="app@1.0.0",
        layers=tuple(
            LockLayer(
                name=name,
                version=SerializableVersion("1.0.0"),
                source="x",
                checksum="sha256:" + "a" * 64,
            )
            for name in ("core", "app")
        ),
    )


@pytest.fixture
def core_release() -> LayerRelease:
    """Return the release ``core`` is updated to."""
    return LayerRelease(layer="core", source="https://example.com/core.git", ref="v2")


@pytest.fixture
def empty_views() -> UpdateViews:
    """Return the old and target views of a layer that asks nothing."""
    view = LayerView(questions={}, extensions=())
    return UpdateViews(old=view, target=view, needs_unsafe=False)


@pytest.fixture
def added_layer_lock() -> BoilerplateLock:
    """Return a lock of ``core`` and ``app`` to which ``docs`` was then added."""
    return BoilerplateLock(
        boilerplate_version="0.3.0",
        copier_version="9.18.1",
        created_at=STAMP,
        updated_at=STAMP,
        root_template="app@1.0.0",
        layers=tuple(
            LockLayer(
                name=name,
                version=SerializableVersion("1.0.0"),
                joined_via=joined_via,
                source="x",
                checksum="sha256:" + "a" * 64,
            )
            for name, joined_via in (
                ("core", JoinedVia.EXTENDS),
                ("app", JoinedVia.EXTENDS),
                ("docs", JoinedVia.ADD),
            )
        ),
    )
