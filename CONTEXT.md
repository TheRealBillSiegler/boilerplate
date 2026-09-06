# Boilerplate — Template Customization

How a user customizes the projects boilerplate generates — the values, structure, and behavior they layer onto a template's output. Covers the generation pipeline and its customization taps.

## Language

**Template**:
A Copier scaffold with a `boilerplate.yml` (name, version, `extends`) that boilerplate renders into a project.
_Avoid_: generator, skeleton, blueprint

**Question**:
A Copier-declared input on a Template (in `copier.yml`) whose answer fills the rendered output.
_Avoid_: variable, prompt, field

**Profile**:
A user's default answers for Template Questions, read from `profile.toml` and merged into the render — global `[defaults]` plus per-Template `[templates.<name>]`.
_Avoid_: typed Profile model, org profile, config

**Layer**:
A Template that `extends` another to add or override files in the composed result.
_Avoid_: plugin, overlay, mixin

**Task**:
A command declared in a Template's `_tasks` that runs after rendering — the escape hatch for arbitrary edits. (Profile-declared tasks are designed but deferred; see ADR-010.)
_Avoid_: hook, script, post-gen step

## Relationships

- A **Template** declares zero or more **Questions**
- A **Profile** supplies default answers to a Template's **Questions** by name — the key namespace is open; the only reserved grammar is `[defaults]` / `[templates.<name>]`
- A **Layer** is a **Template** that `extends` another **Template**
- **Tasks** accumulate across composed **Layers** and run once, after the final render
- Customization escalates in power: **Profile** (a value) < **Layer** (structure) < **Task** (behavior) — reach for the least powerful that works

## Example dialogue

> **Dev:** "I always want my org's package index in generated projects — is that a Profile?"
> **Maintainer:** "Not the typed Profile model — that's retired. If `project` declares a `package_index_url` **Question**, set it once in your **profile** `[defaults]` and every render fills it. Need a whole file `project` doesn't ship? Author a **Layer** that `extends` it. Need to append to a file it didn't anticipate? Add a **Task**."

## Flagged ambiguities

- **Profile** (typed model) — retired. The pydantic `Profile`/`PackageIndex`/`Container` classes, their resolver, and the original `boilerplate config` command conflated a typed two-field config with a switchable named instance, stamping values through a `_boilerplate` namespace. Retired in favor of a plain default-answers file — the word **profile** is reused for that file (`profile.toml`; see the **Profile** term above), plus **Layers** (structure) and **Tasks** (behavior). Do not reintroduce a _typed_ customization model — "profile" now names a plain file, not a pydantic model.
- The `boilerplate config` command is retired; no `config` command exists today. A repurposed form — named, switchable **profile** **default sets** via `config list` / `config use <name>` / `config show` (kubectl-contexts pattern) — is designed but deferred (see [ADR-010](docs/design/adr-010-profile.md)). Its old typed-**Profile**-model role and `config validate` are gone for good, not deferred.
