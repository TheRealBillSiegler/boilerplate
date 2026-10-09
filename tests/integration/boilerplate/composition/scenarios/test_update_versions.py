"""The pre-walk version rules on real tags: resume, drift, downgrades and old copies.

The rules are pure functions over parsed versions; these scenarios feed them
versions read from a composed project of the made-up family, through the real
answers files, the real repositories' tags and a real lock file. The project is
`app` over `service`, `docs` and `core`, walked in the lock's order: core,
service, docs, app.
"""

import dataclasses
import shutil
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest
import yaml

from boilerplate.common.exceptions import (
    AnswersFileIncompleteError,
    UpdateDowngradeError,
    UpdateLayerDriftError,
    UpdateTargetMismatchError,
)
from boilerplate.composition.updating import (
    check_answers_complete,
    read_recorded_answers_by_layer,
)
from boilerplate.composition.updating.versions import (
    LayerVersions,
    VersionResolution,
    plan_resume,
    read_layer_versions,
    resolve_versions,
)
from boilerplate.composition.views import LayerView
from boilerplate.models import (
    BoilerplateLock,
    ChangeClassification,
    LockLayer,
    MigrationRecord,
    MigrationStatus,
)
from boilerplate.project_state.lock_file import read_lock, write_lock
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from boilerplate.types import SerializableVersion
from tests.boilerplate.templates.conftest import (
    commit_all,
    compose,
    git,
    layer_view,
    rehome_layer,
)
from tests.integration.boilerplate.composition.family import Family
from tests.integration.boilerplate.composition.scenarios.builders import (
    compose_family,
    templates_at,
    update_family_layer,
)
from tests.integration.boilerplate.composition.temp_dir import temp_dir_inside

BASE = {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}
PAUSED = {**BASE, "core": "2.0.0", "app": "1.1.0"}
STAMP = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def v(version: str) -> SerializableVersion:
    """Return `version` as a PEP 440 version."""
    return SerializableVersion(version)


def targets(tags: Mapping[str, str]) -> dict[str, SerializableVersion]:
    """Return `tags` as the planned target of every layer."""
    return {layer: v(tag) for layer, tag in tags.items()}


def conflict_record(tags: Mapping[str, str], finished: list[str]) -> MigrationRecord:
    """Return the conflict record of a walk to `tags` paused after `finished`."""
    return MigrationRecord(
        id="2",
        from_version="app@1.0.0",
        to_version=f"app@{tags['app']}",
        timestamp=STAMP,
        status=MigrationStatus.CONFLICT,
        classification=ChangeClassification.MAJOR,
        targets=dict(tags),
        finished=tuple(finished),
    )


def plan_and_resolve(
    layers: tuple[LayerVersions, ...],
    planned: Mapping[str, SerializableVersion],
    record: MigrationRecord | None,
    explicit: Mapping[str, SerializableVersion] | None = None,
) -> VersionResolution:
    """Plan the resume from `record` as the walk planner does, then resolve."""
    return resolve_versions(layers, planned, plan_resume(layers, record, explicit))


@dataclasses.dataclass(frozen=True)
class Project:
    """A composed family project with its lock and the ancestors of its layers."""

    family: Family
    root: Path
    order: list[str]
    ancestors: dict[str, list[str]]

    @classmethod
    def compose(cls, family: Family, work: Path, root: Path) -> "Project":
        """Describe the project composed at `root` from the BASE templates."""
        templates = templates_at(family, work, BASE)
        order = [layer.name for layer in compose("app", templates).layers]
        ancestors = {
            name: [m.name for m in compose(name, templates).layers[:-1]]
            for name in order
        }
        return cls(family, root, order, ancestors)

    def copied_to(self, destination: Path) -> "Project":
        """Copy the project, git history included, and describe the copy."""
        shutil.copytree(self.root, destination)
        return dataclasses.replace(self, root=destination)

    def write_lock(self, tags: Mapping[str, str]) -> BoilerplateLock:
        """Write the lock of the last complete update, at `tags`, and read it back."""
        lock = BoilerplateLock(
            boilerplate_version="0.3.0",
            copier_version="9.18.1",
            created_at=STAMP,
            updated_at=STAMP,
            root_template=f"app@{tags['app']}",
            layers=tuple(
                LockLayer(
                    name=name,
                    version=v(tags[name]),
                    source=self.family.repos[name].as_posix(),
                    commit=tags[name],
                    checksum="sha256:" + "0" * 64,
                )
                for name in self.order
            ),
        )
        write_lock(self.root, lock)
        return read_lock(self.root)

    def layers(self, lock: BoilerplateLock) -> tuple[LayerVersions, ...]:
        """Read every layer's versions from the lock and the answers files."""
        with ReleaseCheckouts() as checkouts:
            return read_layer_versions(self.root, lock, self.ancestors, checkouts)

    def hand_run(self, layer: str, tag: str) -> None:
        """Record that `layer` was updated by hand to `tag`, and commit it."""
        rehome_layer(
            self.root, layer=layer, source=self.family.repos[layer], commit=tag
        )
        commit_all(self.root, f"hand-run {layer} {tag}")


