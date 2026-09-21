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

from boilerplate.composition.models import (
    Composition,
    CompositionGraph,
    CompositionLayer,
    GraphNode,
)
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import ExecutionContext
from boilerplate.composition.serialization import extract_complete_copier_config
from boilerplate.repository.directory_repository import DirectoryTemplateRepository

_TAG = "v1.0.0"
_ANSWERS_FILE = ".copier-answers.gitlayer.yml"
_ANSWERS_DIRECTIVE = f"_answers_file: {_ANSWERS_FILE}\n"
_TAGGED_CONTENT = "release content for {{ project_name }}"
_TAGGED_QUESTIONS = f"{_ANSWERS_DIRECTIVE}project_name:\n  type: str\n  default: demo\n"
_WORKING_TREE_CONTENT = "unreleased content for {{ unreleased_question }}"
_WORKING_TREE_QUESTIONS = (
    f"{_TAGGED_QUESTIONS}unreleased_question:\n  type: str\n  default: unreleased\n"
)
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


def _single_layer_composition(template: Path) -> Composition:
    """Wrap ``template`` as a one-layer composition.

    Args:
        template: Template directory to render.

    Returns:
        A composition whose only layer is ``template``.
    """
    spec = "gitlayer@0.1.0"
    node = GraphNode(name="gitlayer", version="0.1.0", path=template)
    return Composition(
        graph=CompositionGraph(nodes={spec: node}, edges={}, sequence=[spec]),
        sequence=[spec],
        layers=[
            CompositionLayer(name="gitlayer", version="0.1.0", path=template, values={})
        ],
        final={"project_name": {"type": "str", "default": "demo"}},
    )


def _render(template: Path, destination: Path) -> None:
    """Render ``template`` into ``destination`` non-interactively.

    Args:
        template: Template directory to render.
        destination: Directory to render into.
    """
    RenderEngine().render(
        _single_layer_composition(template),
        ExecutionContext(
            destination=destination,
            context_data={"project_name": "demo"},
            overwrite=True,
            interactive=False,
            skip_tasks=True,
        ),
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
            final={"project_name": {"type": "str", "default": "demo"}},
        )

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
