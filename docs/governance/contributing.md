# Contributing

Contributions are welcome! Here's how to get started.

Please review our [Security policy](./security.md) before contributing.

## Development setup

1. **Clone the repository**:

    ```powershell
    git clone https://github.com/TheRealBillSiegler/boilerplate.git
    cd boilerplate
    ```

2. **Install dependencies**:

    ```powershell
    uv sync --group dev
    ```

3. **Run tests**:

    ```powershell
    uv run pytest
    ```

## Development workflow

### Code quality

All code must pass quality checks:

```powershell
# Format code
uv run ruff format

# Lint code
uv run ruff check

# Type check
uv run pyright

# Run tests
uv run pytest
```

Or run everything at once — the same steps CI runs — with the local gate:

```powershell
uv run python scripts/check.py
```

The pipeline these checks feed into is documented in [CI Pipeline](./ci.md).

### Testing

- Write tests for new features
- Use descriptive test names
- Include integration tests for CLI commands

### Documentation

- Update relevant documentation
- Add docstrings to new functions/classes
- Include usage examples

## Submitting changes

1. **Create a feature branch**:

    ```powershell
    git checkout -b feature/your-feature-name
    ```

2. **Make your changes**:
    - Follow existing code patterns
    - Include tests
    - Update documentation

3. **Run quality checks**: `uv run python scripts/check.py` (see [Code quality](#code-quality) for the individual commands)

4. **Commit and push**:

    ```powershell
    git add .
    git commit -m "feat: your feature description"
    git push origin feature/your-feature-name
    ```

5. **Create a pull request**:
    - Title it as a conventional commit (`type: description`) — a workflow validates PR titles against [conventional-commit types](./ci.md)
    - Explain the changes
    - Reference any related issues

## Code guidelines

- Use type hints consistently
- Follow PEP 8 (enforced by Ruff)
- Prefer composition over inheritance
- Write clear, descriptive names
- Keep functions focused and small

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
