# Development environment

Boilerplate projects include a complete, modern Python development environment. This section documents that **Development Environment** and its parts: the **Toolchain**, the everyday **Workflow**, the **Project Layout**, its **Configuration**, and the **Guardrails** that enforce quality.

## Toolchain

Boilerplate fills the core of the everyday development loop — one curated, preconfigured tool for each part below.

**The slot model.** A development environment decomposes into recurring roles — slots — such as runtime, dependency management, lint/format, types, tests, and editor. Boilerplate's stance: fill each inner-loop slot with exactly one opinionated tool (uv, ruff, pyright, pytest, VS Code) rather than offering options. See [The Development Environment Landscape](../design/dev-environment-landscape.md) for the full taxonomy.

### ![uv Logo](../assets/uv.svg){ style="height: 1em; vertical-align: middle;" } uv

**Dependency & environment manager.** An extremely fast package and project manager (written in Rust) that installs and pins Python, manages your virtual environment, and keeps installs reproducible from `pyproject.toml` — day to day, `uv sync`, `uv add <pkg>`, `uv remove <pkg>`. [Official docs](https://docs.astral.sh/uv/)

<div class="brand-mark" markdown>
![I found reproducibility in Boilerplate.](../assets/boilerplate_found_reproducibility.svg){ width="420" }
</div>

### ![Ruff Logo](../assets/ruff_bolt.svg){ style="height: 1em; vertical-align: middle;"} Ruff

**Linter & formatter.** One fast tool (also Rust) for both jobs — enforces PEP 8, docstrings, and naming, auto-fixes what it can, and formats on save, so style stays out of your way. [Official docs](https://docs.astral.sh/ruff/)

### ![Pyright Logo](../assets/PyrightSmall_NoBackground.png){ style="height: 1em; vertical-align: middle;"} Pyright

**Type checker.** Catches type errors as you type — live in VS Code via Pylance — so mistakes surface early instead of at runtime. [On GitHub](https://github.com/microsoft/pyright)

### ![Pytest Logo](../assets/pytest.png){ style="height: 1em; vertical-align: middle;"} Pytest

**Test runner.** Discovers and runs your tests from the command line or the VS Code Test Explorer, with fixtures, parametrization, and coverage already wired in. [Official docs](https://docs.pytest.org/)

### ![VS Code Logo](../assets/vscode.svg){ style="height: 1em; vertical-align: middle;"} VS Code

**Editor.** Your workspace, pre-wired so the rest of the toolchain just works — format-on-save, live type hints, and test discovery out of the box. [Setup guide](vscode.md)

### ![Git Logo](../assets/git.svg){ style="height: 1em; vertical-align: middle;" } Git

**Version control.** Tracks your project's history, makes branching and experimentation safe, and syncs with remotes like GitHub. [Official docs](https://git-scm.com/doc)

## Typical developer workflow

### 1. Start or clone a project

**New project**:

1. Plop down some project files using a template:

    ```powershell
    boilerplate new <template>
    ```

2. Add some dependencies:

    ```powershell
    uv add pandas pydantic
    ```

    !!! tip
        Add `--dev` to add dev only dependencies.

**Existing project**:

1. Clone the project:

    ```powershell
    git clone <repo>
    ```

2. Synchronize the dependencies:

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

!!! warning
    Opening a cloned project before `uv sync` can leave VS Code without a detected interpreter — see [the fix](vscode.md#troubleshooting-the-interpreter-isnt-detected).

### 3. Develop & test

- **Ruff** handles styling and lint checks in real-time and formats on save
- **Pyright** highlights type issues as you code
- **Pytest** runs your automated tests (via the command line or the VS Code Test Explorer)

### 4. Git workflow

```powershell
git commit -m "Descriptive message"
git push
```

Regular commits and pushes help maintain a well-versioned codebase.

### 5. Build & publish (if applicable)

```powershell
uv build
uv publish
```

Use these commands to distribute your package.

## Project layout

A consistent project layout helps everyone understand the codebase at a glance. Here's our standard structure:

```text
root/
├─ .vscode/
│    ├─ extensions.json
│    └─ settings.json
├─ src/
│  └─ your_package/
│     ├─ __init__.py
│     └─ module.py
├─ tests/
│    └─ your_package/
│        └─ test_module.py
├─ notebooks/
├─ .gitignore
├─ pyproject.toml
└─ README.md
```

- **`.vscode/`**: Local editor settings and recommended extensions ensure a consistent VS Code experience
- **`src/`**: Houses production code. Separating it from tests and configuration files prevents naming conflicts and maintains clarity
- **`src/your_package/`**: Contains the main application code, including sub-packages and modules
- **`tests/`**: Mirrors the structure of your main package with corresponding test files
- **`.gitignore`**: Lists files and directories (e.g., virtual environments, build artifacts, temporary files, sensitive data) that Git should ignore
- **`README.md`**: Provides an overview of your project's purpose, setup, and usage

## Configuration

### What boilerplate configures for you

Generated projects arrive with the toolchain pre-wired. Beginners can ignore the specifics and just code; the exact configuration is here when you want it.

??? note "The shipped configuration (click to expand)"

    - **Ruff** (`[tool.ruff]`) — `fix = true` and a broad rule set (~26 categories: pyflakes, pycodestyle, isort, pydocstyle with the **Google** convention, annotations, bugbear, pathlib, pyupgrade, and more), plus docstring code formatting. `tests/` and `__init__.py` get sensible per-file ignores.
    - **Pyright** (`[tool.pyright]`) — `typeCheckingMode = "strict"` over `src/` (tests relaxed). Type-checking runs live via Pylance in VS Code; add `pyright` to your dev dependencies to also run it from the CLI.
    - **pytest** (`[tool.pytest.ini_options]`) — `log_cli = true`, with `pytest-cov` and `pytest-mock` in the dev group.
    - **VS Code** (`.vscode/`) — Ruff as the default formatter for Python and notebooks, format-on-save, and pytest discovery enabled. The interpreter isn't pinned; the Python extension auto-detects `.venv` in the workspace root.

    The authoritative configuration is the generated `pyproject.toml` and `.vscode/` — these summaries point you at it, not away from it.

## Guardrails: where quality is enforced

The same checks run at every stage, so local development has full guardrails:

- **Local gates** — the generated `pyproject.toml` configures `ruff`, `pyright` (strict mode over `src/`), and `pytest` so you can validate before committing.

## Where next

- [VS Code](vscode.md) — interpreter selection, extensions, and troubleshooting for the generated `.vscode/` setup.
- [Developer platform architecture](../reference/platform/index.md) — the reference model this environment implements.
