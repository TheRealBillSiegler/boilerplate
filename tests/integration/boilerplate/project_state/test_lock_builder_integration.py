"""``build_lock`` against a project whose layers point at real tagged repositories."""

import hashlib
from datetime import UTC, datetime
from importlib.metadata import version as installed_version
from pathlib import Path

import pytest

from boilerplate.project_state.lock_builder import build_lock
from boilerplate.project_state.lock_file import read_lock, write_lock
from boilerplate.repository.release_checkouts import ReleaseCheckouts
from boilerplate.repository.template_checksum import template_checksum
from boilerplate.types import SerializableVersion
from tests.boilerplate.templates.conftest import build_layer_repo, commit_all, git

pytestmark = [pytest.mark.usefixtures("isolated_temp")]

EARLIER = datetime(2026, 9, 1, 9, 30, tzinfo=UTC)


class Layers:
    """Two tagged layer repositories and the project that records them."""

    def __init__(self, root: Path) -> None:
        self.releases: dict[str, dict[str, Path]] = {}
        self.repos: dict[str, Path] = {}
        for layer in ("core", "app"):
            self.releases[layer] = {}
            for tag in ("1.0.0", "1.1.0"):
                release = root / "releases" / layer / tag
                release.mkdir(parents=True)
                (release / "file.txt").write_text(f"{layer} {tag}\n", encoding="utf-8")
                self.releases[layer][tag] = release
            self.repos[layer] = build_layer_repo(
                root / "repos" / layer, self.releases[layer]
            )
        self.project = root / "project"
        self.project.mkdir()

    def record(self, layer: str, commit: str, **extra: str) -> Path:
        """Write the layer's answers file as Copier would, pointing at its repo."""
        path = self.project / f".copier-answers.{layer}.yml"
        lines = [f"_commit: {commit}", f"_src_path: {self.repos[layer].as_posix()}"]
        lines += [f"{key}: {value}" for key, value in extra.items()]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return path


@pytest.fixture
def layers(tmp_path: Path) -> Layers:
    """Return the layers with both answers files recorded at 1.0.0."""
    built = Layers(tmp_path)
    built.record("core", "1.0.0", name="demo")
    built.record("app", "1.0.0")
    return built


class TestBuildLock:
    def test_lists_the_layers_in_the_order_given(self, layers: Layers) -> None:
        """Keep the composition's topological order."""
        lock = build_lock(layers.project, ["core", "app"], boilerplate_version="0.3.0")

        assert [layer.name for layer in lock.layers] == ["core", "app"]

    def test_records_source_version_commit_and_checksum_per_layer(
        self, layers: Layers
    ) -> None:
        """Read the layer's answers file and its release."""
        lock = build_lock(layers.project, ["core", "app"], boilerplate_version="0.3.0")

        core = lock.layers[0]
        assert (core.source, core.commit, core.version, core.checksum) == (
            layers.repos["core"].as_posix(),
            "1.0.0",
            SerializableVersion("1.0.0"),
            template_checksum(layers.releases["core"]["1.0.0"]),
        )

    def test_hashes_each_answers_file(self, layers: Layers) -> None:
        """Hash the raw bytes of every layer's answers file."""
        lock = build_lock(layers.project, ["core", "app"], boilerplate_version="0.3.0")

        assert lock.copier_answers_file_hashes == {
            layer: hashlib.sha256(
                (layers.project / f".copier-answers.{layer}.yml").read_bytes()
            ).hexdigest()
            for layer in ("core", "app")
        }

    def test_names_the_tools_and_the_root_template(self, layers: Layers) -> None:
        """Record both versions and the last layer as the root."""
        lock = build_lock(layers.project, ["core", "app"], boilerplate_version="0.3.0")

        assert (lock.boilerplate_version, lock.copier_version, lock.root_template) == (
            "0.3.0",
            installed_version("copier"),
            "app@1.0.0",
        )

    def test_a_new_lock_is_stamped_with_one_instant(self, layers: Layers) -> None:
        """Create and update the lock at the same moment, which is now."""
        before = datetime.now(UTC)

        lock = build_lock(layers.project, ["core", "app"], boilerplate_version="0.3.0")

        assert lock.created_at == lock.updated_at
        assert before <= lock.updated_at <= datetime.now(UTC)

    def test_a_rewritten_lock_keeps_when_the_project_was_created(
        self, layers: Layers
    ) -> None:
        """Carry ``created_at`` over from the lock being replaced."""
        first = build_lock(layers.project, ["core", "app"], boilerplate_version="0.3.0")
        earlier = first.model_copy(update={"created_at": EARLIER})

        second = build_lock(
            layers.project,
            ["core", "app"],
            boilerplate_version="0.3.0",
            previous=earlier,
        )

        assert second.created_at == EARLIER

    def test_leaves_the_callers_checkouts_in_place(self, layers: Layers) -> None:
        """Read the releases from the given checkouts and not remove them."""
        with ReleaseCheckouts() as checkouts:
            source = layers.repos["core"].as_posix()
            held = checkouts.get(source, "1.0.0").path

            lock = build_lock(
                layers.project,
                ["core", "app"],
                boilerplate_version="0.3.0",
                checkouts=checkouts,
            )

            assert held.is_dir()
        assert lock == build_lock(
            layers.project, ["core", "app"], boilerplate_version="0.3.0"
        ).model_copy(
            update={"created_at": lock.created_at, "updated_at": lock.updated_at}
        )

    def test_a_commit_past_a_tag_is_read_the_way_copier_reads_it(
        self, layers: Layers
    ) -> None:
        """Record the version Copier's update compares: a post-release of the tag."""
        repo = layers.repos["core"]
        (repo / "file.txt").write_text("past the tag\n", encoding="utf-8")
        commit_all(repo, "work after 1.1.0")
        described = git(repo, "describe", "--tags", "--always").strip()
        layers.record("core", described, name="demo")

        lock = build_lock(layers.project, ["core", "app"], boilerplate_version="0.3.0")

        core = lock.layers[0]
        assert (core.commit, core.version.base_version, core.version.post) == (
            described,
            "1.1.0",
            1,
        )

    def test_a_layer_without_a_recorded_commit_is_refused(self, layers: Layers) -> None:
        """Name the layer: a plain-directory render records no ``_commit``."""
        (layers.project / ".copier-answers.app.yml").write_text(
            f"_src_path: {layers.repos['app'].as_posix()}\n", encoding="utf-8"
        )

        with pytest.raises(ValueError, match="app"):
            build_lock(layers.project, ["core", "app"], boilerplate_version="0.3.0")

    def test_the_lock_round_trips_through_the_writer(self, layers: Layers) -> None:
        """Write what was built and read it back unchanged."""
        lock = build_lock(layers.project, ["core", "app"], boilerplate_version="0.3.0")

        write_lock(layers.project, lock)

        assert read_lock(layers.project) == lock