@pytest.fixture(scope="module")
def base_project(
    family: Family, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Project]:
    """Compose `app` at BASE, committed, with a lock at BASE."""
    work = tmp_path_factory.mktemp("update-versions")
    with temp_dir_inside(work):
        root = compose_family(family, work, "app", BASE)
        project = Project.compose(family, work, root)
        project.write_lock(BASE)
        commit_all(root, "lock")
        yield project


@pytest.fixture()
def project(base_project: Project, tmp_path: Path) -> Project:
    """Return a private copy of the BASE project."""
    return base_project.copied_to(tmp_path / "copy")


@pytest.fixture(scope="module")
def paused_project(
    family: Family, base_project: Project, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Project]:
    """Run core to 2.0.0 and service in place, as a walk paused after service."""
    work = tmp_path_factory.mktemp("paused")
    with temp_dir_inside(work):
        paused = base_project.copied_to(work / "paused")
        root = paused.root
        for layer in ("core", "service"):
            update_family_layer(
                family,
                root,
                root="app",
                layer=layer,
                before=BASE,
                after=PAUSED,
                work=work,
                data={},
                step_views=True,
            )
            commit_all(root, f"{layer} step")
        yield paused


class TestAPausedWalkResumesFromItsRecord:
    """Core 1.0.0 to 2.0.0, service stays, app 1.0.0 to 1.1.0; paused after service."""

    RECORD_TAGS: ClassVar[dict[str, str]] = {**PAUSED}

    def _resolve(
        self,
        paused: Project,
        planned: Mapping[str, str],
        explicit: Mapping[str, SerializableVersion] | None = None,
    ):
        lock = paused.write_lock(BASE)
        record = conflict_record(self.RECORD_TAGS, ["core", "service"])
        return plan_and_resolve(paused.layers(lock), targets(planned), record, explicit)

    def test_the_answers_files_record_what_the_paused_walk_did(
        self, paused_project: Project
    ) -> None:
        layers = {
            layer.name: layer
            for layer in paused_project.layers(paused_project.write_lock(BASE))
        }

        assert {n: str(layer.commit_version) for n, layer in layers.items()} == {
            "core": "2.0.0",
            "service": "1.0.0",
            "docs": "1.0.0",
            "app": "1.0.0",
        }

    def test_skips_service_although_its_own_version_did_not_move(
        self, paused_project: Project
    ) -> None:
        resolution = self._resolve(paused_project, self.RECORD_TAGS)

        assert resolution.resume is not None
        assert resolution.resume.finished == ("core", "service")
        assert tuple(resolution.old_copies) == ("docs", "app")

    def test_a_release_published_after_the_pause_does_not_move_the_targets(
        self, paused_project: Project, family: Family
    ) -> None:
        assert "3.0.0" in family.tags["core"]

        resolution = self._resolve(paused_project, {**PAUSED, "core": "3.0.0"})

        assert resolution.targets["core"] == v("2.0.0")

    def test_a_remaining_layers_old_copy_uses_the_locks_ancestor_versions(
        self, paused_project: Project
    ) -> None:
        resolution = self._resolve(paused_project, self.RECORD_TAGS)

        assert {
            name: str(version)
            for name, version in resolution.old_copies["app"].versions.items()
        } == {"core": "1.0.0", "service": "1.0.0", "docs": "1.0.0", "app": "1.0.0"}

    def test_an_explicit_target_that_differs_is_refused(
        self, paused_project: Project
    ) -> None:
        with pytest.raises(UpdateTargetMismatchError) as caught:
            self._resolve(paused_project, self.RECORD_TAGS, {"app": v("1.1.0.post1")})

        assert caught.value.error_code == "BP_UPDATE_TARGET_MISMATCH"
        assert caught.value.remediation is not None
        assert "git stash --include-untracked" in caught.value.remediation

    def test_the_record_no_longer_binds_once_the_partial_update_is_set_aside(
        self, paused_project: Project, tmp_path: Path
    ) -> None:
        set_aside = paused_project.copied_to(tmp_path / "aside")
        git(set_aside.root, "reset", "--hard", "HEAD~2")
        lock = set_aside.write_lock(BASE)
        record = conflict_record(self.RECORD_TAGS, ["core", "service"])

        resolution = plan_and_resolve(
            set_aside.layers(lock),
            targets({**PAUSED, "core": "3.0.0"}),
            record,
            {"app": v("1.1.0")},
        )

        assert resolution.resume is None
        assert resolution.targets["core"] == v("3.0.0")


