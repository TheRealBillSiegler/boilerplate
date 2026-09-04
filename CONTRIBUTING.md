# Contributing to Boilerplate

Thank you for your interest in contributing to Boilerplate! This guide will help you get started.

## Development Environment Setup

1. Install [uv](https://docs.astral.sh/uv/) (the project's package manager).
2. Clone the repository and install dependencies:

   ```bash
   git clone <repo-url>
   cd boilerplate
   uv sync
   ```

3. Verify your setup by running tests and linting:

   ```bash
   uv run pytest
   uv run ruff check .
   uv run pyright
   ```

## Code Standards

Key points, enforced by ruff and pyright in CI:

- **Python 3.12+** with full type hints on public APIs.
- **Google-style docstrings** (required for mkdocstrings compatibility).
- **One class per file**, even if the class is small.
- **No relative imports** (enforced by ruff).
- **Pydantic `BaseModel`** at boundaries; dataclasses or plain classes for internals.
- Stdlib **`logging.getLogger(__name__)`** for logging, never `print`.

See the [Contributing guide](docs/governance/contributing.md) on the docs site for the full development workflow, versioning policy, and breaking-change process.

## Running Tests

```bash
uv run pytest                 # Run all tests
uv run pytest -m "not slow"   # Skip slow tests
```

Tests must mirror the `src/` directory structure under `tests/`. For example:
`src/boilerplate/cli/cli.py` -> `tests/boilerplate/cli/test_cli.py`

## Running Linting and Type Checking

```bash
uv run ruff check .    # Lint
uv run ruff format .   # Format
uv run pyright         # Type check (strict mode)
```

All code must pass ruff and pyright cleanly before submission.

## Branch Model

`develop` is the integration branch: all feature and fix branches are cut from it and merged back into it. It is the default branch for day-to-day work.

`main` is release-only. It advances exclusively via a maintainer's manual merge from `develop` when cutting a release — there is no automated promotion. See [RELEASING.md](RELEASING.md) for the full release checklist.

Cutting a branch from `main` instead of `develop` is incorrect and will cause your work to diverge from the integration line.

## Decisions

Decision authority rests with the maintainers listed in [CODEOWNERS](CODEOWNERS).

## Pull Request Process

1. **Create a feature branch** from `develop`.
2. **Use conventional commits** for all commit messages:

   ```text
   <type>[optional scope]: <description>
   ```

   Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`

3. **Include tests** for new functionality. Tests should document behavior, not implementation.
4. **Ensure CI passes** -- all linting, type checking, and tests must be green. Run the same checks locally first with `uv run python scripts/check.py`; the pipeline itself is documented in [docs/governance/ci.md](docs/governance/ci.md).
5. **Keep PRs focused** -- one feature or fix per PR.

## Reporting Issues

Open a GitHub issue with a clear description, steps to reproduce, and expected vs. actual behavior.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
