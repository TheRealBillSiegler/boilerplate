# Contributing

Contributions are welcome! Here's how to get started.

Please review our [Security policy](./security.md) and [Code of Conduct](https://github.com/TheRealBillSiegler/boilerplate/blob/develop/CODE_OF_CONDUCT.md) before contributing.

## Development setup

Follow [Development environment setup](https://github.com/TheRealBillSiegler/boilerplate/blob/develop/CONTRIBUTING.md#development-environment-setup) in the repository root's CONTRIBUTING.md.

## Development workflow

### Code quality

Run the local gate before pushing — it mirrors CI's lint, typecheck, test, and docs jobs (the package smoke test, ShellCheck, and the new-tests-go-red check are CI-only):

```powershell
uv run python scripts/check.py
```

For the individual ruff, pyright, and pytest commands, see [Running linting and type checking](https://github.com/TheRealBillSiegler/boilerplate/blob/develop/CONTRIBUTING.md#running-linting-and-type-checking). The pipeline these checks feed into is documented in [CI Pipeline](./ci.md#the-local-gate).

### Mutation score ratchet

A separate workflow, [Mutation score](https://github.com/TheRealBillSiegler/boilerplate/blob/develop/.github/workflows/mutation.yml), runs mutmut once a month against the pure algorithmic core (composition, common, models, types, repository, settings, catalog, integrations — not the CLI or the Jinja templates) and checks the result against `tests/mutation-baseline.json` with `scripts/mutation_ratchet.py`: a package's score may rise, never fall, and a drop fails the run. Trigger it manually from the Actions tab (`workflow_dispatch`) for a cheap trial on one package by filling in the `paths` input, e.g. `src/boilerplate/common/`. The workflow never opens a PR or pushes; raising the baseline after a genuine improvement is a human step — download the run's `mutation-scores.json` artifact and copy its contents over `tests/mutation-baseline.json` in an ordinary PR.

### Testing

- Write tests for new features
- Use descriptive test names
- Include integration tests for CLI commands

When you add a test alongside a `src/` change, make it fail against the old code first, then land the fix — the standard red-green cycle. CI enforces this: see [New tests go red](./ci.md#new-tests-go-red) for the mechanics. Renaming a test function in place (same file, new name) looks like adding a new one to that check, so give the renamed test a fresh red run too — moving or renaming the whole file is handled automatically.

### Documentation

- Update relevant documentation
- Add docstrings to new functions/classes
- Include usage examples

## Submitting changes

Follow the [Pull request process](https://github.com/TheRealBillSiegler/boilerplate/blob/develop/CONTRIBUTING.md#pull-request-process).

When you open the pull request:

- Title it as a conventional commit (`type: description`) — a workflow validates PR titles against [conventional-commit types](./ci.md).
- Explain the changes.
- Reference any related issues.

## Code guidelines

See [Code standards](https://github.com/TheRealBillSiegler/boilerplate/blob/develop/CONTRIBUTING.md#code-standards).

## Breaking changes and versioning

When contributing breaking changes, follow Boilerplate's versioning and deprecation policies:

- **CLI changes**: Follow the [Versioning & Compatibility Policy](./versioning.md) — deprecate for at least one minor version before removal
- **Template changes**: Follow [Versioning and migration](../templates-hub/versioning.md) — provide automated migration via Copier scripts
- **Approval & deprecation**: See the [Versioning & Compatibility Policy § Breaking-Change Approval](./versioning.md#breaking-change-approval) for the approval process and deprecation guidelines

## Architecture

See the [Design specifications](../design/README.md) for the architecture.

## Reporting bugs and requesting features

Search [existing GitHub issues](https://github.com/TheRealBillSiegler/boilerplate/issues) first, then [open a new one](https://github.com/TheRealBillSiegler/boilerplate/issues/new) — for a bug, include a clear description, steps to reproduce, and expected vs. actual behavior; for a feature, describe the use case and motivation.

## Reporting a security vulnerability

See the [Security policy](./security.md) — do not open a public issue.

Next: [CI Pipeline](ci.md) — what runs when you push and open your PR.