class TestAmbiguousDriftStops:
    """Without a binding record, a layer and its ancestor both off the lock stop."""

    def test_a_retarget_after_a_pause_stops(self, project: Project) -> None:
        """Core was hand-run past the paused target, so the record no longer binds."""
        project.hand_run("core", "2.1.0")
        project.hand_run("service", "1.1.0")
        lock = project.write_lock(BASE)
        record = conflict_record(
            {**BASE, "core": "2.0.0", "service": "1.1.0", "app": "1.1.0"},
            ["core", "service"],
        )

        with pytest.raises(UpdateLayerDriftError) as caught:
            plan_and_resolve(
                project.layers(lock),
                targets({**BASE, "core": "3.0.0", "service": "1.2.0", "app": "1.1.0"}),
                record,
            )

        assert caught.value.error_code == "BP_UPDATE_LAYER_DRIFT"
        assert caught.value.layers == ("core", "service")

    def test_hand_runs_of_a_layer_and_an_ancestor_stop(self, project: Project) -> None:
        project.hand_run("core", "1.1.0")
        project.hand_run("service", "1.1.0")
        lock = project.write_lock(BASE)

        with pytest.raises(UpdateLayerDriftError) as caught:
            plan_and_resolve(
                project.layers(lock),
                targets({**BASE, "core": "2.0.0", "service": "1.2.0", "app": "1.1.0"}),
                None,
            )

        message = str(caught.value)
        assert "core: _commit 1.1.0, boilerplate.lock 1.0.0" in message
        assert "service: _commit 1.1.0, boilerplate.lock 1.0.0" in message
        assert caught.value.remediation is not None
        assert "git stash --include-untracked" in caught.value.remediation

    def test_a_hand_run_of_one_layer_warns_and_proceeds(self, project: Project) -> None:
        project.hand_run("service", "1.1.0")
        lock = project.write_lock(BASE)

        resolution = plan_and_resolve(
            project.layers(lock),
            targets({**BASE, "service": "1.2.0", "app": "1.1.0"}),
            None,
        )

        assert [(w.layer, w.commit) for w in resolution.warnings] == [
            ("service", "1.1.0")
        ]
        assert resolution.old_copies["service"].commit == "1.1.0"
        assert resolution.old_copies["app"].versions["service"] == v("1.0.0")


class TestDowngradesStopBeforeAnyLayerRuns:
    """A target older than a layer's recorded version is refused on real tags."""

    def test_a_target_older_than_the_recorded_tag_is_refused(
        self, project: Project
    ) -> None:
        project.hand_run("service", "1.2.0")
        lock = project.write_lock({**BASE, "service": "1.2.0"})

        with pytest.raises(UpdateDowngradeError) as caught:
            plan_and_resolve(
                project.layers(lock), targets({**BASE, "service": "1.1.0"}), None
            )

        assert (caught.value.layer, caught.value.recorded, caught.value.target) == (
            "service",
            "1.2.0",
            "1.1.0",
        )


def _views(project: Project, work: Path) -> dict[str, LayerView]:
    """Return every layer's scoped view at the BASE versions, in walk order."""
    templates = templates_at(project.family, work, BASE)
    return {name: layer_view(name, templates) for name in project.order}


def _recorded(project: Project) -> dict[str, dict[str, Any]]:
    return read_recorded_answers_by_layer(project.root)


def _trim_to_own_keys(project: Project, layer: str, own: set[str]) -> None:
    """Rewrite `layer`'s answers file as a vanilla hand-run update leaves it."""
    path = project.root / f".copier-answers.{layer}.yml"
    recorded = yaml.safe_load(path.read_text(encoding="utf-8"))
    kept = {k: v for k, v in recorded.items() if k.startswith("_") or k in own}
    path.write_text(yaml.safe_dump(kept), encoding="utf-8", newline="\n")


class TestATrimmedAnswersFile:
    """A vanilla hand-run of service keeps only service's own keys."""

    def test_an_untouched_project_passes(
        self, project: Project, tmp_path: Path
    ) -> None:
        check_answers_complete(_views(project, tmp_path), _recorded(project))

    def test_a_trimmed_service_file_passes_on_cores_record(
        self, project: Project, tmp_path: Path
    ) -> None:
        """Core declares the keys service's file lost, and core's file records them."""
        _trim_to_own_keys(project, "service", {"python_version", "port"})

        check_answers_complete(_views(project, tmp_path), _recorded(project))

    def test_a_key_no_layer_records_stops_naming_each_layer_that_lacks_it(
        self, project: Project, tmp_path: Path
    ) -> None:
        """Core's file loses `author_name` too, so no file can fill service's."""
        _trim_to_own_keys(project, "service", {"python_version", "port"})
        core_keys = set(_recorded(project)["core"]) - {"author_name"}
        _trim_to_own_keys(project, "core", core_keys)

        with pytest.raises(AnswersFileIncompleteError) as caught:
            check_answers_complete(_views(project, tmp_path), _recorded(project))

        assert caught.value.missing == {
            "core": ("author_name",),
            "service": ("author_name",),
        }
