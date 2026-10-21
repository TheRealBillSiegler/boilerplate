# Quickstart

**Less yak. More stack.** Scaffold fully configured, dependency-locked Python projects with **Boilerplate**.

This guide shows you how to:

1. Scaffold your first project
1. Run the dev loop

This guide scaffolds your first project and runs its tests. Install Boilerplate first — [Setup options](https://therealbillsiegler.github.io/boilerplate/0.4/install/#setup-options) and [Verify installation](https://therealbillsiegler.github.io/boilerplate/0.4/install/#verify-installation) — and skim the [toolchain](https://therealbillsiegler.github.io/boilerplate/0.4/environment/#toolchain) it standardizes.

______________________________________________________________________

## Scaffold a new project

Generate a clean, opinionated project structure, accepting every default in one shot:

```bash
boilerplate new project my-first-project --non-interactive
```

Expected: creates my-first-project/ with:

- src/my_first_project/module.py (with an `add(a, b)` function)
- tests/my_first_project/test_module.py (with tests for `add`)
- pyproject.toml, README.md, .vscode/, and notebooks/
- `__init__.py` with a version string
- additional files

Want to set the project name, description, dependencies, and author yourself? Drop `--non-interactive` and answer the 9 prompts interactively (each has a sensible default — press Enter to accept it):

```bash
boilerplate new project my-first-project
```

Building a Streamlit app? Use the Streamlit template:

```bash
boilerplate new streamlit my-streamlit-app
```

Pin to an exact template version when needed (check the current version with `boilerplate list`; the bundled `project` template is currently at `0.3.0`):

```bash
boilerplate new project@0.3.0 my-versioned-project
```

Planned

`boilerplate update` — moving a generated project to a newer template version — is planned; see the [roadmap](https://therealbillsiegler.github.io/boilerplate/0.4/roadmap/index.md) for sequencing and the [update model design](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-007-update-model/index.md) for the approach.

Non-interactive (accept defaults) and overwrite a non-empty destination:

```bash
boilerplate new project --non-interactive -f my-first-project
```

`--force` / `-f` overwrites without confirmation

If `my-first-project` already exists, `--force` silently overwrites any files the template writes there, without asking first. It does not delete files the template doesn't manage. There is no undo — make sure any file the template will touch doesn't hold work you want to keep.

### Available templates

Boilerplate ships two first-party templates today — see [Choose a template](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/#choose-a-template) for what each one adds and when to reach for it.

______________________________________________________________________

## The dev loop

The dev loop is the cycle you repeat inside a project; the [Development Environment guide](https://therealbillsiegler.github.io/boilerplate/0.4/environment/#the-dev-loop) covers it in full.

1. **Enter the project directory**

   ```bash
   cd my-first-project
   ```

1. **Add a dependency**

   ```bash
   uv add pandas pydantic
   ```

   Tip

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

   Tip

   Use `-q` for quiet; Use `-vv` for detailed diagnostics.

   Expected: tests run; all passed; exit 0.

______________________________________________________________________

## Project layout at a glance

See [Project structure](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/project/#project-structure) for the generated tree and what each part is for.

______________________________________________________________________

## Next steps

- **[Installation Guide](https://therealbillsiegler.github.io/boilerplate/0.4/install/index.md)** — platform-specific installation details
- **[Templates Hub](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/index.md)** — pick a starting point
- **[Commands](https://therealbillsiegler.github.io/boilerplate/0.4/cli/index.md)** — every command and option explained
- **[VS Code Guide](https://therealbillsiegler.github.io/boilerplate/0.4/environment/vscode/index.md)** — tips for a friction-free experience in your IDE (code editor)

Enjoy building with Boilerplate! ✨
