# Boilerplate

**Boilerplate pairs a Python development environment, one tool for each job, with templates that build on one another to stamp out projects.** Use its templates as they are, or put your own standards on top of one instead of forking it. It renders each template with [Copier](https://copier.readthedocs.io/), a tool for project templates, and you don't need to know Copier to use it.

Boilerplate takes care of the setup chores around writing code, the kind developers call yak shaving: a working toolchain and a configured project. You start at the work.

Each pick is the most modern and lightweight option for its job: uv for installing Python and managing dependencies, Ruff for linting and formatting, Pyright in strict mode for type checking, pytest for testing and VS Code as the editor. The templates configure them in `pyproject.toml` and `.vscode/`, so the editor and the command line format code the same way.

**Less yak. More stack.**

New project, dependencies installed, pytest passing.

The [Quickstart](https://therealbillsiegler.github.io/boilerplate/0.4/quickstart/index.md) shows the same steps in text.

[Quickstart](https://therealbillsiegler.github.io/boilerplate/0.4/quickstart/index.md) [Browse Templates Hub](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/index.md)

Coming from Copier?

Start with [Why Boilerplate?](https://therealbillsiegler.github.io/boilerplate/0.4/why/index.md) for the pitch, or go straight to [Template Composition](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/composition/index.md) for the `extends` mechanics.

Already on uv?

`uv init` gives you a package; Boilerplate gives you the judgment around it.

Evaluating Boilerplate?

[Why Boilerplate?](https://therealbillsiegler.github.io/boilerplate/0.4/why/index.md) covers the ethos and the environment; [Implementation Status](https://therealbillsiegler.github.io/boilerplate/0.4/status/index.md) shows what is implemented.

______________________________________________________________________

## Why choose Boilerplate?

- **Instant productivity**

  ______________________________________________________________________

  Scaffold fully configured projects with one command.

- **Locked dependencies**

  ______________________________________________________________________

  `uv.lock` pins the environment, so every machine resolves the same.

- **Toolchain**

  ______________________________________________________________________

  `uv`, `ruff`, and `pytest` arrive preconfigured and ready to go, plus a strict `pyright` configuration checked live via Pylance.

- **Cross-platform**

  ______________________________________________________________________

  Windows 11 installs are automated; Linux/WSL2 and macOS follow the same steps manually.

- **Minimal configuration**

  ______________________________________________________________________

  Defaults from the first render, so there is less setup before you write code.

- **[Template composition](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/composition/index.md)**

  ______________________________________________________________________

  Layer templates with `extends` — one command, one merged question set, deterministic precedence when layers overlap.

Planned

`boilerplate update` — a three-way merge that consumes the lock `boilerplate new` writes to move a generated project to a newer template version — is planned. See the [roadmap](https://therealbillsiegler.github.io/boilerplate/0.4/roadmap/index.md) for sequencing, the [update model design](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-007-update-model/index.md) for the approach, and [Implementation Status](https://therealbillsiegler.github.io/boilerplate/0.4/status/index.md) for what exists today.

______________________________________________________________________

## Mini quickstart

```powershell
# Install (-ExecutionPolicy Bypass is per-process only)
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/TheRealBillSiegler/boilerplate/v0.4.0/scripts/install.ps1 | iex"
# Scaffold
boilerplate new project my-first-project
```

With [Git](https://git-scm.com/) and [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uv tool install git+https://github.com/TheRealBillSiegler/boilerplate.git@v0.4.0
boilerplate new project my-first-project
```

Then run `uv run pytest` inside `my-first-project`. The [Quickstart](https://therealbillsiegler.github.io/boilerplate/0.4/quickstart/index.md) walks every step with expected output, and [Installation](https://therealbillsiegler.github.io/boilerplate/0.4/install/#setup-options) covers manual setup.

______________________________________________________________________

## Explore further

- **[Quickstart](https://therealbillsiegler.github.io/boilerplate/0.4/quickstart/index.md)**

  ______________________________________________________________________

  Scaffold, install, and run your first project.

- **[CLI reference](https://therealbillsiegler.github.io/boilerplate/0.4/cli/index.md)**

  ______________________________________________________________________

  Commands, options, and examples.

- **[Installation](https://therealbillsiegler.github.io/boilerplate/0.4/install/index.md)**

  ______________________________________________________________________

  Manual setup for Linux, WSL2, and macOS.

- **[Templates Hub](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/index.md)**

  ______________________________________________________________________

  Explore available templates and where to start.

- **[VS Code configuration](https://therealbillsiegler.github.io/boilerplate/0.4/environment/vscode/index.md)**

  ______________________________________________________________________

  Set up the recommended editor experience.

- **[Toolchain deep dive](https://therealbillsiegler.github.io/boilerplate/0.4/environment/index.md)**

  ______________________________________________________________________

  See how the tools fit together.

- **[Developer platform architecture](https://therealbillsiegler.github.io/boilerplate/0.4/reference/platform/index.md)**

  ______________________________________________________________________

  The reference model and standards.

- **[Contributing](https://therealbillsiegler.github.io/boilerplate/0.4/governance/contributing/index.md)**

  ______________________________________________________________________

  Development setup and coding standards; see also the [Security policy](https://therealbillsiegler.github.io/boilerplate/0.4/governance/security/index.md).

- **[FAQ](https://therealbillsiegler.github.io/boilerplate/0.4/faq/index.md) & [Troubleshooting](https://therealbillsiegler.github.io/boilerplate/0.4/troubleshooting/index.md)**

  ______________________________________________________________________

  Answers to common questions and fixes for common setup issues.

______________________________________________________________________
