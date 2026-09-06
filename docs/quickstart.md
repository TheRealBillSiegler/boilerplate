# Quickstart

**Less yak. More stack.** Scaffold fully configured, dependency-locked Python projects with **Boilerplate**.

This guide shows you how to:

1. Install Boilerplate
2. Scaffold your first project
3. Follow the standard development workflow

---

## Install Boilerplate

=== "Windows 11 (Automated)"

    ```powershell
    powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/TheRealBillSiegler/boilerplate/main/scripts/install.ps1 | iex"
    ```

    Note: `-ExecutionPolicy Bypass` applies to this process only; it does not change your machine policy.

    The script installs and configures:

    - **Git** (if missing)
    - **Visual Studio Code** (if missing), with recommended extensions (Ruff, Jupyter, etc.)
    - **uv** for dependency and environment management
    - The **boilerplate** package (installed from its public Git repository)

    On Windows 10 (no `winget` by default)? Use the [manual setup path](install.md#setup-options) instead.

=== "Linux, macOS, or WSL"

    Manual setup — see the [Installation Guide](install.md#setup-options) for the steps.

---

### Verify installation

```bash
boilerplate version
```

Expected: prints a semantic version and exits 0.

!!! tip
    If verification fails, check [Troubleshooting](troubleshooting.md) or the [FAQ](faq.md).

---

### What's included

Boilerplate standardizes a fast, type‑safe workflow with:

- [uv](https://docs.astral.sh/uv/) — dependency, Python, and virtualenv management
- [ruff](https://docs.astral.sh/ruff/) — formatter and linter
- [pyright](https://github.com/microsoft/pyright) — a strict configuration ships; type-checked live in VS Code via Pylance
- [pytest](https://docs.pytest.org/) — testing framework
- [boilerplate](cli.md) CLI + Copier — template‑driven scaffolding
- [git](https://git-scm.com/doc) — source control

---

## Scaffold a new project

Generate a clean, opinionated project structure, accepting every default in one shot:

```bash
boilerplate new project my-first-project -n
```

Expected: creates my-first-project/ with:

- src/my_first_project/module.py (with an `add(a, b)` function)
- tests/my_first_project/test_module.py (with tests for `add`)
- pyproject.toml, README.md, .vscode/, and notebooks/
- `__init__.py` with a version string
- additional files

Want to set the project name, description, dependencies, and author yourself? Drop `-n` and answer the 7 prompts interactively (each has a sensible default — press Enter to accept it):

```bash
boilerplate new project my-first-project
```

Need a web front‑end? Use the Streamlit template:

```bash
boilerplate new streamlit my-streamlit-app
```

Pin to an exact template version when needed (check the current version with `boilerplate list`; the bundled `project` template is currently at `0.2.0`):

```bash
boilerplate new project@0.2.0 my-versioned-project
```

> **Note:** Upgrading a generated project to a newer template version (`boilerplate update`) is currently design-only — see [design/adr-007-update-model.md](design/adr-007-update-model.md) for the planned approach.

Non‑interactive (accept defaults) and overwrite existing destination:

```bash
boilerplate new project -n -f my-first-project
```

!!! warning "`--force` / `-f` overwrites without confirmation"
    If `my-first-project` already exists, `--force` silently overwrites any files the template writes there, without asking first. It does not delete files the template doesn't manage. There is no undo — make sure any file the template will touch doesn't hold work you want to keep.

### Available templates

- `project` — standard Python application/library/project ([Guide](templates-hub/project.md) · [Hub](templates-hub/index.md))
- `streamlit` — data apps & dashboards ([Guide](templates-hub/streamlit/streamlit.md) · [Hub](templates-hub/index.md) · [Containers](templates-hub/streamlit/deployment/containers/index.md))

---

## Work on an existing project

Clone and synchronize dependencies:

```bash
git clone <repo-url>
cd <repo-name>
uv sync
```

Expected: dependencies installed, virtual environment created

VS Code not detecting the interpreter? See [VS Code setup](environment/vscode.md).

Update to latest compatible versions when needed:

```bash
uv sync --upgrade
```

---

## Development workflow

1. **Enter the project directory**

    ```bash
    cd my-first-project
    ```

1. **Open the project in VS Code**

    ```bash
    code .
    ```

    Or: VS Code → File → Open Folder → select my-first-project

1. **Format & lint**

    ```bash
    uv run ruff format .
    uv run ruff check .
    ```

    Or: format on save in VS Code

1. **Type‑check**

    ```bash
    uv run pyright
    ```

    Or: check inline diagnostics in VS Code

1. **Run tests**

    ```bash
    uv run pytest
    ```

    !!! tip
        Use `-q` for quiet; Use `-vv` for detailed diagnostics.

    Expected: tests run; all passed; exit 0.

??? question "Tests not discovered or not running in VS Code?"
    - **Cause:** The test framework is not enabled or the environment is not activated.
    - **Solution:**
        1. Ensure you have run `uv sync` and activated the environment.
        2. In VS Code, open the Command Palette and run “Python: Discover Tests”.
        3. Select `pytest` as the test framework.
    - **Verify:**
        - Tests appear in the VS Code Test Explorer.
        - Running `uv run pytest` in the terminal should show all tests passing.

---

## Project layout at a glance

```text
root/
├─ .vscode/
├─ src/
│  └─ your_package/
├─ tests/
│  └─ your_package/
├─ notebooks/
├─ .gitignore
├─ pyproject.toml
└─ README.md
```

- `src/` contains application code; `tests/` mirrors it for test coverage
- `.vscode/` pins editor settings and recommendations
- `pyproject.toml` centralizes metadata, dependencies, and tool configs (ruff, pyright, etc.); `uv` reads it to produce deterministic installs

---

## Next steps

- **[Installation Guide](install.md)** — platform‑specific installation details  
- **[Templates Hub](templates-hub/index.md)** — pick a starting point  
- **[Commands](cli.md)** — every command and option explained  
- **[VS Code Guide](environment/vscode.md)** — tips for a friction‑free IDE experience

Enjoy building with Boilerplate! ✨
