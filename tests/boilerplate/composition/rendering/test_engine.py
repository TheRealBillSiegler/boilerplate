"""Unit tests for the object-oriented Renderer.

These tests patch the Copier Worker to avoid filesystem work and validate
orchestration semantics:
- The merged questionnaire is asked once, by its own Worker.
- Executes layers in order, each under its scoped view.
- Tasks are applied only on the final layer.
- RenderOptions flags are passed through correctly (interactive/defaults, overwrite).
"""

from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar

import pytest
from copier.errors import CopierAnswersInterrupt

import boilerplate.composition.rendering.worker_session as session_mod
from boilerplate.common.exceptions import (
    MissingRequiredAnswersError,
    UserCancelledError,
)
from boilerplate.composition.models import (
    Composition,
    CompositionGraph,
    CompositionLayer,
    GraphNode,
)
from boilerplate.composition.rendering.engine import RenderEngine
from boilerplate.composition.rendering.models.execution_context import ExecutionContext

# Test-only alias for an internal helper; tests may legitimately probe internals.
_find_missing = RenderEngine._find_missing_required_answers  # pyright: ignore[reportPrivateUsage]


class FakeWorker:
    last_instances: ClassVar[list["FakeWorker"]] = []

    def __init__(self, **kwargs: object) -> None:
        self.init_kwargs = kwargs
        self.ran = False
        self.asked = False
        self.answers = None
        self.dst_path = kwargs.get("dst_path")

    def __enter__(self) -> "FakeWorker":
        type(self).last_instances.append(self)
        # Simulate answers per layer to observe accumulation
        # Include src path in metadata for minimal parity
        src_path_val = str(self.init_kwargs.get("src_path") or "")
        self.answers = type(
            "Answers",
            (),
            {
                "user": {"layer_mark": src_path_val},
                "metadata": {"_src_path": src_path_val},
                "hidden": set(),
            },
        )()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False

    def _ask(self) -> None:
        self.asked = True

    def run_copy(self) -> None:
        self.ran = True


def _layer_workers() -> list[FakeWorker]:
    """Return the Workers that rendered a layer, in render order."""
    return [w for w in FakeWorker.last_instances if w.ran]


def _questionnaire_workers() -> list[FakeWorker]:
    """Return the Workers that asked the questionnaire."""
    return [w for w in FakeWorker.last_instances if w.asked]


@pytest.fixture(autouse=True)
def patch_copier_symbols(monkeypatch: pytest.MonkeyPatch):
    # Patch the copier.Worker the render drives
    monkeypatch.setattr(session_mod, "ScopedWorker", FakeWorker)
    # Ensure clean state per test run
    try:
        FakeWorker.last_instances.clear()
    except Exception:
        FakeWorker.last_instances = []


