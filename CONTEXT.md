# Boilerplate — Domain Glossary

The project's domain vocabulary, one definition per term: templates, composition, and customization; the development environment a generated project ships with; and the mechanics that render, lock, and update a project over time.

## Language

<!-- --8<-- [start:language] -->
**Template**:
A directory containing `boilerplate.yml` (name, version, `extends`) and `copier.yml` that boilerplate renders into a project — a Copier scaffold. Its filesystem location is the **template root**.
_Avoid_: generator, skeleton, blueprint

**Template Specifier**:
A `name@version` string uniquely identifying a template — the resolved form.

**Template Reference**:
The input form of a **Template Specifier** — `name` or `name@version` — before resolution.

**Question**:
A Copier-declared input on a Template (in `copier.yml`) whose answer fills the rendered output.
_Avoid_: variable, prompt, field

**Profile**:
A user's default answers for Template Questions, read from `profile.toml` and merged into the render — global `[defaults]` plus per-Template `[templates.<name>]`.
_Avoid_: typed Profile model, org profile, config

**Layer**:
A Template that `extends` another to add or override files in the composed result — one rendered node in the composition graph, each with its own answers file.
_Avoid_: plugin, overlay, mixin

**Task**:
A command declared in a Template's `_tasks` that runs after rendering — the escape hatch for arbitrary edits.
_Avoid_: hook, script, post-gen step

**Answer Preset**:
A YAML file supplying answers to template questions declaratively for CI/CD. Passed via `--answers`.

