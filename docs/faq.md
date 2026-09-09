# Frequently asked questions

## Before you start (prerequisites)

### What do I need before installing Boilerplate?

Nothing — see [Before you start](install.md#before-you-start) for what `uv` provisions for you and what the Windows installer adds.

### Do I need administrator rights?

Only for two `winget` installs on Windows — see [Before you start](install.md#before-you-start).

### Is `-ExecutionPolicy Bypass` in the install command safe?

Yes, it's scoped to that one process — see [Before you start](install.md#before-you-start) for why.

## About Boilerplate

### What does Boilerplate do?

Boilerplate is a command-line tool that generates a new, ready-to-code Python project from a template: run one command and it creates a folder with your source layout, tests, dependency configuration, and editor settings already wired together and consistent across your team. Its distinguishing feature is composition — you can layer multiple templates (for example, a base project plus a Streamlit add-on) into a single generated project with one merged set of setup questions, instead of running separate tools for each piece.

### How is this different from applying multiple Copier templates to one project?

Copier can apply several independent templates to one project (one answers file each), which works when the templates touch disjoint files. Boilerplate adds author-declared composition (`extends`) on top of Copier: one command, one merged question set, and deterministic precedence when layers overlap the same files. See [Why Boilerplate?](why.md) for the full comparison.

### How do I get accessible, color-free output?

Set `BOILERPLATE_ACCESSIBLE=1` (or the standard `NO_COLOR`) — see [Environment variables](cli.md#environment-variables).

## Security

### How do I report a security vulnerability?

Do **not** open a public GitHub issue. Report vulnerabilities privately by following the [Security policy](governance/security.md). This keeps details confidential until a fix is available.

## More resources

- **[CLI Reference](cli.md)** - Complete command documentation
- **[Templates Hub](templates-hub/index.md)** - Available project templates
- **[Development Environment](environment/index.md)** - Toolchain overview
- **`uv`**: [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)
- **`ruff`**: [https://docs.astral.sh/ruff/](https://docs.astral.sh/ruff/)
- **`pyright`**: [https://github.com/microsoft/pyright](https://github.com/microsoft/pyright)
- **`code` (VS Code)**: [https://code.visualstudio.com/docs](https://code.visualstudio.com/docs)
- **`pytest`**: [https://docs.pytest.org/](https://docs.pytest.org/)
- **`pyproject.toml`**: [https://packaging.python.org/en/latest/guides/writing-pyproject-toml/](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)

## Support

### Where can I get help?

- **Issues**: Report bugs and feature requests on GitHub
- **Troubleshooting**: See our [troubleshooting guide](troubleshooting.md) for common issues
- **Source Code**: Explore the implementation on GitHub

### How do I report a bug?

Search [existing GitHub issues](https://github.com/TheRealBillSiegler/boilerplate/issues) first, then [open a new one](https://github.com/TheRealBillSiegler/boilerplate/issues/new) with a clear description, steps to reproduce, and expected vs. actual behavior.

### How do I request a feature?

[Open a new GitHub issue](https://github.com/TheRealBillSiegler/boilerplate/issues/new) describing the use case and motivation.

### Can I contribute to the project?

Yes! See our [contributing guide](governance/contributing.md) for details on development setup, code standards, and the review process.
