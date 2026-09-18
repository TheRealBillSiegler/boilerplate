"""The engine module names what Typer itself raises and pushes.

Both objects come from Typer's private vendored Click, so these tests are the
tripwire for an upstream rename: they fail before any command does.
"""

import typer
from typer.core import TyperCommand
from typer.testing import CliRunner

from boilerplate.cli import cli
from boilerplate.cli.engine import Context, UsageError, get_current_context


class TestUsageError:
    def test_is_what_the_parser_raises(self, typer_cli_runner: CliRunner) -> None:
        result = typer_cli_runner.invoke(
            cli.app, ["--bogus-flag"], standalone_mode=False
        )

        assert isinstance(result.exception, UsageError)

    def test_is_the_base_of_the_public_bad_parameter(self) -> None:
        assert issubclass(typer.BadParameter, UsageError)


class TestContext:
    def test_is_the_base_of_the_public_context(self) -> None:
        assert issubclass(typer.Context, Context)


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

    def test_sees_a_context_entered_by_hand(self) -> None:
        ctx = typer.Context(TyperCommand("stub"))

        with ctx:
            assert get_current_context() is ctx
