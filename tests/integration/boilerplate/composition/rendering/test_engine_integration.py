"""End-to-end runs against a template directory that is a git repository.

Copier treats such a directory as a VCS template: it clones it into a temp
directory and checks out a reference before reading or copying anything.
These tests pin the two consequences that only show up with a real git
repository — which revision the user gets, and whether the clone survives.

The revision contract is docs/design/adr-015-idiomatic-artifacts.md: a
composed project's recorded `_commit` must stay resolvable in the template's
own repository, so a render resolves at Copier's default ref (the latest tag)
and never at `HEAD`, whose dirty-render commit exists only inside Copier's
throwaway clone. Both halves of a layer — the question schema read through
the catalog and the files written by the render — must land on that same
revision, so each is pinned here from its own entry point.
"""

import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Any

import pytest
import yaml
from copier.errors import DirtyLocalWarning

from boilerplate.common.exceptions import MissingRequiredAnswersError
from boilerplate.composition.models import (
    Composition,
    CompositionGraph,
    CompositionLayer,
    GraphNode,
)
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import ExecutionContext
from boilerplate.composition.serialization import extract_complete_copier_config
from boilerplate.project_state.lock_file import LOCK_FILE_NAME, read_lock
from boilerplate.repository.directory_repository import DirectoryTemplateRepository
from boilerplate.repository.template_checksum import template_checksum
from boilerplate.types import SerializableVersion

_TAG = "v1.0.0"
_ANSWERS_FILE = ".copier-answers.gitlayer.yml"
_ANSWERS_DIRECTIVE = f"_answers_file: {_ANSWERS_FILE}\n"
_TAGGED_CONTENT = "release content for {{ project_name }}"
_TAGGED_QUESTIONS = f"{_ANSWERS_DIRECTIVE}project_name:\n  type: str\n  default: demo\n"
_WORKING_TREE_CONTENT = "unreleased content for {{ unreleased_question }}"
_WORKING_TREE_QUESTIONS = (
    f"{_TAGGED_QUESTIONS}unreleased_question:\n  type: str\n  default: unreleased\n"
)
_PROJECT_NAME_QUESTION: dict[str, Any] = {
    "project_name": {"type": "str", "default": "demo"}
}
_ANSWERS_STUB = (
    "# Changes here will be overwritten by Copier; NEVER EDIT MANUALLY\n"
    "{{ _copier_answers|to_nice_yaml -}}\n"
)


def _git(cwd: Path, *args: str) -> None:
    """Run a git command in ``cwd``, raising on failure.

    Args:
        cwd: Directory to run the command in.
        args: Arguments passed to the ``git`` executable.
    """
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture(autouse=True)
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Detaches git from the developer's global/system config and identity.

    Copier runs git itself when reading a VCS-tracked template, so the
    identity has to live in the environment rather than in a per-command
    argument list.
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "absent-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "absent-gitconfig-system"))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Boilerplate Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Boilerplate Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.invalid")


