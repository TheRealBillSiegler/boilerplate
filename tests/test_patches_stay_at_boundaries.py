"""Every patch in the suite replaces something at a boundary, never a collaborator.

A test that patches one of this package's own objects couples itself to the
current arrangement of the code: it keeps passing while behaviour breaks, and
it breaks while behaviour stays the same. Patching belongs at the boundaries
the code does not control, which is where a real dependency is slow, absent,
or impossible to steer into the case under test.

The scan reads every test module as an AST and collects the targets of
``mocker.patch``, ``mocker.patch.object``, ``monkeypatch.setattr`` and bare
``patch``. A target whose owner resolves to a module outside this package
passes; a target inside it passes only when ``ALLOWED_SEAMS`` names it with a
reason. The planted-violation test proves the scan reports what it claims to.

Known blind spot: a target passed through a variable rather than a literal is
not seen. Keep patch targets literal.
"""

import ast
import importlib
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

PACKAGE = "boilerplate"
TESTS = Path(__file__).parent
PATCHERS = {"mocker.patch", "patch", "mock.patch"}
OBJECT_PATCHERS = {"mocker.patch.object", "patch.object", "monkeypatch.setattr"}

# Each entry names the seam and why the real thing cannot stand in the test.
ALLOWED_SEAMS: dict[str, str] = {
    "boilerplate.cli.commands.new._stdin_supports_prompts": (
        "Console probe; whether stdin is a terminal depends on the host."
    ),
    "boilerplate.cli.commands.new._stdin_is_real_console": (
        "Win32 console API probe; the answer depends on the host."
    ),
    "boilerplate.cli.cli.configure_logging": (
        "Process-global logging state; the arguments are the observable effect."
    ),
    "boilerplate.cli.cli.Settings": (
        "Reads the environment; a failing settings load cannot be staged through it."
    ),
    "boilerplate.__version__": ("Package metadata fixed at install time."),
    "boilerplate.settings.profile.profile_toml_path": ("The user's home directory."),
    "boilerplate.cli.utils.DirectoryTemplateRepository": (
        "Filesystem fault injection: a PermissionError or disk error cannot "
        "be produced deterministically on every platform."
    ),
    "boilerplate.repository.directory_repository.TemplateMeta.load": (
        "Filesystem fault injection: a file removed between listing and "
        "reading cannot be timed deterministically."
    ),
    "boilerplate.composition.staging.IntentJournal.read": (
        "Filesystem fault injection: a staging folder removed between its "
        "journal read and its owner check cannot be timed deterministically."
    ),
    "boilerplate.composition.rendering.engine.Worker": (
        "Copier's worker; a real one renders to disk."
    ),
    "boilerplate.composition.rendering.engine.Template": (
        "Copier's template loader; a real one clones or reads a template."
    ),
    "boilerplate.composition.staging.copy_back.run_git": (
        "Fault injection: git's restore failing partway through a copy back (a "
        "full disk, a file another program has open) cannot be produced "
        "deterministically on every platform; the wrapper runs every other git "
        "call for real."
    ),
    "boilerplate.composition.serialization.yaml_utils.template_public_attr_names": (
        "Counterfactual: drops one attribute from the extraction to show it is the "
        "only blocker to composing from git-repository layers; no input removes it."
    ),
}


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return None if base is None else f"{base}.{node.attr}"
    return None


def _imports(tree: ast.Module) -> dict[str, str]:
    """Map each name a module binds by import to the dotted path it names."""
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                names[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return names


def patch_targets(source: str) -> Iterator[str]:
    """Yield the dotted target of every patch call in a test module's source."""
    tree = ast.parse(source)
    names = _imports(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = _dotted(node.func) or ""
        args = node.args
        if func in PATCHERS and args and isinstance(args[0], ast.Constant):
            yield str(args[0].value)
        elif func in OBJECT_PATCHERS and len(args) >= 2:
            owner, attr = args[0], args[1]
            if isinstance(owner, ast.Constant):
                yield str(owner.value)
            elif isinstance(attr, ast.Constant):
                head, *rest = (_dotted(owner) or "?").split(".")
                yield ".".join([names.get(head, head), *rest, str(attr.value)])


def _owner_module(target: str) -> str | None:
    """Return the module that owns the object a patch target replaces.

    Resolves the owner by importing it, so ``pkg.mod.sys.stdin`` reports
    ``sys`` and a class attribute reports the class's module.
    """
    owner_path = target.rsplit(".", 1)[0]
    parts = owner_path.split(".")
    for i in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:i]))
        except ImportError:
            continue
        for attr in parts[i:]:
            obj = getattr(obj, attr, None)
            if obj is None:
                return None
        if isinstance(obj, types.ModuleType):
            return obj.__name__
        return getattr(obj, "__module__", None)
    return None


def _is_internal(target: str) -> bool:
    owner = _owner_module(target)
    return owner is not None and owner.split(".")[0] == PACKAGE


def violations(source: str) -> list[str]:
    """List the patch targets in ``source`` that reach inside the package."""
    return [
        target
        for target in patch_targets(source)
        if target not in ALLOWED_SEAMS and _is_internal(target)
    ]


def _test_modules() -> list[Path]:
    return sorted(p for p in TESTS.rglob("*.py") if p.name != Path(__file__).name)


class TestPatchesStayAtBoundaries:
    @pytest.mark.parametrize(
        "module", _test_modules(), ids=lambda p: p.relative_to(TESTS).as_posix()
    )
    def test_no_patch_reaches_inside_the_package(self, module: Path) -> None:
        found = violations(module.read_text(encoding="utf-8"))

        assert not found, (
            f"{module.relative_to(TESTS).as_posix()} patches inside {PACKAGE}: "
            f"{found}. Test through the interface, or name the seam in "
            "ALLOWED_SEAMS with the reason the real thing cannot stand."
        )

    def test_every_allowed_seam_is_still_used(self) -> None:
        used = {
            target
            for module in _test_modules()
            for target in patch_targets(module.read_text(encoding="utf-8"))
        }

        assert set(ALLOWED_SEAMS) <= used, sorted(set(ALLOWED_SEAMS) - used)

    def test_the_scan_reports_a_planted_violation(self) -> None:
        planted = (
            "from boilerplate.cli import cli\n"
            "def test_x(mocker, monkeypatch):\n"
            '    mocker.patch("boilerplate.cli.utils.compute_composition")\n'
            '    monkeypatch.setattr(cli, "Display", object())\n'
            '    mocker.patch("boilerplate.cli.commands.new.sys.stdin")\n'
        )

        assert violations(planted) == [
            "boilerplate.cli.utils.compute_composition",
            "boilerplate.cli.cli.Display",
        ]
