# Development environment

Boilerplate projects include a complete, modern Python development environment. This section documents that [Development Environment](https://therealbillsiegler.github.io/boilerplate/0.4/design/01-overview/#term-development-environment) and its parts: the [Toolchain](#toolchain), the [**dev loop**](#the-dev-loop), the [Project Layout](#project-layout), and their [Configuration](#configuration).

## Toolchain

Boilerplate fills each slot the dev loop uses with one preconfigured, overridable tool rather than a menu, and the [toolchain](https://therealbillsiegler.github.io/boilerplate/0.4/reference/platform/#the-toolchain) lists the picks. They are set up on your machine, in each project and in your editor — see [A whole environment, one pick per slot](https://therealbillsiegler.github.io/boilerplate/0.4/why/#a-whole-environment-one-pick-per-slot); the [landscape](https://therealbillsiegler.github.io/boilerplate/0.4/design/dev-environment-landscape/index.md) holds the full taxonomy.

### uv

**Dependency & environment manager.** An extremely fast package and project manager (written in Rust) that installs and pins Python, manages your virtual environment, and keeps installs reproducible from `pyproject.toml` — day to day, `uv sync`, `uv add <pkg>`, `uv remove <pkg>`. [Official docs](https://docs.astral.sh/uv/)

### Ruff

**Linter & formatter.** One fast tool (also Rust) for both jobs — enforces PEP 8, docstrings, and naming, auto-fixes what it can, and formats on save, so style stays out of your way. [Official docs](https://docs.astral.sh/ruff/)

### Pyright

**Type checker.** Catches type errors as you type — live in VS Code via Pylance — so mistakes surface early instead of at runtime. [On GitHub](https://github.com/microsoft/pyright)

### Pytest

**Test runner.** Discovers and runs your tests from the command line or the VS Code Test Explorer, with fixtures, parametrization, and coverage already wired in. [Official docs](https://docs.pytest.org/)

### VS Code

**Editor.** Your workspace, pre-wired so the rest of the toolchain just works — format-on-save, live type hints, and test discovery out of the box. [Setup guide](https://therealbillsiegler.github.io/boilerplate/0.4/environment/vscode/index.md) [Official docs](https://code.visualstudio.com/docs)

### Git

**Version control.** Tracks your project's history, makes branching and experimentation safe, and syncs with remotes like GitHub. [Official docs](https://git-scm.com/doc)

## The dev loop

The **dev loop** is the cycle you repeat inside a project, which is test-driven development's red-green-refactor: write a failing test, make it pass with the least code, then refactor with the tests still green. Then run the checks, commit, and start the next turn. Steps 1 and 2 get a project ready; steps 3 and 4 are the loop.

### 1. Start or clone a project

**New project**:

```powershell
boilerplate new <template>
```

Add dependencies as you go — `uv add <pkg>`, or `uv add --dev <pkg>` for a development-only dependency.

**Existing project**:

1. Clone the project:

   ```powershell
   git clone <repo>
   ```

1. Synchronize the dependencies:

   ```powershell
   uv sync
   ```

   This installs or updates dependencies based on your `pyproject.toml`.

   To upgrade dependencies:

   ```powershell
   uv sync --upgrade
   ```

### 2. Open VS Code

```powershell
code .
```

Launch a fully configured editor with linting, auto-formatting, type checks, etc.

Warning

Opening a cloned project before `uv sync` can leave VS Code without a detected interpreter — see [the fix](https://therealbillsiegler.github.io/boilerplate/0.4/environment/vscode/#troubleshooting-the-interpreter-isnt-detected).

### 3. Red, green, refactor

- **Pytest** runs your tests, via the command line or the VS Code Test Explorer. Write a test that fails (red), make it pass with the least code (green), then refactor while it stays green:

  ```powershell
  uv run pytest
  ```

The checks run alongside:

- **Ruff** handles styling and lint checks in real time and formats on save — or run it yourself:

  ```powershell
  uv run ruff format .
  uv run ruff check --fix .
  ```

- **Pyright** highlights type issues as you code — or run it yourself:

  ```powershell
  uv run pyright
  ```

### 4. Commit and repeat

Commit each turn that passes its tests and checks, then start the next one. Many commits make one pull request.

```powershell
git commit
```

## Project layout

A consistent project layout helps everyone understand the codebase at a glance — see [Project structure](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/project/#project-structure) for the generated tree.

- **`.vscode/`**: Local editor settings and recommended extensions ensure a consistent VS Code experience
- **`src/`**: Houses production code. Separating it from tests and configuration files prevents naming conflicts and maintains clarity
- **`src/your_package/`**: Contains the main application code, including sub-packages and modules
- **`tests/`**: Mirrors the structure of your main package with corresponding test files
- **`.gitignore`**: Lists files and directories (e.g., virtual environments, build artifacts, temporary files, sensitive data) that Git should ignore
- **`README.md`**: Provides an overview of your project's purpose, setup, and usage

## Configuration

### What boilerplate configures for you

Generated projects arrive with the toolchain pre-wired. Beginners can ignore the specifics and just code; the exact configuration is here when you want it.

The shipped configuration (click to expand)

- **Ruff** (`[tool.ruff]`) — `fix = true` and a broad rule set (~26 categories: pyflakes, pycodestyle, isort, pydocstyle with the **Google** convention, annotations, bugbear, pathlib, pyupgrade, and more), plus docstring code formatting. `tests/` and `__init__.py` get sensible per-file ignores.
- **Pyright** (`[tool.pyright]`) — `typeCheckingMode = "strict"` over `src/` (tests relaxed). Type-checking runs live via Pylance in VS Code and from the CLI with `uv run pyright`; `pyright` ships in the dev group.
- **pytest** (`[tool.pytest.ini_options]`) — `log_cli = true`, with `pytest-cov` and `pytest-mock` in the dev group.
- **VS Code** (`.vscode/`) — Ruff as the default formatter for Python and notebooks, format-on-save, and pytest discovery enabled. The interpreter isn't pinned; the Python extension auto-detects `.venv` in the workspace root.

The authoritative configuration is the generated `pyproject.toml` and `.vscode/` — these summaries point you at it, not away from it. The [`pyproject.toml` guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) explains the file itself.

## Where next

- [VS Code](https://therealbillsiegler.github.io/boilerplate/0.4/environment/vscode/index.md) — interpreter selection, extensions, and troubleshooting for the generated `.vscode/` setup.
- [Developer platform architecture](https://therealbillsiegler.github.io/boilerplate/0.4/reference/platform/index.md) — the reference model this environment implements.
