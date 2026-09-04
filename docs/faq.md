# Frequently asked questions

## Before you start (prerequisites)

### What do I need before installing Boilerplate?

Nothing needs to be preinstalled to use Boilerplate itself — `uv` manages Python automatically. The Windows automated installer (`install.ps1`) also installs Git and VS Code via `winget` if they are not already present.

### Do I need administrator rights?

Only for the `winget` steps that install Git and VS Code. The Boilerplate tool itself installs into your user profile (`%USERPROFILE%\.local\bin`) and requires no elevated permissions.

### Is `-ExecutionPolicy Bypass` in the install command safe?

Yes. The `-ExecutionPolicy Bypass` flag applies only to that single PowerShell process — it does not change your machine's execution policy or any persistent setting. Once the installer exits, your normal policy is back in effect.

## About Boilerplate

### What does Boilerplate do?

Boilerplate is a command-line tool that generates a new, ready-to-code Python project from a template: run one command and it creates a folder with your source layout, tests, dependency configuration, and editor settings already wired together and consistent across your team. Its distinguishing feature is composition — you can layer multiple templates (for example, a base project plus a Streamlit add-on) into a single generated project with one merged set of setup questions, instead of running separate tools for each piece.

### How is this different from applying multiple Copier templates to one project?

Copier can apply several independent templates to one project (one answers file each), which works when the templates touch disjoint files. Boilerplate adds author-declared composition (`extends`) on top of Copier: one command, one merged question set, and deterministic precedence when layers overlap the same files. See [Why Boilerplate?](why.md) for the full comparison.

### How do I get accessible, color-free output?

Set `BOILERPLATE_ACCESSIBLE=1` to force color-free output — equivalent to `--color never`. The standard `NO_COLOR` environment variable is also respected.

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
