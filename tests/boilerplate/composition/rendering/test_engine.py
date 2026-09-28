"""Unit tests for the object-oriented Renderer.

These tests patch Copier Worker/Template to avoid filesystem work and
validate orchestration semantics:
- Executes layers in order.
- Tasks are applied only on the final layer.
- RenderOptions flags are passed through correctly (interactive/defaults, overwrite).
"""

from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar

import pytest
from copier.errors import CopierAnswersInterrupt

import boilerplate.composition.rendering.engine as mod
from boilerplate.common.exceptions import (
    InteractiveRenderFailedError,
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


class FakeTemplate:
    def __init__(
        self, *args: object, **kwargs: object
    ) -> None:  # signature matches Template(url=str(...))
        pass


class FakeWorker:
    last_instances: ClassVar[list["FakeWorker"]] = []

    def __init__(self, **kwargs: object) -> None:
        self.init_kwargs = kwargs
        self.template = None
        self._cleanup_hooks: list[Callable[[], None]] = []
        self.ran = False
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

    def run_copy(self) -> None:
        self.ran = True


@pytest.fixture(autouse=True)
def patch_copier_symbols(monkeypatch: pytest.MonkeyPatch):
    # Patch copier.Template and copier.Worker used inside renderer
    monkeypatch.setattr(mod, "Template", FakeTemplate)
    monkeypatch.setattr(mod, "Worker", FakeWorker)
    # Ensure clean state per test run
    try:
        FakeWorker.last_instances.clear()
    except Exception:
        FakeWorker.last_instances = []


def _make_composition(tmp_path: Path, n: int, with_tasks: bool = True) -> Composition:
    layers = []
    nodes: dict[str, GraphNode] = {}
    order: list[str] = []
    for i in range(n):
        p = tmp_path / f"tmpl{i}"
        p.mkdir(parents=True, exist_ok=True)
        # Minimal boilerplate.yml to satisfy TemplateMeta.load
        (p / "boilerplate.yml").write_text(
            """
            schema_version: "1.0"
            name: sample
            description: x
            version: "0.0.1"
            extends: []
            """.strip()
        )
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
        p.mkdir(parents=True, exist_ok=True)
        (p / "boilerplate.yml").write_text(
            f"""
            schema_version: "1.0"
            name: {name}
            description: x
            version: "0.0.1"
            extends: []
            """.strip()
        )
        if copier_yml:
            (p / "copier.yml").write_text(copier_yml)
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
    assert len(FakeWorker.last_instances) == num_layers

    # Check order and flags uniformly for all layers
    for idx, inst in enumerate(FakeWorker.last_instances):
        is_final_layer = idx == num_layers - 1

        assert inst.init_kwargs["src_path"] == str(comp.layers[idx].path)
        assert inst.init_kwargs["skip_tasks"] == (not is_final_layer)
        # defaults should be True when not interactive; only first layer
        # could be interactive
        assert inst.init_kwargs["defaults"] is True


def test_propagates_renderoptions_and_first_layer_interactive(tmp_path: Path):
    comp = _make_composition(tmp_path, 2, with_tasks=False)
    ctx = ExecutionContext(
        destination=tmp_path / "out2",
        context_data={"alpha": 1},
        overwrite=False,
        interactive=True,
    )

    RenderEngine().render(comp, ctx)

    assert len(FakeWorker.last_instances) == 2
    first, second = FakeWorker.last_instances

    # Overwrite: user's --force only gates the first layer (writing into a
    # pre-existing destination). Non-first layers are orchestrated overlays
    # of the composition and always overwrite.
    assert first.init_kwargs["overwrite"] is False
    assert second.init_kwargs["overwrite"] is True

    # First layer interactive -> defaults False; second layer non-interactive
    # -> defaults True
    assert first.init_kwargs["defaults"] is False
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

    assert len(FakeWorker.last_instances) == 3
    # First layer honors user's --force (False here)
    assert FakeWorker.last_instances[0].init_kwargs["overwrite"] is False
    # Non-first layers always overwrite regardless of user's --force
    assert FakeWorker.last_instances[1].init_kwargs["overwrite"] is True
    assert FakeWorker.last_instances[2].init_kwargs["overwrite"] is True


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

    assert len(FakeWorker.last_instances) == 1
    worker = FakeWorker.last_instances[0]

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

    assert len(FakeWorker.last_instances) == 1
    worker = FakeWorker.last_instances[0]

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
    assert len(FakeWorker.last_instances) == num_layers

    # Check all layers uniformly: only final layer executes tasks
    for idx, worker in enumerate(FakeWorker.last_instances):
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
    p.mkdir(parents=True, exist_ok=True)
    (p / "boilerplate.yml").write_text(
        """
        schema_version: "1.0"
        name: sample
        description: x
        version: "0.0.1"
        extends: []
        """.strip()
    )
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
        assert len(FakeWorker.last_instances) == 1

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
        assert len(FakeWorker.last_instances) == 1


class _FakePromptToolkitError(Exception):
    """Stand-in for prompt_toolkit.output.win32.NoConsoleScreenBufferError."""


# Pretend this exception lives in prompt_toolkit so the translator recognizes it.
_FakePromptToolkitError.__module__ = "prompt_toolkit.output.win32"


class _FakeQuestionaryError(Exception):
    """Stand-in for questionary.*Error raised under a pseudo-TTY."""


_FakeQuestionaryError.__module__ = "questionary.prompts.text"


class _CrashingWorker(FakeWorker):
    """FakeWorker subclass whose run_copy raises a fake prompt_toolkit error."""

    # subclass will set this on the class
    exc_to_raise: ClassVar[type[BaseException]] = _FakePromptToolkitError

    def run_copy(self) -> None:
        raise type(self).exc_to_raise("simulated prompt failure")


class _UnrelatedError(Exception):
    """Stand-in for a crash that is NOT from the prompt stack."""


class _NonPromptCrashingWorker(FakeWorker):
    def run_copy(self) -> None:
        raise _UnrelatedError("totally unrelated bug")


class TestInteractivePromptCrashTranslation:
    """Worker errors originating in prompt_toolkit/questionary get translated."""

    def test_prompt_toolkit_error_translated_to_boilerplate_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _CrashingWorker.exc_to_raise = _FakePromptToolkitError
        monkeypatch.setattr(mod, "Worker", _CrashingWorker)

        comp = _make_composition_with_questions(
            tmp_path,
            {"project_name": {"type": "str", "default": "x"}},
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=True,  # bypass the pre-flight; let Copier "prompt"
        )

        with pytest.raises(InteractiveRenderFailedError) as exc_info:
            RenderEngine().render(comp, ctx)

        # The original prompt_toolkit error is preserved via `__cause__`.
        assert isinstance(exc_info.value.__cause__, _FakePromptToolkitError)

    def test_questionary_error_also_translated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _CrashingWorker.exc_to_raise = _FakeQuestionaryError
        monkeypatch.setattr(mod, "Worker", _CrashingWorker)

        comp = _make_composition_with_questions(
            tmp_path, {"x": {"type": "str", "default": "x"}}
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=True,
        )

        with pytest.raises(InteractiveRenderFailedError):
            RenderEngine().render(comp, ctx)

    def test_unrelated_error_is_not_translated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Errors not from prompt_toolkit/questionary propagate unchanged."""
        monkeypatch.setattr(mod, "Worker", _NonPromptCrashingWorker)

        comp = _make_composition_with_questions(
            tmp_path, {"x": {"type": "str", "default": "x"}}
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=True,
        )

        with pytest.raises(_UnrelatedError):
            RenderEngine().render(comp, ctx)


# ---------------------------------------------------------------------------
# Ctrl+C at a prompt: user cancellation, not a crash to dump
# ---------------------------------------------------------------------------


class _CopierAnswersInterruptCrashingWorker(FakeWorker):
    """FakeWorker whose run_copy raises a real CopierAnswersInterrupt.

    Carries realistic-looking payload strings so the regression test proves
    they never reach the caller, not just that *some* exception fires.
    """

    payload: ClassVar[tuple[str, str, str]] = (
        "AnswersMap(fake)",
        "Question(fake)",
        "Template(fake)",
    )

    def run_copy(self) -> None:
        answers, last_question, template = type(self).payload
        # Real callers pass AnswersMap/Question/Template instances; plain
        # strings are enough to prove the payload never reaches the caller.
        raise CopierAnswersInterrupt(answers, last_question, template)  # pyright: ignore[reportArgumentType]


class _PlainKeyboardInterruptWorker(FakeWorker):
    """FakeWorker whose run_copy raises a bare KeyboardInterrupt.

    Simulates Ctrl+C outside the prompt layer (e.g. mid file-write) -- NOT
    the CopierAnswersInterrupt Copier raises during prompting.
    """

    def run_copy(self) -> None:
        raise KeyboardInterrupt


class TestUserCancellationTranslation:
    """Ctrl+C at a prompt is recognized as user cancellation, not a crash."""

    def test_copier_answers_interrupt_becomes_concise_cancellation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The render path translates CopierAnswersInterrupt to UserCancelledError.

        Regression test: proves the translated error's message never contains
        the raw answers/question/template payload, regardless of how large or
        sensitive that payload is.
        """
        abs_template_path = str(tmp_path.resolve())
        _CopierAnswersInterruptCrashingWorker.payload = (
            "AnswersMap(fake answers)",
            "Question(fake question)",
            f"Template(path={abs_template_path})",
        )
        monkeypatch.setattr(mod, "Worker", _CopierAnswersInterruptCrashingWorker)

        comp = _make_composition_with_questions(
            tmp_path, {"x": {"type": "str", "default": "x"}}
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=True,
        )

        with pytest.raises(UserCancelledError) as exc_info:
            RenderEngine().render(comp, ctx)

        message = str(exc_info.value)
        assert message == "Aborted."
        assert "AnswersMap(" not in message
        assert "Question(" not in message
        assert abs_template_path not in message

    def test_plain_keyboard_interrupt_outside_prompt_is_not_swallowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bare KeyboardInterrupt (not CopierAnswersInterrupt) propagates.

        Only CopierAnswersInterrupt gets the friendly cancellation treatment.
        A plain Ctrl+C elsewhere in the render path (e.g. mid file-write) is a
        different, less controlled situation and must not be silently caught
        or reclassified.
        """
        monkeypatch.setattr(mod, "Worker", _PlainKeyboardInterruptWorker)

        comp = _make_composition_with_questions(
            tmp_path, {"x": {"type": "str", "default": "x"}}
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=True,
        )

        with pytest.raises(KeyboardInterrupt):
            RenderEngine().render(comp, ctx)


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

        exclude = FakeWorker.last_instances[0].init_kwargs["exclude"]
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
        assert len(FakeWorker.last_instances) == 1


# ---------------------------------------------------------------------------
# `unsafe` is scoped per layer to what that layer's own render actually needs
# ---------------------------------------------------------------------------


class TestLayerScopedUnsafe:
    """`unsafe` is granted per layer, not blanket-True for the whole composition.

    A layer needs it when its Worker will load Jinja extensions (its own, or
    the merged union injected when the composition's final schema declares
    any — see TestMergedExtensionInjection) or when it is the final layer
    executing the accumulated task list
    (docs/design/adr-014-deferred-task-execution.md). Extension-free,
    task-free invocations run with unsafe=False, narrowing the permissive
    posture of docs/design/adr-003-permissive-execution.md without changing
    behavior for layers that need the grant.

    These cases hand the engine a final schema with no `_jinja_extensions`,
    so only each layer's own on-disk declarations are in play.
    """

    def test_layer_without_extensions_or_tasks_gets_unsafe_false(
        self, tmp_path: Path
    ) -> None:
        comp = _make_two_layer_composition(tmp_path, with_tasks=False)
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)

        base_worker, final_worker = FakeWorker.last_instances
        assert base_worker.init_kwargs["unsafe"] is False
        assert final_worker.init_kwargs["unsafe"] is False

    def test_layer_declaring_jinja_extensions_gets_unsafe_true(
        self, tmp_path: Path
    ) -> None:
        comp = _make_two_layer_composition(
            tmp_path,
            base_copier_yml="_jinja_extensions:\n  - some_pkg.SomeExtension\n",
            with_tasks=False,
        )
        ctx = ExecutionContext(
            destination=tmp_path / "out",
            context_data={},
            overwrite=True,
            interactive=False,
        )

        RenderEngine().render(comp, ctx)

        base_worker, final_worker = FakeWorker.last_instances
        assert base_worker.init_kwargs["unsafe"] is True
        # The sibling stays scoped down here only because this final schema
        # carries no merged `_jinja_extensions` union (the merger would
        # normally union the base's declaration into it).
        assert final_worker.init_kwargs["unsafe"] is False

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

        base_worker, final_worker = FakeWorker.last_instances
        # Non-final layers always render with tasks skipped, so a
        # non-final layer never needs unsafe for tasks.
        assert base_worker.init_kwargs["unsafe"] is False
        assert final_worker.init_kwargs["unsafe"] is True


class TestMergedExtensionInjection:
    """The merged `_jinja_extensions` union reaches every layer's Worker.

    The first layer's Worker asks the merged questionnaire, so a question
    default may use a filter from a sibling layer's extension; without the
    union injected, that render dies with `No filter named ...` (the
    end-to-end case lives in
    tests/integration/boilerplate/test_composed_extensions_integration.py).
    """

    def test_union_in_final_schema_grants_unsafe_to_every_layer(
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

        base_worker, final_worker = FakeWorker.last_instances
        assert base_worker.init_kwargs["unsafe"] is True
        assert final_worker.init_kwargs["unsafe"] is True

    def test_build_merged_template_exposes_injected_union(self, tmp_path: Path) -> None:
        layer = tmp_path / "layer"
        layer.mkdir()

        template = RenderEngine._build_merged_template(  # pyright: ignore[reportPrivateUsage]
            template_path=layer,
            merged_questions={},
            tasks_value=[],
            extensions_value=["probe_ext.ProbeExtension"],
            is_first_layer=True,
        )

        assert tuple(template.jinja_extensions) == ("probe_ext.ProbeExtension",)

    def test_filepath_specs_stay_layer_local(self, tmp_path: Path) -> None:
        """A filepath-style loader spec resolves only in its declaring layer's tree.

        The union filter therefore never injects it into siblings.
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

        base_worker, final_worker = FakeWorker.last_instances
        # Nothing injectable survives the filter, so neither layer needs
        # the unsafe grant.
        assert base_worker.init_kwargs["unsafe"] is False
        assert final_worker.init_kwargs["unsafe"] is False

    def test_injection_augments_own_declarations_in_place(self, tmp_path: Path) -> None:
        """The layer's own list keeps its order; injected entries append after it.

        Loader-before-spec ordering matters to copier_template_extensions.
        """
        layer = tmp_path / "layer"
        layer.mkdir()
        (layer / "copier.yml").write_text(
            "_jinja_extensions:\n"
            "  - copier_template_extensions.TemplateExtensionLoader\n"
            "  - _extensions/context.py:ContextUpdater\n",
            encoding="utf-8",
        )

        template = RenderEngine._build_merged_template(  # pyright: ignore[reportPrivateUsage]
            template_path=layer,
            merged_questions={},
            tasks_value=[],
            extensions_value=[
                "copier_template_extensions.TemplateExtensionLoader",
                "probe_ext.ProbeExtension",
            ],
            is_first_layer=True,
        )

        assert tuple(template.jinja_extensions) == (
            "copier_template_extensions.TemplateExtensionLoader",
            "_extensions/context.py:ContextUpdater",
            "probe_ext.ProbeExtension",
        )