@pytest.fixture()
def temp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points ``tempfile`` at an empty directory so clones are countable.

    Returns:
        The directory Copier's ``mkdtemp`` will create its clones in.
    """
    root = tmp_path / "tempdir"
    root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(root))
    return root


@pytest.fixture()
def dirty_git_template(tmp_path: Path) -> Path:
    """Build a template repo tagged ``v1.0.0`` with newer, uncommitted edits.

    The uncommitted revision differs from the tagged one in both halves a
    layer contributes: it declares an extra question in ``copier.yml`` and
    references that question from the rendered file.

    Returns:
        Path to the template directory, which is the git repository root and
        the only entry in its parent catalog directory.
    """
    template = tmp_path / "catalog" / "gitlayer"
    template.mkdir(parents=True)
    (template / "boilerplate.yml").write_text(
        'schema_version: "1"\nname: gitlayer\nversion: 0.1.0\ndescription: layer\n',
        encoding="utf-8",
    )
    (template / "copier.yml").write_text(_TAGGED_QUESTIONS, encoding="utf-8")
    (template / "marker.txt.jinja").write_text(_TAGGED_CONTENT, encoding="utf-8")
    (template / "{{_copier_conf.answers_file}}.jinja").write_text(
        _ANSWERS_STUB, encoding="utf-8"
    )

    _git(template, "-c", "init.defaultBranch=main", "init")
    _git(template, "add", "-A")
    _git(template, "commit", "-m", "initial")
    _git(template, "tag", _TAG)

    (template / "copier.yml").write_text(_WORKING_TREE_QUESTIONS, encoding="utf-8")
    (template / "marker.txt.jinja").write_text(_WORKING_TREE_CONTENT, encoding="utf-8")
    return template


def _single_layer_composition(
    template: Path, name: str, final: dict[str, Any]
) -> Composition:
    """Wrap ``template`` as a one-layer composition at version ``0.1.0``.

    Args:
        template: Template directory to render.
        name: Name the layer carries in the composition.
        final: Questions the composition asks, keyed by question name.

    Returns:
        A composition whose only layer is ``template``.
    """
    spec = f"{name}@0.1.0"
    node = GraphNode(name=name, version="0.1.0", path=template)
    return Composition(
        graph=CompositionGraph(nodes={spec: node}, edges={}, sequence=[spec]),
        sequence=[spec],
        layers=[CompositionLayer(name=name, version="0.1.0", path=template, values={})],
        final=final,
    )


def _render_composition(composition: Composition, destination: Path) -> None:
    """Render ``composition`` into ``destination`` non-interactively.

    Args:
        composition: Composition to render, layers in order.
        destination: Directory to render into.
    """
    RenderEngine().render(
        composition,
        ExecutionContext(
            destination=destination,
            context_data={"project_name": "demo"},
            overwrite=True,
            interactive=False,
            skip_tasks=True,
        ),
    )


def _render(template: Path, destination: Path) -> None:
    """Render ``template`` into ``destination`` non-interactively.

    Args:
        template: Template directory to render.
        destination: Directory to render into.
    """
    _render_composition(
        _single_layer_composition(template, "gitlayer", _PROJECT_NAME_QUESTION),
        destination,
    )


def _catalog_config(catalog: Path) -> dict[str, Any]:
    """Read the sole catalog template's Copier config the way `Composer` does.

    Args:
        catalog: Directory holding template subdirectories.

    Returns:
        The extracted ``copier.yml``-style mapping for that template.
    """
    (info,) = DirectoryTemplateRepository(catalog).load_templates()
    return extract_complete_copier_config(info.copier_template)


class TestGitTemplateRevision:
    def test_renders_tagged_content_not_working_tree(
        self, dirty_git_template: Path, tmp_path: Path
    ) -> None:
        destination = tmp_path / "out"

        with warnings.catch_warnings():
            # Copier carries uncommitted template changes into its clone only
            # when the ref is `HEAD`, and says so with this warning. A render
            # at the latest tag must never provoke it.
            warnings.simplefilter("error", DirtyLocalWarning)
            _render(dirty_git_template, destination)

        assert (destination / "marker.txt").read_text(encoding="utf-8") == (
            "release content for demo"
        )

    def test_records_the_tag_as_the_answers_file_commit(
        self, dirty_git_template: Path, tmp_path: Path
    ) -> None:
        destination = tmp_path / "out"

        _render(dirty_git_template, destination)

        answers = yaml.safe_load(
            (destination / _ANSWERS_FILE).read_text(encoding="utf-8")
        )
        # A `git describe` shape (`v1.0.0-1-g<hash>`) would name the draft
        # commit Copier makes inside its own throwaway clone, which exists in
        # no repository afterwards and so resolves nowhere.
        assert answers["_commit"] == _TAG

    def test_catalog_config_read_sees_tagged_questions(
        self, dirty_git_template: Path
    ) -> None:
        config = _catalog_config(dirty_git_template.parent)

        assert "project_name" in config
        assert "unreleased_question" not in config


@pytest.fixture()
def plain_base_template(tmp_path: Path) -> Path:
    """Build a plain (non-git) template layer with its own per-layer answers file.

    Returns:
        Path to the template directory.
    """
    template = tmp_path / "catalog" / "baselayer"
    template.mkdir(parents=True)
    (template / "boilerplate.yml").write_text(
        'schema_version: "1"\nname: baselayer\nversion: 0.1.0\ndescription: layer\n',
        encoding="utf-8",
    )
    (template / "copier.yml").write_text(
        "_answers_file: .copier-answers.baselayer.yml\n"
        "base_question:\n  type: str\n  default: base\n",
        encoding="utf-8",
    )
    (template / "base.txt.jinja").write_text(
        "base content for {{ base_question }}", encoding="utf-8"
    )
    (template / "{{_copier_conf.answers_file}}.jinja").write_text(
        _ANSWERS_STUB, encoding="utf-8"
    )
    return template


class TestMultiLayerPerLayerAnswers:
    """A composed multi-layer render writes one answers file per layer.

    Per docs/design/adr-015-idiomatic-artifacts.md, each layer's own
    ``copier.yml`` governs its own answers file, natively written by Copier
    during that layer's render -- Boilerplate no longer writes any canonical
    ``.copier-answers.yml`` of its own.
    """

    def test_each_layer_gets_its_own_answers_file(
        self, plain_base_template: Path, dirty_git_template: Path, tmp_path: Path
    ) -> None:
        destination = tmp_path / "out"
        base_spec = "baselayer@0.1.0"
        git_spec = "gitlayer@0.1.0"

        composition = Composition(
            graph=CompositionGraph(
                nodes={
                    base_spec: GraphNode(
                        name="baselayer", version="0.1.0", path=plain_base_template
                    ),
                    git_spec: GraphNode(
                        name="gitlayer", version="0.1.0", path=dirty_git_template
                    ),
                },
                edges={},
                sequence=[base_spec, git_spec],
            ),
            sequence=[base_spec, git_spec],
            layers=[
                CompositionLayer(
                    name="baselayer",
                    version="0.1.0",
                    path=plain_base_template,
                    values={},
                ),
                CompositionLayer(
                    name="gitlayer", version="0.1.0", path=dirty_git_template, values={}
                ),
            ],
            final=_PROJECT_NAME_QUESTION,
        )

        _render_composition(composition, destination)

        base_answers = yaml.safe_load(
            (destination / ".copier-answers.baselayer.yml").read_text(encoding="utf-8")
        )
        assert base_answers["_src_path"] == str(plain_base_template)
        assert "_commit" not in base_answers

        git_answers = yaml.safe_load(
            (destination / _ANSWERS_FILE).read_text(encoding="utf-8")
        )
        assert git_answers["_src_path"] == str(dirty_git_template)
        assert git_answers["_commit"] == _TAG

        assert not (destination / ".copier-answers.yml").exists()


class TestCreationLock:
    """A successful render ends with ``boilerplate.lock`` describing its layers."""

    @pytest.fixture()
    def mixed_composition(
        self, plain_base_template: Path, dirty_git_template: Path
    ) -> Composition:
        """Compose a plain-folder layer and a git-backed layer, in that order."""
        specs = {"baselayer": plain_base_template, "gitlayer": dirty_git_template}
        nodes = {
            f"{name}@0.1.0": GraphNode(name=name, version="0.1.0", path=path)
            for name, path in specs.items()
        }
        return Composition(
            graph=CompositionGraph(nodes=nodes, edges={}, sequence=list(nodes)),
            sequence=list(nodes),
            layers=[
                CompositionLayer(name=name, version="0.1.0", path=path, values={})
                for name, path in specs.items()
            ],
            final={"project_name": {"type": "str", "default": "demo"}},
        )

    def test_a_folder_layer_is_locked_at_its_version_with_no_commit(
        self, mixed_composition: Composition, plain_base_template: Path, tmp_path: Path
    ) -> None:
        destination = tmp_path / "out"

        _render_composition(mixed_composition, destination)

        base = read_lock(destination).layers[0]
        assert (base.name, base.version, base.commit, base.source, base.checksum) == (
            "baselayer",
            SerializableVersion("0.1.0"),
            None,
            str(plain_base_template),
            template_checksum(plain_base_template),
        )

    def test_a_git_layer_is_locked_at_the_commit_its_answers_file_records(
        self, mixed_composition: Composition, dirty_git_template: Path, tmp_path: Path
    ) -> None:
        destination = tmp_path / "out"

        _render_composition(mixed_composition, destination)

        git_layer = read_lock(destination).layers[1]
        assert (git_layer.name, git_layer.commit, git_layer.source) == (
            "gitlayer",
            _TAG,
            str(dirty_git_template),
        )

    def test_the_lock_names_the_layers_in_order_and_the_root(
        self, mixed_composition: Composition, tmp_path: Path
    ) -> None:
        destination = tmp_path / "out"

        _render_composition(mixed_composition, destination)

        lock = read_lock(destination)
        assert [layer.name for layer in lock.layers] == ["baselayer", "gitlayer"]
        # The git layer's version is the release its commit names, the way
        # Copier's update reads it, not the version its folder declares.
        assert lock.root_template == "gitlayer@1.0.0"
        assert set(lock.copier_answers_file_hashes or {}) == {"baselayer", "gitlayer"}

    def test_the_lock_records_the_version_of_the_tool_given(
        self, mixed_composition: Composition, tmp_path: Path
    ) -> None:
        destination = tmp_path / "out"

        RenderEngine(boilerplate_version="9.9.9").render(
            mixed_composition,
            ExecutionContext(
                destination=destination,
                context_data={"project_name": "demo"},
                overwrite=True,
                interactive=False,
                skip_tasks=True,
            ),
        )

        assert read_lock(destination).boilerplate_version == "9.9.9"

    def test_a_render_that_fails_writes_no_lock(
        self, mixed_composition: Composition, tmp_path: Path
    ) -> None:
        destination = tmp_path / "out"
        failing = mixed_composition.model_copy(
            update={"final": {"required_without_default": {"type": "str"}}}
        )

        with pytest.raises(MissingRequiredAnswersError, match="required_without"):
            _render_composition(failing, destination)

        assert not (destination / LOCK_FILE_NAME).exists()


class TestGitTemplateCleanup:
    def test_render_removes_its_clone(
        self, dirty_git_template: Path, tmp_path: Path, temp_root: Path
    ) -> None:
        destination = tmp_path / "out"

        _render(dirty_git_template, destination)

        assert (destination / "marker.txt").exists(), "render produced no output"
        assert list(temp_root.glob("copier*")) == []

    def test_catalog_config_read_removes_its_clone(
        self, dirty_git_template: Path, temp_root: Path
    ) -> None:
        config = _catalog_config(dirty_git_template.parent)

        assert "project_name" in config, "config read produced nothing"
        assert list(temp_root.glob("copier*")) == []


class TestCopierVersionLine:
    """Copier's "Copying from template version" line names a real version.

    Seam: the progress line Copier writes to stderr when a layer renders.
    Source of truth: the layer version the composition carries, which is the
    ``0.1.0`` literal in ``_single_layer_composition`` for a plain
    folder, and the git tag (``v1.0.0``) for a git-backed template, whose
    version Copier uses to choose migrations.
    Breaks if the engine stops supplying the version, or overrides a git one.
    """

    def test_plain_folder_reports_the_layer_version(
        self,
        plain_base_template: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        RenderEngine().render(
            _single_layer_composition(
                plain_base_template,
                "baselayer",
                {"base_question": {"type": "str", "default": "base"}},
            ),
            ExecutionContext(
                destination=tmp_path / "out",
                context_data={},
                overwrite=True,
                interactive=False,
                skip_tasks=True,
            ),
        )

        assert "Copying from template version 0.1.0\n" in capsys.readouterr().err

    def test_git_backed_template_keeps_its_git_version(
        self,
        dirty_git_template: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _render(dirty_git_template, tmp_path / "out")

        assert "Copying from template version 1.0.0\n" in capsys.readouterr().err


@pytest.fixture()
def base_layer_writing_shared(tmp_path: Path) -> Path:
    """Build a plain first layer that writes `shared.txt`.

    Returns:
        Path to the template directory.
    """
    layer = tmp_path / "catalog" / "base"
    layer.mkdir(parents=True)
    (layer / "boilerplate.yml").write_text(
        'schema_version: "1"\nname: base\nversion: 0.1.0\ndescription: layer\n',
        encoding="utf-8",
    )
    (layer / "shared.txt.jinja").write_text("base content", encoding="utf-8")
    return layer


@pytest.fixture()
def final_layer_protecting_shared(tmp_path: Path) -> Path:
    """Build a final, plain layer overlaying `shared.txt`, declaring it project-owned.

    Returns:
        Path to the template directory.
    """
    layer = tmp_path / "catalog" / "final"
    layer.mkdir(parents=True)
    (layer / "boilerplate.yml").write_text(
        'schema_version: "1"\nname: final\nversion: 0.1.0\ndescription: layer\n',
        encoding="utf-8",
    )
    (layer / "copier.yml").write_text(
        "_skip_if_exists:\n  - shared.txt\n", encoding="utf-8"
    )
    (layer / "shared.txt.jinja").write_text("final content", encoding="utf-8")
    return layer


def _two_layer_composition(base: Path, final: Path) -> Composition:
    """Wrap `base` then `final` as a two-layer composition.

    Args:
        base: The first layer to render.
        final: The second (final) layer, overlaying `base`.

    Returns:
        A composition whose layers are `base` then `final`, in that order.
    """
    base_spec = "base@0.1.0"
    final_spec = "final@0.1.0"
    return Composition(
        graph=CompositionGraph(
            nodes={
                base_spec: GraphNode(name="base", version="0.1.0", path=base),
                final_spec: GraphNode(name="final", version="0.1.0", path=final),
            },
            edges={final_spec: [base_spec]},
            sequence=[base_spec, final_spec],
        ),
        sequence=[base_spec, final_spec],
        layers=[
            CompositionLayer(name="base", version="0.1.0", path=base, values={}),
            CompositionLayer(name="final", version="0.1.0", path=final, values={}),
        ],
        final=_PROJECT_NAME_QUESTION,
    )


class TestComposedRenderIgnoresSkipIfExists:
    """No layer's `_skip_if_exists` applies in a composed render.

    docs/design/04-composition-engine.md §Per-Layer Render Loop: a composed
    render writes every layer's files regardless of what its own
    `_skip_if_exists` declares — that list governs only the layer's own
    `copier update`.
    """

    def test_forced_render_overwrites_file_first_layer_declares_project_owned(
        self, final_layer_protecting_shared: Path, tmp_path: Path
    ) -> None:
        destination = tmp_path / "out"
        destination.mkdir()
        (destination / "shared.txt").write_text("existing content", encoding="utf-8")

        _render(final_layer_protecting_shared, destination)

        assert (destination / "shared.txt").read_text(encoding="utf-8") == (
            "final content"
        )

    def test_final_layer_overlays_shared_file_it_declares_project_owned(
        self,
        base_layer_writing_shared: Path,
        final_layer_protecting_shared: Path,
        tmp_path: Path,
    ) -> None:
        destination = tmp_path / "out"

        _render_composition(
            _two_layer_composition(
                base_layer_writing_shared, final_layer_protecting_shared
            ),
            destination,
        )

        assert (destination / "shared.txt").read_text(encoding="utf-8") == (
            "final content"
        )


class TestForcedRerenderOverRejectedAnswer:
    """A `--force` re-render takes its answers as data, whatever the file records."""

    def _layer(self, root: Path, choices: str, default: str) -> Path:
        template = root / "colorlayer"
        template.mkdir(parents=True, exist_ok=True)
        (template / "boilerplate.yml").write_text(
            'schema_version: "1"\nname: colorlayer\nversion: 0.1.0\ndescription: x\n',
            encoding="utf-8",
        )
        (template / "copier.yml").write_text(
            "_answers_file: .copier-answers.colorlayer.yml\n"
            f"color:\n  type: str\n  choices: [{choices}]\n  default: {default}\n",
            encoding="utf-8",
        )
        (template / "{{_copier_conf.answers_file}}.jinja").write_text(
            _ANSWERS_STUB, encoding="utf-8"
        )
        return template

    def _render(self, template: Path, destination: Path) -> None:
        spec = "colorlayer@0.1.0"
        node = GraphNode(name="colorlayer", version="0.1.0", path=template)
        RenderEngine().render(
            Composition(
                graph=CompositionGraph(nodes={spec: node}, edges={}, sequence=[spec]),
                sequence=[spec],
                layers=[
                    CompositionLayer(
                        name="colorlayer", version="0.1.0", path=template, values={}
                    )
                ],
                final={
                    "color": {"type": "str", "choices": ["green"], "default": "green"}
                },
            ),
            ExecutionContext(
                destination=destination,
                overwrite=True,
                interactive=False,
                skip_tasks=True,
            ),
        )

    def test_the_new_default_replaces_a_recorded_answer_the_view_rejects(
        self, tmp_path: Path
    ) -> None:
        """Compose supplies every answer as data, so no recorded answer is checked."""
        destination = tmp_path / "out"
        self._render(self._layer(tmp_path, "red, blue", "red"), destination)

        self._render(self._layer(tmp_path, "green", "green"), destination)

        recorded = yaml.safe_load(
            (destination / ".copier-answers.colorlayer.yml").read_text(encoding="utf-8")
        )
        assert recorded["color"] == "green"
