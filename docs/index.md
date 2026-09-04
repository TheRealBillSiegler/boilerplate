---
description: An ethos made executable. Scaffold Python projects fast with uv, Ruff, Pyright, and pytest—all preconfigured and ready to ship.
---

# Boilerplate

**An ethos made executable** — Start fast. Stay consistent. Reproduce anywhere.

A Python development environment and project scaffolder for teams. Preconfigured uv, Ruff, Pyright, and pytest give you a fast start, locked dependencies, and consistent workflows. Generate, sync, test, and ship — without wrestling with PATH, venvs, or lint configs.

**Less yak. More stack.**

[Quickstart](quickstart.md){ .md-button .md-button--primary } [Browse Templates Hub](templates-hub/index.md){ .md-button }

!!! tip "Coming from Copier?"
    Start with [Why Boilerplate?](why.md) for the pitch, jump into the [Quickstart](quickstart.md) to try it, or go straight to [Template Composition](templates-hub/composition.md) for the `extends` mechanics.

> Pains this fixes:
>
> - Environments drift across machines and teammates
> - PATH and interpreter confusion in VS Code
> - Tool mismatch and inconsistent configs

---

## Why choose Boilerplate?

| Benefit | What it means for you |
|---------|-----------------------|
| :material-rocket-launch: **Instant productivity** | Scaffold fully configured projects with one command. |
| :material-package-variant-closed: **Locked dependencies** | `uv.lock` pins the environment, so every machine resolves the same. |
| :material-tools: **Curated toolchain** | Integrated tools (`uv`, `ruff`, `pyright`, `pytest`) arrive *preconfigured* and ready to go. |
| :material-earth: **Cross‑platform** | Windows 11 installs are automated; Linux/WSL2 and macOS follow the same steps manually. |
| :material-cog: **Minimal configuration** | Sensible defaults out of the box—less setup before you write code. |
| :material-puzzle: **[Template composition](templates-hub/composition.md)** | Layer templates with `extends` — one command, one merged question set, deterministic precedence when layers overlap. |

!!! note "Lifecycle & exit"
    Reproducible lock files are planned for roadmap Phase 1; updating an already-generated project to a newer template version (`boilerplate update`, three-way merge) is planned for Phase 3 and consumes the Phase 1 lock. Both are design-only today. See the [update model design](design/adr-007-update-model.md) for the intended approach, and [Implementation Status](status.md) for the full design-vs-code map.

---

## Mini quickstart

```powershell
# Install (Windows 11; -ExecutionPolicy Bypass is per-process only)
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/TheRealBillSiegler/boilerplate/main/scripts/install.ps1 | iex"
# Scaffold
boilerplate new project my-first-project
```

That's the loop: install once, scaffold, then `uv run pytest` inside the new project to watch it pass its own gates. The [Quickstart](quickstart.md) walks every step with expected output; [Installation](install.md#setup-options) covers macOS/Linux and manual setup.

Just want the CLI? `uv tool install git+https://github.com/TheRealBillSiegler/boilerplate.git`

---

## Explore further

- **[Quickstart](quickstart.md)** — scaffold, install, and run your first project.
- **[CLI reference](cli.md)** — commands, options, and examples.
- **[Installation](install.md)** — manual setup for Linux, WSL2, and macOS.
- **[Templates Hub](templates-hub/index.md)** — explore available templates and where to start.
- **[VS Code configuration](environment/vscode.md)** — set up the recommended editor experience.
- **[Toolchain deep dive](environment/index.md)** — see how the tools fit together.
- **[Developer platform architecture](reference/platform/index.md)** — the platform model and standards.
- **[Contributing](governance/contributing.md)** — development setup and coding standards; see also the [Security policy](governance/security.md).
- **[FAQ](faq.md)** and **[Troubleshooting](troubleshooting.md)** — answers to common questions and fixes for common setup issues.
