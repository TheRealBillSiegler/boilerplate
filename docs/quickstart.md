# Quickstart

**Less yak. More stack.** Scaffold fully configured, dependency-locked Python projects with **Boilerplate**.

This guide shows you how to:

1. Install Boilerplate
2. Scaffold your first project
3. Follow the standard development workflow

---

## Install Boilerplate

Install Boilerplate before you start this guide — see [Setup options](install.md#setup-options) for the steps on your platform.

---

### Verify installation

See [Verify installation](install.md#verify-installation).

---

### What's included

Boilerplate standardizes a fast, type-safe toolchain — see [Toolchain](environment/index.md#toolchain) for what's in it.

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

> **Note:** Upgrading a generated project to a newer template version (`boilerplate update`) is currently design-only — see the [roadmap](roadmap.md) for the planned approach.

Non‑interactive (accept defaults) and overwrite existing destination:

```bash
boilerplate new project -n -f my-first-project
```

!!! warning "`--force` / `-f` overwrites without confirmation"
    If `my-first-project` already exists, `--force` silently overwrites any files the template writes there, without asking first. It does not delete files the template doesn't manage. There is no undo — make sure any file the template will touch doesn't hold work you want to keep.

### Available templates

Boilerplate ships two first-party templates today — see [Choose a template](templates-hub/index.md#choose-a-template) for what each one adds and when to reach for it.

---

## Development workflow

1. **Enter the project directory**

    ```bash
    cd my-first-project
    ```

1. **Add a dependency**

    ```bash
    uv add pandas pydantic
    ```

    !!! tip
        Add `--dev` for a development-only dependency.

1. **Open the project in VS Code**

    ```bash
    code .
    ```

    Or: VS Code → File → Open Folder → select my-first-project

1. **Run tests**

    ```bash
    uv run pytest
    ```

    !!! tip
        Use `-q` for quiet; Use `-vv` for detailed diagnostics.

    Expected: tests run; all passed; exit 0.

---

## Project layout at a glance

See [Project structure](templates-hub/project.md#project-structure) for the generated tree and what each part is for.

---

## Next steps

- **[Installation Guide](install.md)** — platform‑specific installation details  
- **[Templates Hub](templates-hub/index.md)** — pick a starting point  
- **[Commands](cli.md)** — every command and option explained  
- **[VS Code Guide](environment/vscode.md)** — tips for a friction‑free IDE experience

Enjoy building with Boilerplate! ✨