def _write_layer_files(path: Path, name: str, copier_yml: str = "") -> None:
    """Write the `boilerplate.yml` and `copier.yml` of a layer named `name`."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "boilerplate.yml").write_text(
        f'schema_version: "1.0"\nname: {name}\ndescription: x\n'
        'version: "0.0.1"\nextends: []\n',
        encoding="utf-8",
    )
    (path / "copier.yml").write_text(copier_yml, encoding="utf-8")


def _make_composition(tmp_path: Path, n: int, with_tasks: bool = True) -> Composition:
    layers = []
    nodes: dict[str, GraphNode] = {}
    order: list[str] = []
    for i in range(n):
        p = tmp_path / f"tmpl{i}"
        _write_layer_files(p, f"tmpl{i}")
        layers.append(
            CompositionLayer(name=f"tmpl{i}", version="0.0.1", path=p, values={})
        )
        spec = f"tmpl{i}@0.0.1"
        nodes[spec] = GraphNode(name=f"tmpl{i}", version="0.0.1", path=p)
        order.append(spec)

    final: dict[str, Any] = {"q": {"default": 1}}
    if with_tasks:
        final["_tasks"] = [["echo", "final"]]

    graph = CompositionGraph(nodes=nodes, edges={}, sequence=order)
    return Composition(graph=graph, sequence=order, layers=layers, final=final)


def _make_two_layer_composition(
    tmp_path: Path,
    *,
    base_copier_yml: str = "",
    final_copier_yml: str = "",
    with_tasks: bool = False,
) -> Composition:
    """Build a base -> final composition with per-layer-controllable `copier.yml`.

    Per-layer directives (e.g. `_jinja_extensions`) can be exercised without
    touching the shipped first-party templates.
    """

    def _write(name: str, copier_yml: str) -> CompositionLayer:
        p = tmp_path / name
        _write_layer_files(p, name, copier_yml)
        return CompositionLayer(name=name, version="0.0.1", path=p, values={})

    base = _write("base", base_copier_yml)
    final = _write("final", final_copier_yml)
    nodes = {
        "base@0.0.1": GraphNode(name="base", version="0.0.1", path=base.path),
        "final@0.0.1": GraphNode(name="final", version="0.0.1", path=final.path),
    }
    graph = CompositionGraph(
        nodes=nodes,
        edges={"final@0.0.1": ["base@0.0.1"]},
        sequence=["base@0.0.1", "final@0.0.1"],
    )
    final_schema: dict[str, Any] = {"q": {"default": 1}}
    if with_tasks:
        final_schema["_tasks"] = [["echo", "final"]]
    return Composition(
        graph=graph,
        sequence=["base@0.0.1", "final@0.0.1"],
        layers=[base, final],
        final=final_schema,
    )


def test_executes_layers_in_order_and_only_final_runs_tasks(tmp_path: Path):
    comp = _make_composition(tmp_path, 3, with_tasks=True)
    ctx = ExecutionContext(
        destination=tmp_path / "out",
        context_data={"x": 1},
        overwrite=True,
        interactive=False,
    )

    RenderEngine().render(comp, ctx)

    num_layers = len(comp.layers)
    workers = _layer_workers()
    assert len(workers) == num_layers

    # Check order and flags uniformly for all layers
    for idx, inst in enumerate(workers):
        is_final_layer = idx == num_layers - 1

        assert inst.init_kwargs["src_path"] == str(comp.layers[idx].path)
        assert inst.init_kwargs["skip_tasks"] == (not is_final_layer)
        # Every answer is already in `data`: no layer prompts.
        assert inst.init_kwargs["defaults"] is True


def test_propagates_renderoptions_and_questionnaire_interactive(tmp_path: Path):
    comp = _make_composition(tmp_path, 2, with_tasks=False)
    ctx = ExecutionContext(
        destination=tmp_path / "out2",
        context_data={"alpha": 1},
        overwrite=False,
        interactive=True,
    )

    RenderEngine().render(comp, ctx)

    (asker,) = _questionnaire_workers()
    first, second = _layer_workers()

    # Overwrite: user's --force only gates the first layer (writing into a
    # pre-existing destination). Non-first layers are orchestrated overlays
    # of the composition and always overwrite.
    assert first.init_kwargs["overwrite"] is False
    assert second.init_kwargs["overwrite"] is True

    # Only the questionnaire pass prompts; the layers take its answers.
    assert asker.init_kwargs["defaults"] is False
    assert asker.init_kwargs["data"] == {"alpha": 1}
    assert first.init_kwargs["defaults"] is True
    assert second.init_kwargs["defaults"] is True


def test_non_first_layers_always_overwrite(tmp_path: Path):
    """Composition layers overlay by design; non-first layers force overwrite.

    Without this, Copier prompts 'Overwrite <file>?' for every file written
    by a non-first layer that conflicts with a file written by a previous
    layer — which is every file that the later layer is designed to
    replace. The user's --force only governs the first layer; subsequent
    layers are not conflicting writes, they are the composition itself.
    """
    comp = _make_composition(tmp_path, 3, with_tasks=False)
    ctx = ExecutionContext(
        destination=tmp_path / "out_overwrite",
        context_data={},
        overwrite=False,  # user did NOT pass --force
        interactive=False,
    )

    RenderEngine().render(comp, ctx)

    workers = _layer_workers()
    assert len(workers) == 3
    # First layer honors user's --force (False here)
    assert workers[0].init_kwargs["overwrite"] is False
    # Non-first layers always overwrite regardless of user's --force
    assert workers[1].init_kwargs["overwrite"] is True
    assert workers[2].init_kwargs["overwrite"] is True


def test_single_layer_executes_tasks_when_present(tmp_path: Path):
    """Single-layer templates execute tasks (final layer = first layer)."""
    comp = _make_composition(tmp_path, 1, with_tasks=True)
    ctx = ExecutionContext(
        destination=tmp_path / "out_single",
        context_data={},
        overwrite=True,
        interactive=False,
    )

    RenderEngine().render(comp, ctx)

    (worker,) = _layer_workers()

    # Single layer is both first AND final, so tasks should run
    assert worker.init_kwargs["skip_tasks"] is False, (
        "Single-layer template should execute tasks (is_final_layer=True)"
    )
    assert worker.ran is True


def test_single_layer_without_tasks_skips_tasks(tmp_path: Path):
    """Single-layer templates without _tasks skip tasks cleanly."""
    comp = _make_composition(tmp_path, 1, with_tasks=False)
    ctx = ExecutionContext(
        destination=tmp_path / "out_no_tasks",
        context_data={},
        overwrite=True,
        interactive=False,
    )

    RenderEngine().render(comp, ctx)

    (worker,) = _layer_workers()

    # No tasks in final schema, but still final layer
    assert worker.init_kwargs["skip_tasks"] is False, (
        "Even without tasks, final layer should have skip_tasks=False "
        "(Copier handles empty tasks gracefully)"
    )
    assert worker.ran is True


def test_multi_layer_only_final_executes_tasks(tmp_path: Path):
    """Multi-layer templates only execute tasks on the final layer."""
    comp = _make_composition(tmp_path, 3, with_tasks=True)
    ctx = ExecutionContext(
        destination=tmp_path / "out_multi",
        context_data={},
        overwrite=True,
        interactive=False,
    )

    RenderEngine().render(comp, ctx)

    num_layers = len(comp.layers)
    workers = _layer_workers()
    assert len(workers) == num_layers

    # Check all layers uniformly: only final layer executes tasks
    for idx, worker in enumerate(workers):
        is_final_layer = idx == num_layers - 1
        expected_skip_tasks = not is_final_layer

        assert worker.init_kwargs["skip_tasks"] == expected_skip_tasks, (
            f"Layer {idx}: skip_tasks should be {expected_skip_tasks} "
            f"(is_final_layer={is_final_layer})"
        )


# ---------------------------------------------------------------------------
# Required-answers pre-flight + interactive-prompt crash translation
# ---------------------------------------------------------------------------


def _make_composition_with_questions(
    tmp_path: Path, questions: dict[str, Any]
) -> Composition:
    """Build a single-layer composition carrying the given question schema."""
    p = tmp_path / "tmpl0"
    _write_layer_files(p, "tmpl0")
    layer = CompositionLayer(name="tmpl0", version="0.0.1", path=p, values={})
    spec = "tmpl0@0.0.1"
    graph = CompositionGraph(
        nodes={spec: GraphNode(name="tmpl0", version="0.0.1", path=p)},
        edges={},
        sequence=[spec],
    )
    return Composition(
        graph=graph, sequence=[spec], layers=[layer], final=dict(questions)
    )


class TestFindMissingRequiredAnswers:
    """Unit tests for the pure helper. Documents which keys count as required."""

    def test_question_without_default_is_required(self) -> None:
        missing = _find_missing(
            questions={"name": {"type": "str"}},
            supplied={},
        )
        assert missing == ["name"]

    def test_question_with_default_is_not_required(self) -> None:
        missing = _find_missing(
            questions={"name": {"type": "str", "default": "x"}},
            supplied={},
        )
        assert missing == []

    def test_supplied_value_satisfies_requirement(self) -> None:
        missing = _find_missing(
            questions={"name": {"type": "str"}},
            supplied={"name": "from-cli"},
        )
        assert missing == []

    def test_when_false_is_skipped(self) -> None:
        missing = _find_missing(
            questions={"slug": {"when": False}},
            supplied={},
        )
        assert missing == []

    def test_directive_keys_are_skipped(self) -> None:
        missing = _find_missing(
            questions={"_tasks": [["echo", "hi"]], "_exclude": ["*.bak"]},
            supplied={},
        )
        assert missing == []

    def test_reports_all_missing_in_schema_order(self) -> None:
        missing = _find_missing(
            questions={
                "first": {"type": "str"},
                "second": {"type": "str", "default": "ok"},
                "third": {"type": "str"},
            },
            supplied={},
        )
        assert missing == ["first", "third"]

    def test_non_dict_entry_is_skipped(self) -> None:
        # Malformed entries are left for Copier to surface, not reported here.
        missing = _find_missing(
            questions={"weird": "not-a-dict"},
            supplied={},
        )
        assert missing == []


class TestPreflightMissingRequiredAnswers:
    """Non-interactive render fails fast with named missing fields."""

    def test_raises_with_named_fields_when_required_and_non_interactive(
        self, tmp_path: Path
    ) -> None:
        comp = _make_composition_with_questions(
            tmp_path,
            {"project_name": {"type": "str"}, "author_email": {"type": "str"}},
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        with pytest.raises(MissingRequiredAnswersError) as exc_info:
            RenderEngine().render(comp, ctx)

        msg = str(exc_info.value)
        assert "project_name" in msg
        assert "author_email" in msg
        # The worker must not have been constructed — render refused pre-flight.
        assert FakeWorker.last_instances == []

    def test_interactive_mode_skips_preflight(self, tmp_path: Path) -> None:
        """Interactive render delegates to Copier, which prompts as usual."""
        comp = _make_composition_with_questions(
            tmp_path,
            {"project_name": {"type": "str"}},
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=True,
        )

        # Does not raise — FakeWorker just records the call and succeeds.
        RenderEngine().render(comp, ctx)
        assert len(_layer_workers()) == 1

    def test_supplied_context_satisfies_preflight(self, tmp_path: Path) -> None:
        comp = _make_composition_with_questions(
            tmp_path,
            {"project_name": {"type": "str"}},
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={"project_name": "pre-supplied"},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)
        assert len(_layer_workers()) == 1


# ---------------------------------------------------------------------------
# Worker excludes: Copier's own DEFAULT_EXCLUDE must survive a layer's `_exclude`
# ---------------------------------------------------------------------------


class TestWorkerExcludes:
    """Copier's DEFAULT_EXCLUDE reaches the worker despite layer `_exclude`.

    Copier only applies its built-in exclusions (`.git`, `__pycache__`, etc.)
    when a layer's `copier.yml` leaves `_exclude` unset; a layer that
    declares its own `_exclude` (as `templates/project/copier.yml` does, to
    hide `_extensions/`) replaces that default outright rather than
    extending it (`Template.exclude` in copier's internals). Passed via
    `Worker.exclude` instead, DEFAULT_EXCLUDE is always additive with a
    layer's own `_exclude`, so it survives regardless of what a layer
    declares.
    """

    def test_default_exclude_patterns_reach_every_worker(self, tmp_path: Path) -> None:
        comp = _make_composition(tmp_path, 1, with_tasks=False)
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)

        exclude = _layer_workers()[0].init_kwargs["exclude"]
        for pattern in (".git", "__pycache__", "~*", "*.py[co]", ".DS_Store", ".svn"):
            assert pattern in exclude, f"{pattern!r} missing from worker exclude"
        # Boilerplate's own authoring-metadata excludes stay covered too.
        assert "/boilerplate.yml" in exclude
        assert "/copier.yml" in exclude


# ---------------------------------------------------------------------------
# Conditional-question pre-flight: a Jinja `when` defers to Copier
# ---------------------------------------------------------------------------


class TestPreflightConditionalWhen:
    """A non-boolean `when` can only be resolved by Copier at render time.

    Copier's own non-interactive `--defaults` path silently skips a question
    whose `when` evaluates false, even with no default (`Worker._ask`: `if
    not question.get_when(): ...; if question.get_default() is MISSING:
    continue`) — it never raises for that case. Reporting such a question as
    "missing" here would false-positive a non-interactive render that Copier
    itself would have completed.
    """

    def test_string_when_is_not_statically_required(self) -> None:
        missing = _find_missing(
            questions={
                "docker_registry": {"type": "str", "when": "{{ enable_docker }}"}
            },
            supplied={},
        )
        assert missing == []

    def test_string_when_defers_even_if_it_would_always_evaluate_true(self) -> None:
        """Deliberate trade-off: a string `when` is never statically required.

        That includes one that (if rendered) would always be true. This
        pre-flight does not simulate Jinja rendering, so it cannot distinguish
        the two cases.
        Erring toward not blocking is intentional — Copier's own `--defaults`
        path still raises (a plainer, per-field) error for a question that
        turns out to truly be required, so nothing is silently skipped end to
        end, only excluded from this pre-flight's aggregated report.
        """
        missing = _find_missing(
            questions={"always_on": {"type": "str", "when": "true"}},
            supplied={},
        )
        assert missing == []

    def test_render_does_not_block_on_a_string_when(self, tmp_path: Path) -> None:
        comp = _make_composition_with_questions(
            tmp_path,
            {"docker_registry": {"type": "str", "when": "{{ enable_docker }}"}},
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)  # must not raise
        assert len(_layer_workers()) == 1


# ---------------------------------------------------------------------------
# `unsafe` is scoped per layer to what that layer's own render actually needs
# ---------------------------------------------------------------------------


class TestLayerScopedUnsafe:
    """`unsafe` is granted per layer, not blanket-True for the whole composition.

    A layer needs it when its Worker will load Jinja extensions or when it is
    the final layer executing the accumulated task list
    (docs/design/adr-014-deferred-task-execution.md). Which extensions grant it
    is decided by ``grants_unsafe`` (tests/boilerplate/composition/rendering/
    test_grants_unsafe.py); this case is the engine's own, the task list.
    """

    def test_final_layer_with_accumulated_tasks_gets_unsafe_true(
        self, tmp_path: Path
    ) -> None:
        """The final layer needs unsafe=True to run ADR-014's accumulated task list.

        This holds even when its own copier.yml declares no extensions.
        """
        comp = _make_two_layer_composition(tmp_path, with_tasks=True)
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)

        base_worker, final_worker = _layer_workers()
        # Non-final layers always render with tasks skipped, so a
        # non-final layer never needs unsafe for tasks.
        assert base_worker.init_kwargs["unsafe"] is False
        assert final_worker.init_kwargs["unsafe"] is True


class TestScopedExtensions:
    """Each layer's Worker gets the extensions of its scoped view; the pass, all.

    The questionnaire Worker asks the full merged schema, so a question default
    may use a filter from any layer's extension (the end-to-end case lives in
    tests/integration/boilerplate/test_composed_extensions_integration.py). A
    layer renders under the extensions of itself and its ancestors only, because
    a descendant's or a sibling's hook would change an ancestor's files.
    """

    def test_union_in_final_schema_reaches_the_questionnaire_and_the_final_layer(
        self, tmp_path: Path
    ) -> None:
        comp = _make_two_layer_composition(tmp_path, with_tasks=False)
        comp.final["_jinja_extensions"] = ["probe_ext.ProbeExtension"]
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)

        (asker,) = _questionnaire_workers()
        base_worker, final_worker = _layer_workers()
        assert asker.init_kwargs["unsafe"] is True
        assert base_worker.init_kwargs["unsafe"] is False
        assert final_worker.init_kwargs["unsafe"] is True

    def test_filepath_specs_stay_layer_local(self, tmp_path: Path) -> None:
        """A filepath-style loader spec resolves only in its declaring layer's tree.

        The view therefore never carries it as an importable extension.
        """
        comp = _make_two_layer_composition(tmp_path, with_tasks=False)
        comp.final["_jinja_extensions"] = ["_extensions/context.py:ContextUpdater"]
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)

        (asker,) = _questionnaire_workers()
        base_worker, final_worker = _layer_workers()
        # Nothing importable survives the filter, so no Worker needs the
        # unsafe grant.
        assert asker.init_kwargs["unsafe"] is False
        assert base_worker.init_kwargs["unsafe"] is False
        assert final_worker.init_kwargs["unsafe"] is False

    def test_a_layer_declaring_its_own_extension_gets_unsafe_for_its_render(
        self, tmp_path: Path
    ) -> None:
        """The engine passes the layer itself to ``grants_unsafe``, not only the view.

        A filepath-style spec never reaches the view, but Copier loads it from
        the declaring layer's own ``copier.yml``.
        """
        comp = _make_two_layer_composition(tmp_path, with_tasks=False)
        base = comp.layers[0]
        (base.path / "_extensions").mkdir()
        (base.path / "_extensions" / "context.py").write_text(
            "from jinja2.ext import Extension\n\n\n"
            "class ContextUpdater(Extension):\n    pass\n",
            encoding="utf-8",
        )
        comp.layers[0] = CompositionLayer(
            name=base.name,
            version=base.version,
            path=base.path,
            values={"_jinja_extensions": ["_extensions/context.py:ContextUpdater"]},
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)

        base_worker, _ = _layer_workers()
        assert base_worker.init_kwargs["unsafe"] is True


# ---------------------------------------------------------------------------
# One questionnaire pass, then each layer under its scoped view
# ---------------------------------------------------------------------------


class _AskInterruptWorker(FakeWorker):
    """FakeWorker whose questionnaire pass raises a real CopierAnswersInterrupt."""

    def _ask(self) -> None:
        raise CopierAnswersInterrupt(
            "AnswersMap(fake)", "Question(fake)", "Template(fake)"
        )  # pyright: ignore[reportArgumentType]


class TestScopedRenderLoop:
    """The questionnaire is asked once over the full schema; layers render scoped."""

    def test_the_questionnaire_is_asked_once_before_any_layer_renders(
        self, tmp_path: Path
    ) -> None:
        comp = _make_composition(tmp_path, 3, with_tasks=False)
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)

        (asker,) = _questionnaire_workers()
        assert FakeWorker.last_instances[0] is asker
        assert not asker.ran
        assert asker.init_kwargs["src_path"] == str(comp.layers[0].path)

    def test_every_layer_receives_the_questionnaires_answers_as_data(
        self, tmp_path: Path
    ) -> None:
        comp = _make_composition(tmp_path, 3, with_tasks=False)
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)

        (asker,) = _questionnaire_workers()
        for worker in _layer_workers():
            assert worker.init_kwargs["data"] == {
                "layer_mark": str(comp.layers[0].path),
                "_src_path": str(comp.layers[0].path),
            }
        assert asker.init_kwargs["src_path"] == str(comp.layers[0].path)

    def test_a_layer_renders_under_its_own_scoped_questions(
        self, tmp_path: Path
    ) -> None:
        comp = _make_two_layer_composition(
            tmp_path,
            base_copier_yml="base_q:\n  type: str\n  default: b\n",
            final_copier_yml="final_q:\n  type: str\n  default: f\n",
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)

        (asker,) = _questionnaire_workers()
        base_worker, final_worker = _layer_workers()
        # The pass and the final layer take the composition's merged schema;
        # the base layer takes only what it declares.
        assert set(asker.init_kwargs["target_view"].questions) == {"q"}
        assert set(base_worker.init_kwargs["target_view"].questions) == {"base_q"}
        assert set(final_worker.init_kwargs["target_view"].questions) == {"q"}

    def test_cancelling_the_questionnaire_becomes_concise_cancellation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(session_mod, "ScopedWorker", _AskInterruptWorker)
        comp = _make_composition_with_questions(
            tmp_path, {"x": {"type": "str", "default": "x"}}
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=True,
        )

        with pytest.raises(UserCancelledError):
            RenderEngine().render(comp, ctx)

        assert [w for w in FakeWorker.last_instances if w.ran] == []

    def test_only_the_final_layer_receives_the_merged_tasks(
        self, tmp_path: Path
    ) -> None:
        comp = _make_composition(tmp_path, 3, with_tasks=True)
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
            skip_tasks=False,
        )

        RenderEngine().render(comp, ctx)

        assert [w.init_kwargs["tasks"] for w in _layer_workers()] == [
            (),
            (),
            (["echo", "final"],),
        ]
