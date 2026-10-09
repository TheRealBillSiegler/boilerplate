# Testing patterns

Root `AGENTS.md` (`## Testing`) holds the structural rules. This file holds the repo-specific patterns established in this suite; follow them rather than inventing alternatives.

## Established patterns

| Pattern | Usage |
| ------- | ----- |
| In-process CLI invocation | `typer.testing.CliRunner` via the `typer_cli_runner` fixture: `result = typer_cli_runner.invoke(app, ["new", ...])`; assert on `result.exit_code` and `result.output`. Primary way to test command modules. |
| Subprocess CLI invocation | `subprocess_cli_runner` fixture (runs `python -m boilerplate` with UTF-8 env) for true end-to-end behavior — log formatting, exit codes, stdout/stderr together. Integration tests wrap it in `CliResult`/`CliTestHelper`. The scenarios call `run_boilerplate` from `builders.py` instead: their module-scoped fixtures cannot use a function-scoped fixture. |
| Mock at boundary | `mocker.patch("boilerplate.cli.commands.new.Composer")`; assert via `.return_value.render.call_args` / `.assert_called_once()`. Patch where the name is *used*, not where it's defined. |
| Patch a module symbol | `monkeypatch.setattr(cli, "Settings", fake_settings)` to swap a collaborator the command imports; combine with `CliRunner` to exercise the callback. |
| `pytest.raises` | Prefer `pytest.raises(Error, match=r"...")` when asserting message content; bare form is fine when only the type matters. |
| Env manipulation | `monkeypatch.setenv` / `monkeypatch.delenv` for `BOILERPLATE_*`; never mutate `os.environ` directly. The autouse `clear_boilerplate_env` fixture strips `BOILERPLATE_*` between tests. |
| Logging assertions | stdlib logging only — no `structlog`, no `caplog`. Unit tests inspect handler config directly (`logging.getLogger("boilerplate").level`, `root.handlers[0]`); integration tests scan subprocess output for `[DEBUG]`/`[INFO]` markers. Reset with the `reset_logging` autouse fixture. |
| Snapshot output | Rich/console output asserted with syrupy: `assert result == snapshot`, module marked `pytestmark = [pytest.mark.snapshot]`, refresh with `--snapshot-update`. For ad-hoc capture, the `captured_display` fixture (a `Display` wired to `StringIO`). |
| `# noqa: ARG002` | Annotate unused method/fixture parameters required by an interface or for side effects. |
| Cross-module composition scenarios | `tests/integration/boilerplate/composition/scenarios/`, auto-marked `scenario` (deselect with `-m "not scenario"`). They test the composition design across modules against real Copier and git, so they do not mirror one source module; see the README there. |
| Scenario class naming | `TestSubjectHappyPath`, `TestSubjectSadPath`, `TestSubjectBoundary`, or a descriptive `TestSubject...` grouping. |

## Parallelism

The suite runs under pytest-xdist (`-n auto --dist loadgroup`); keep tests worker-isolated. Use `tmp_path` for filesystem state, suffix shared on-disk locations with `PYTEST_XDIST_WORKER` (see `template_factory`), and co-locate stateful groups with `pytest.mark.xdist_group`.

## Plugins

Installed: `pytest-mock`, `pytest-cov`, `pytest-xdist`, `syrupy`. Not installed — do not reach for them or the patterns they imply: `pytest-asyncio`, `pytest-httpx`, `pytest-timeout`, `pytest-randomly`. This is a synchronous Typer CLI: no async tests, no httpx/ASGI.
