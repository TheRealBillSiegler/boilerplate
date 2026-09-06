---
description: An ethos made executable. Scaffold Python projects fast with uv, Ruff, Pyright, and pytest—all preconfigured and ready to ship.
---

# Boilerplate

**An ethos made executable** — Start fast. Stay consistent. Reproduce anywhere.

Almost every Python project starts with work that isn't the work: picking the tools again, copying the last project's config, getting the linter and the type checker to agree on the same rules. Boilerplate is a project scaffolder for teams that want those decisions made once — uv, Ruff, a strict Pyright configuration, and pytest already wired into `pyproject.toml` and `.vscode/` — and for template maintainers who want templates that stack instead of fork.

Already on uv? `uv init` gives you a package; Boilerplate gives you the judgment around it, and lets a base template carry your team's standards under every specialized one. Already on Copier? Your templates keep working unchanged; `extends` composition and org-wide default answers are what's new.

**Less yak. More stack.**

[Quickstart](quickstart.md){ .md-button .md-button--primary } [Browse Templates Hub](templates-hub/index.md){ .md-button }

!!! tip "Coming from Copier?"
    Start with [Why Boilerplate?](why.md) for the pitch, or go straight to [Template Composition](templates-hub/composition.md) for the `extends` mechanics.

!!! tip "Evaluating for a team?"
    [Why Boilerplate?](why.md) covers the ethos, the environment, and what is shipped versus designed.

---

## Why choose Boilerplate?

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Instant productivity**

    ---

    Scaffold fully configured projects with one command.

-   :material-package-variant-closed:{ .lg .middle } **Locked dependencies**

    ---

    `uv.lock` pins the environment, so every machine resolves the same.

-   :material-tools:{ .lg .middle } **Curated toolchain**

    ---

    `uv`, `ruff`, and `pytest` arrive preconfigured and ready to go, plus a strict `pyright` configuration checked live via Pylance.

-   :material-earth:{ .lg .middle } **Cross-platform**

    ---

    Windows 11 installs are automated; Linux/WSL2 and macOS follow the same steps manually.

-   :material-cog:{ .lg .middle } **Minimal configuration**

    ---

    Sensible defaults out of the box — less setup before you write code.

-   :material-puzzle:{ .lg .middle } **[Template composition](templates-hub/composition.md)**

    ---

    Layer templates with `extends` — one command, one merged question set, deterministic precedence when layers overlap.

</div>

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

<div class="grid cards" markdown>

-   :material-flag-checkered:{ .lg .middle } **[Quickstart](quickstart.md)**

    ---

    Scaffold, install, and run your first project.

-   :material-console:{ .lg .middle } **[CLI reference](cli.md)**

    ---

    Commands, options, and examples.

-   :material-download:{ .lg .middle } **[Installation](install.md)**

    ---

    Manual setup for Linux, WSL2, and macOS.

-   :material-view-grid-plus:{ .lg .middle } **[Templates Hub](templates-hub/index.md)**

    ---

    Explore available templates and where to start.

-   :material-microsoft-visual-studio-code:{ .lg .middle } **[VS Code configuration](environment/vscode.md)**

    ---

    Set up the recommended editor experience.

-   :material-toolbox:{ .lg .middle } **[Toolchain deep dive](environment/index.md)**

    ---

    See how the tools fit together.

-   :material-sitemap:{ .lg .middle } **[Developer platform architecture](reference/platform/index.md)**

    ---

    The platform model and standards.

-   :material-account-group:{ .lg .middle } **[Contributing](governance/contributing.md)**

    ---

    Development setup and coding standards; see also the [Security policy](governance/security.md).

-   :material-help-circle:{ .lg .middle } **[FAQ](faq.md) & [Troubleshooting](troubleshooting.md)**

    ---

    Answers to common questions and fixes for common setup issues.

</div>

---

<div class="brand-mark" markdown>
![Strict typing saves lives. Less yak. More stack.](assets/boilerplate_less_yak.svg){ width="280" }
</div>
