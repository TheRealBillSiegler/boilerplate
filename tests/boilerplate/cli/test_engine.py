"""The engine module names what Typer itself raises and pushes.

The import line in ``boilerplate.cli.engine`` is the tripwire for an upstream
rename; these tests assert the two facts the CLI relies on: the usage-error
class is the one the parser raises, and the context lookup sees the context
Typer pushes.
"""

import typer
from typer.testing import CliRunner

from boilerplate.cli import cli
from boilerplate.cli.engine import UsageError, get_current_context


class TestUsageError:
    def test_is_what_the_parser_raises(self, typer_cli_runner: CliRunner) -> None:
        result = typer_cli_runner.invoke(
            cli.app, ["--bogus-flag"], standalone_mode=False
        )

        assert isinstance(result.exception, UsageError)


class TestGetCurrentContext:
    def test_sees_the_context_typer_pushes(self) -> None:
        app = typer.Typer()
        seen: list[object] = []

        @app.command()
        def record(ctx: typer.Context) -> None:
            seen.append((ctx, get_current_context()))

        result = CliRunner().invoke(app, [])

        assert result.exit_code == 0, result.output
        ctx, current = seen[0]
        assert current is ctx