**Answers File**:
Records answers given during render. Owned by Copier; Boilerplate MUST NOT write to it. See [04-composition-engine.md §Render Behavior](04-composition-engine.md#render-behavior) for the per-layer `_answers_file:` contract.

**Atomic Staged Write Pattern**:
Boilerplate's stage-then-rename file-emission discipline: stage in an isolated directory, validate, then atomically move into place. Canonical definition in [07-operational-quality.md §Atomic Staged Write Pattern](07-operational-quality.md#atomic-staged-write-pattern).

**`.boilerplate/environment.yml`**:
On-disk filesystem path holding the `EnvironmentProvisionRecord`. Use this name when discussing the file.

**boilerplate.yml**:
Boilerplate-specific metadata file inside a template directory. Declares name, version, and dependencies. See [02-data-models.md §TemplateMeta](02-data-models.md#templatemeta).

**Configuration**:
The settings that wire a **Development Environment**'s toolchain — `pyproject.toml` and `.vscode/`. A part of the Development Environment; see the [Development Environment](../environment/index.md) guide. Distinct from Boilerplate's own runtime configuration (the `Settings` object — see [§Runtime Configuration](#runtime-configuration-settings)).

**`.copier-answers.<layer>.yml`**:
The per-layer answers file Copier writes; `<layer>` is the layer's invariant name (matches `LockLayer.name`). One file per composition layer.

**Copier**:
The external tool ([Copier](https://copier.readthedocs.io/)) responsible for file rendering, answer collection, and task execution. Boilerplate orchestrates Copier without replacing it.

**copier.yml**:
Copier questionnaire file. Declares questions (variables) and tasks. Owned by Copier; Boilerplate reads but MUST NOT write to it.

**DAG / Dependency Graph**:
Directed Acyclic Graph of template specifiers, derived from `extends` chains.

**Development Environment**:
The setup a developer works in — its **Toolchain**, its **Configuration** (`pyproject.toml`, `.vscode/`), **Project Layout**, **Workflow**, and **Guardrails**. What a generated project ships with (INT-001). Distinct from **Environment Provisioning**, the subsystem that installs and pins it.

**enforced substrate**:
The `enforced` value of **substrate**: coerce-at-touch-points within Boilerplate's own runtime — schema/parse validation, path-safety (TOCTOU) re-validation, consent/task gating, and lock/checksum verification. Boilerplate rejects on violation with a `BP_*` code; there is no opt-out.

**Environment**:
The problem domain — a developer's setup and its tendency to diverge across machines and time ("environment drift"). Umbrella over **Development Environment** (the thing) and **Environment Provisioning** (the subsystem); in prose, avoid the bare word where one specific sense is meant.

**Environment Provisioning**:
The subsystem that installs and version-pins a **Development Environment** — the `env apply` flow, providers, and the `EnvironmentProfile`. Target design (INT-004; see [§08](08-environment-provisioning.md)). Supersedes the informal label "Environment(s) Pillar."

**EnvironmentProfile**:
`boilerplate-env.yml` — the declarative input to **Environment Provisioning** (tool versions + configuration). Not **Profile** (`profile.toml`, a user's default answers to template questions — see [ADR-010](adr-010-profile.md)); the two are unrelated despite the shared word.

**`EnvironmentProvisionRecord`**:
The schema for the env-state record. Use this name when discussing structure (the file on disk is `.boilerplate/environment.yml`).

**extends-based composition**:
The static `extends:` mechanism in template metadata that drives composition. Not a runtime feature; resolved at composition time.

**first-party gating scaffolding**:
The CI pipelines, lint configs, and profile assets shipped beside templates as user-runnable parts of the **preconfigured** substrate. User opts in; gates execute in third-party tools' native venues (CI runners, hook runners).

**first-party templates**:
Templates Boilerplate publishes as their own git repositories, extracted from the authoring monorepo at release time — the canonical first-party distribution channel (vs user-provided or third-party); see [ADR-006](adr-006-template-distribution.md).

**gating scaffolding**:
See **first-party gating scaffolding**.

**Guardrails**:
Where quality is enforced across a **Development Environment** — dev-time (format-on-save, live type-checking) and CI. A part of the Development Environment; see the [Development Environment](../environment/index.md) guide.

**Lock File (`boilerplate.lock`)**:
Records exact versions, commit hashes, and checksums used. Owned by Boilerplate.

**Managed project**:
A project Boilerplate tracks and can update: it has a `boilerplate.lock`. Contrast **Unmanaged project**. `adopt` transitions an unmanaged project to managed.

**Non-git layer**:
A composition layer whose template source has no git history (a plain filesystem directory or an archive). Records `commit: null` in the lock; `update` skips it with a warning — Copier has no built-in fallback merge for it — and `copier recopy` is the manual refresh. See [06-project-lifecycle.md](06-project-lifecycle.md).

**PEP**:
Python Enhancement Proposal — the standards process for the Python language. Referenced PEPs: 440 (versioning), 508 (dependency specifiers), 517/518 (build system), 621 (project metadata), 660 (editable installs), 723 (inline script metadata).

**PEP discipline**:
The convention that when a PEP defines the canonical way, first-party templates use it — no custom conventions that duplicate or contradict a PEP.

**plural-shape architecture**:
Authoring shape that admits future siblings (e.g., `ci-azure-pipelines` today, `ci-github-actions` later) by extending the answer-value enum, not by introducing a breaking schema change.

**post-render validation**:
Out-of-scope content verdicts performed against generated projects after Boilerplate hands off (detecting drift between shipped defaults and user-edited config). Not enforced; structurally outside Boilerplate's reach.

**Project Layout**:
The standard project structure — `src/`, `tests/`, and their conventions. A part of the **Development Environment**; see the [Development Environment](../environment/index.md) guide.

**RenderEngine**:
The proper-noun class that orchestrates Copier across composition layers.

**safe update**:
The conflict-detected, atomically-rolled-back update workflow Boilerplate provides over Copier's per-layer merge. See [04 §Safe Update](04-composition-engine.md#safe-update) for the implementation.

**slot**:
One recurring role in a development environment (linter, type checker, test runner, …), per [The Development Environment Landscape](dev-environment-landscape.md). Boilerplate fills the inner-loop slots with one opinionated tool each; templates fill slots *within* those slots (each tool's per-project configuration).

**substrate**:
A layer's enforcement mode — `enforced` (Boilerplate's own runtime gates and rejects on violation, with no opt-out) or `preconfigured` (defaults are shipped; user-runnable gating scaffolding executes the check in third-party venues; the user MAY opt out). Per-layer assignments live in PROD-001 `enforcement_layers`.

**TOFU**:
Trust-on-first-use — a security model where the first interaction with a remote source is trusted, and subsequent interactions are verified against the initial state.

**Toolchain**:
The tool *set* within a **Development Environment**: uv, ruff, pyright, pytest, VS Code, git. A part of the environment, **not** a synonym for it.

**Trust Level**:
Binary classification for a template's origin: *trusted* or *untrusted*. Untrusted code is default-deny and requires explicit consent. The lock's optional `trust_tier` field is a free-form string field reserved for future richer tiers. See [03-template-system.md](03-template-system.md).

**Unmanaged project**:
A project with Copier answers file(s) (`.copier-answers.*`) but no `boilerplate.lock` — e.g. a plain `copier copy` project, or one after `eject`. Contrast **Managed project**. `adopt` transitions it to managed.

**schema v1**:
The first generation of this design suite's on-disk contracts (`schema_version` major `1`, e.g. `"1"` / `"boilerplate/lock@1"`). Independent of the tool's release version (SemVer `0.x` until the first stable `1.0`), which tracks implementation maturity, not contract generation.

**WASM**:
WebAssembly — the plugin architecture used by proto for cross-platform tool installation.

**Workflow**:
The everyday developer loop within a **Development Environment** — sync → edit → check → test → commit. A part of the Development Environment; see the [Development Environment](../environment/index.md) guide.
<!-- --8<-- [end:language] -->

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
