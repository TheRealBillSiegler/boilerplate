---
description: Why Boilerplate exists — the ethos it encodes, the environment it sets up, and the composition layer it builds on Copier.
---

# Why Boilerplate?

Boilerplate takes care of the parts around writing code — a working toolchain and a configured project — so a new Python project starts on one golden path and you start at the work. A golden path is the supported, opinionated way to build one kind of project.

Boilerplate is an ethos made executable: engineering judgment — which tools, how they're configured, how a project is laid out — encoded as software that runs, so a new project inherits the discipline instead of being advised toward it. It is two things at once: a particular Python development environment, and the scaffolder that stamps out projects configured for it.

## Yak shaving

You need one package for the task at hand. That package needs a newer Python. The newer Python needs a PATH fix before it will even run. Three side quests deep, and the actual work hasn't started. The chain has a name — [**yak shaving**](https://en.wiktionary.org/wiki/yak_shaving): a prerequisite that hides another prerequisite until the original task is buried under toil that isn't the task.

No single link in that chain is hard. The damage is the pattern — individually tolerable incidents that quietly become an operating model:

- "I'll just copy the last project." "Works on my machine."
- Tool choice re-litigated for every repository — Ruff or Black, uv or Poetry.
- Onboarding that eats a day before the first test runs.
- A setup README that drifted from what the tooling actually does.

Python itself raises the stakes. The ecosystem ships no equivalent of `npm create` or `dotnet new` — no blessed on-ramp to a working project — and the tooling underneath keeps moving: packaging and environment managers compete, get replaced, and leave layers of guidance behind them. Much of what a search turns up teaches techniques the current PEPs have already superseded, and there is no canonical, up-to-date reference project to copy from. Every team re-derives "modern" on its own, or inherits whichever year's answer its oldest tutorial froze.

**Less yak. More stack.** is the promise to cut that chain down: the environment arrives working, the project arrives configured, and you start at the task itself.

## The ethos

Three opinions the tool executes rather than recommends:

- **Opinionated defaults, visible overrides.** Every pick — uv, Ruff, Pyright strict, pytest — is a default rather than a mandate: template questions, [`profile.toml`](customization.md), and plain config edits are the sanctioned escape hatches.
- **Automation over documentation.** When a practice matters, it is encoded — in the installer, the template, or the generated config — instead of written into instructions that drift.
- **Legibility before trust.** You can inspect what generation will do before believing it: `boilerplate new --dry-run` shows the render plan — layer order and destination — without writing anything, `boilerplate graph` shows the layers, `boilerplate compose` shows the merged configuration.

## A whole environment, one pick per slot

A development environment is a set of [slots](design/01-overview.md#term-slot) — shell, runtime and package manager, linter, type checker, test runner, editor — and most teams fill them by accretion. Boilerplate fills each slot with one opinionated, overridable pick, at three layers:

- **Machine** — the [installer](install.md) bootstraps the baseline itself: PowerShell 7 (installed first when missing), Git, VS Code with extensions, uv, and the boilerplate CLI. There is no prerequisites section that quietly assumes an hour of setup.
- **Project** — every generated project arrives with a uv-managed, locked environment and Ruff, Pyright strict, and pytest configured in `pyproject.toml`; its example module and test pass those checks on the first run.
- **Editor** — templates ship `.vscode/` settings and extension recommendations, so the editor and the toolchain agree on interpreter, linting, and formatting.

The [environment overview](environment/index.md) walks the full toolchain and how the pieces fit. Environment validation is deliberately thin today ([Implementation Status](status.md)).

## One path, not a repeated conversation

Boilerplate started in 2024 inside a small enablement team, as a way to stop re-explaining the same project setup to every new project. It was research before it was software: a systematic pass over the landscape — package and environment managers, scaffolders, type checkers, test runners — judged against one brief, *the most modern and lightweight in each*, and against what current PEPs actually prescribe. The stack settled late that year, and the tool was built for colleagues from its first mention. The leverage is structural: the judgment gets absorbed once, upstream, and one maintained path replaces the recurring setup conversation.

The tool holds itself to the standard it hands out: this repository's own CI runs the same checks it configures in every generated project — Ruff, Pyright strict, pytest — plus a strict docs build. See [the local check](governance/ci.md#the-local-check).

One early user described the before-and-after: "before, it was like having your laundry folded — but on the floor. After, it's like sliding the drawer into the dresser: the clothes go in, and it slides friction-free." Another summed up the install as ending in "a fully suped-up Python environment."

## Built on Copier

Boilerplate stands on [Copier](https://copier.readthedocs.io/) rather than reinventing it: Copier does the rendering, prompting, and answers-file bookkeeping, and templates stay standard Copier templates. Composition metadata lives in a separate `boilerplate.yml` beside `copier.yml`; Boilerplate never modifies or replaces your `copier.yml`, and a template becomes a layer by adding that one file.

Boilerplate adds two things on top. The first is the opinions: Copier is deliberately a general-purpose engine — any language, any layout, bring your own templates and your own judgment — while Boilerplate ships [the ethos](#the-ethos) and [the environment](#a-whole-environment-one-pick-per-slot) above as maintained templates and an installer that keep pace with the toolchain and with current standards. Adopting it with a single template and no composition at all still gets you that.

The second is the layer Copier's maintainers approved in principle but left to the community ([copier-org/copier#934](https://github.com/copier-org/copier/issues/934)): declared template composition. Copier's own [multi-template pattern](https://copier.readthedocs.io/en/stable/configuring/#applying-multiple-templates-to-the-same-subproject) works well when templates touch disjoint files; its practical boundary is overlap. When two templates render the same file — `pyproject.toml` is the recurring example ([discussion #1485](https://github.com/orgs/copier-org/discussions/1485)) — there is no merge: Copier prompts per conflicting file, or the last-applied template wins. With Boilerplate, the *template author* declares composition once — `extends: [project]` in the template's `boilerplate.yml` — and `boilerplate new` renders the full layer stack in one command, with one merged question set and deterministic precedence when layers overlap; the [composition guide](templates-hub/composition.md) covers the mechanics in depth. A [`profile.toml`](customization.md) pre-fills org answers (your package index, your registry) across the whole catalog without forking templates.

Already using Copier? Your templates keep working unchanged; composition and the curated environment are what's new.

| Use case | Recommended tool |
|----------|-----------------|
| Your own templates, any language, no opinions wanted | Copier |
| An opinionated, maintained Python environment and scaffold | Boilerplate |
| Single custom template, no composition | Copier |
| Multiple templates touching disjoint files | Copier's [multi-template pattern](https://copier.readthedocs.io/en/stable/configuring/#applying-multiple-templates-to-the-same-subproject) |
| Layered templates with `extends`, overlapping files | Boilerplate |
| One merged question set across layers | Boilerplate |
| Org-wide default answers without forking templates | Boilerplate |

## Who it's for

Platform teams and template maintainers who own more than one template and want the common foundation defined once — and individuals who want an opinionated, preconfigured Python scaffold without assembling the toolchain themselves.

## Where next

- **[The vision](design/01-overview.md#what-boilerplate-is)** — the target catalog and environment, in design terms.
- **[Implementation status](status.md)** — what is implemented, partial, or planned.
- **[Quickstart](quickstart.md)** — install and scaffold your first project.
- **[Template composition](templates-hub/composition.md)** — the `extends` mechanics in depth.
- **[Environment overview](environment/index.md)** — the toolchain, slot by slot.
