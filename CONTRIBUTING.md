# Contributing to Boilerplate

This file covers environment setup, code standards, tests, branching, and the pull request process.

## Development environment setup

1. Install [uv](https://docs.astral.sh/uv/) (the project's package manager).
2. Clone the repository and install dependencies:

   ```bash
   git clone https://github.com/TheRealBillSiegler/boilerplate.git
   cd boilerplate
   uv sync
   ```

3. Verify your setup with the local check:

   ```bash
   uv run python scripts/check.py
   ```

   It mirrors CI's `check` job, documented in [CI Pipeline](docs/governance/ci.md#the-local-check); a failure here is a failure there.

## Code standards

Key points, enforced by ruff and pyright in CI:

- **Python 3.12+** with full type hints on public APIs.
- **Google-style docstrings** (required for mkdocstrings compatibility).
- **One class per file**, even if the class is small.
- **No relative imports** (enforced by ruff).
- **Pydantic `BaseModel`** at boundaries; dataclasses or plain classes for internals.
- Stdlib **`logging.getLogger(__name__)`** for logging, never `print`.

Full conventions: [AGENTS.md](AGENTS.md). See the [Contributing guide](docs/governance/contributing.md) on the docs site for the full development workflow, versioning policy, and breaking-change process.

## Running tests

```bash
uv run pytest                 # Run all tests
uv run pytest -m "not slow"   # Skip slow tests
```

Tests must mirror the `src/` directory structure under `tests/` -- for example, `src/boilerplate/cli/cli.py` maps to `tests/boilerplate/cli/test_cli.py`.

## Running linting and type checking

```bash
uv run ruff check --no-fix .   # Lint, CI-equivalent (drop --no-fix to auto-fix locally)
uv run ruff format --check .   # Format check, CI-equivalent (drop --check to reformat locally)
uv run pyright                 # Type check (strict mode)
```

All code must pass ruff and pyright cleanly before submission. `uv run python scripts/check.py` runs all of the above plus the full test suite and the docs build in one step.

## Branch model

`develop` is the integration branch: all feature and fix branches are cut from it and merged back into it. It is the default branch for day-to-day work.

`main` is release-only. It moves only when a release is cut: merging the release PR on `develop` tags the release, and a workflow fast-forwards `main` to that tag. See [RELEASING.md](RELEASING.md) for the full release checklist.

Cutting a branch from `main` instead of `develop` is incorrect and will cause your work to diverge from the integration line.

## Decisions

Decision authority rests with the project's maintainer, listed in [CODEOWNERS](CODEOWNERS).

## Pull request process

1. **Create a feature branch** from `develop`.
2. **Use conventional commits** for commit messages and for the PR title, which becomes the subject of the squash commit on `develop`. See [AGENTS.md § Commits](AGENTS.md#commits) for the format and type list.
3. **Include tests** for new functionality. Tests should document behavior, not implementation.
4. **Ensure CI passes** -- all linting, type checking, and tests must be green. Run the same checks locally first with `uv run python scripts/check.py`; the pipeline itself is documented in [docs/governance/ci.md](docs/governance/ci.md).
5. **Keep PRs focused** -- one feature or fix per PR.

## Reporting issues

See [Reporting bugs and requesting features](docs/governance/contributing.md#reporting-bugs-and-requesting-features) on the docs site.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE), except contributions to the files under `src/boilerplate/templates/`, which are licensed under the [MIT No Attribution License](src/boilerplate/templates/LICENSE) (MIT-0).
