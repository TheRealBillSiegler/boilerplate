# Boilerplate — Domain Glossary

The project's domain vocabulary, one definition per term: templates, composition, and customization; the development environment a generated project ships with; and the mechanics that render, lock, and update a project over time. Definitions name the design's concepts; `docs/status.md` records which are built.

## Language

<!-- --8<-- [start:language] -->
**Template**:  
A directory containing `boilerplate.yml` (name, version, `extends`) and `copier.yml` that boilerplate renders into a project — a Copier scaffold. Its filesystem location is the **template root**.  
_Avoid_: generator, skeleton, blueprint  
_Carve-out_: "template skeleton" names the `init-template` command's scaffold output, not this term.

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
One template rendered at a node of the composition graph, each with its own answers file; a derived Layer (also "derived template" in prose) `extends` another Template to add or override its files. As a verb, a template *layers* on the template it `extends`; in plain prose, templates build on one another.  
_Avoid_: plugin, overlay, mixin  
_Carve-out_: "overlay merge" names ADR-011's deep-merge strategy for downstream structured-file customization, not this term.

**Scoped View**:  
A Layer's merged questions, secret-question list and Jinja extensions over itself and its ancestors; every render of that Layer, at compose and at update, uses it. See design 04 §Scoped view.

**Full Merged Schema**:  
Every Layer's questions joined; the questionnaire at compose uses it, and an update step takes each question's definition and default from it. See design 04 §Scoped view and §Safe Update.

**Hidden Question**:  
A Question whose `when` evaluates false under the recorded answers, the literal `when: false` derived questions among them; no Answers File records it. See design 04 §Safe Update.

**Task**:  
A command declared in a Template's `_tasks` that runs after rendering — the escape hatch for arbitrary edits.  
_Avoid_: hook, script, post-gen step

**Answer Preset**:  
A set of answers applied to a render declaratively, as a YAML file — for CI/CD use.

**Answers File**:  
Records answers given during render. Owned by Copier; Boilerplate MUST NOT write to it. See design 04 §Render behavior for the per-layer `_answers_file:` contract.

**Atomic Staged Write Pattern**:  
Boilerplate's stage-then-rename file-emission discipline: stage in an isolated directory, validate, then atomically move into place. Canonical definition in design 07 §Atomic staged write pattern.

**`.boilerplate/environment.yml`**:  
On-disk filesystem path holding the `EnvironmentProvisionRecord`. Use this name when discussing the file.

**boilerplate.yml**:  
Boilerplate-specific metadata file inside a template directory. Declares name, version, and dependencies. See design 02 §TemplateMeta.

**Configuration**:  
The settings that wire the **Toolchain** into a project — `pyproject.toml` and `.vscode/`. A part of the Development Environment; see the Development Environment guide. Distinct from Boilerplate's own runtime configuration (the `Settings` object — see design 01 §Runtime configuration (Settings)).

**`.copier-answers.<layer>.yml`**:  
The per-layer answers file Copier writes; `<layer>` is the layer's invariant name (matches `LockLayer.name`). One file per composition layer.

**Copier**:  
The external tool ([Copier](https://copier.readthedocs.io/)) responsible for file rendering, answer collection, and task execution. Boilerplate orchestrates Copier without replacing it.

**copier.yml**:  
Copier questionnaire file. Declares questions (variables) and tasks. Owned by Copier; Boilerplate reads but MUST NOT write to it.

**Copy back**:  
The step of `update` and `add` that reproduces the staging worktree's result in the user's checkout as uncommitted changes: `git restore --source=<commit> --worktree -- :/` from the worktree's last per-layer commit. See design 06 §Staging worktree.

**Curation**:  
Choosing the **Toolchain**'s picks from the **Tool landscape** as a set, each for how it works with the others, then configuring them together and maintaining them together. It joins the **Development Environment** and the **Starter templates**, which carry the same picks.

**DAG / Dependency Graph**:  
Directed Acyclic Graph of template specifiers, derived from `extends` chains.

**dev loop**:  
The cycle you repeat inside a project — sync → edit → check → test → commit — on the tools the **Development Environment** provides: the **golden path** for everyday work. A part of the Development Environment; see the Development Environment guide.  
_Avoid_: inner loop, developer workflow, development workflow

**Development Environment**:  
The setup a developer works in, on the machine, in the project and in the editor: the **Toolchain**, its **Configuration** (`pyproject.toml`, `.vscode/`), the **Project Layout**, and the **dev loop**. In the reference model it carries the Toolchain beside the **Starter templates**. Distinct from **Environment Provisioning**, the subsystem that installs it and pins the Toolchain's versions.

**enforced substrate**:  
The `enforced` value of **substrate**: coerce-at-touch-points within Boilerplate's own runtime — schema/parse validation, path-safety (TOCTOU) re-validation, consent/task gating, and lock/checksum verification. Boilerplate rejects on violation with a `BP_*` code; there is no opt-out.

**Environment**:  
The problem domain — a developer's setup and its tendency to diverge across machines and time ("environment drift"). Umbrella over **Development Environment** (the thing) and **Environment Provisioning** (the subsystem); in prose, avoid the bare word where one specific sense is meant.

**Environment Provisioning**:  
The subsystem that installs and version-pins a **Development Environment** — the `env apply` flow, providers, and the `EnvironmentProfile`. See design 08. Supersedes the informal label "Environment(s) Pillar."

**EnvironmentProfile**:  
`boilerplate-env.yml` — the declarative input to **Environment Provisioning** (tool versions + configuration). Not **Profile** (`profile.toml`, a user's default answers to template questions — see ADR-010); the two are unrelated despite the shared word.

**`EnvironmentProvisionRecord`**:  
The schema for the env-state record. Use this name when discussing structure (the file on disk is `.boilerplate/environment.yml`).

**extends-based composition**:  
The static `extends:` mechanism in template metadata that drives composition. Not a runtime feature; resolved at composition time.

**first-party gating scaffolding**:  
The CI pipelines, lint configs, and profile assets shipped beside templates as user-runnable parts of the **preconfigured** substrate. User opts in; gates execute in third-party tools' native venues (CI runners, hook runners).

**first-party templates**:  
Templates Boilerplate publishes as their own git repositories, extracted from the authoring monorepo at release time — the canonical first-party distribution channel (vs user-provided or third-party); see ADR-006.

**gating scaffolding**:  
See **first-party gating scaffolding**.

**golden path**:  
A **workflow** whose decisions are already thought out for you: the supported, opinionated route through one job. Golden paths nest: each template is a golden path to a starting point, solving the plumbing so a project starts ready for work, and the **dev loop** is the golden path for the everyday work that follows. An element of the reference model, answering *how do we work?*; see Developer platform architecture §The golden path.  
_Avoid_: paved road, paved path

**Guardrails**:  
An element of the reference model, answering *how do we comply?*: the automated checks that verify a project against the standards its templates configure — dev-time in a **Development Environment** (format-on-save, live type-checking) and CI — as part of the **preconfigured** substrate. See Developer platform architecture §Guardrails.

**Lock File (`boilerplate.lock`)**:  
Records exact versions, commit hashes, and checksums used. Owned by Boilerplate.

**Managed project**:  
A project Boilerplate tracks and can update: it has a `boilerplate.lock`. Contrast **Unmanaged project**. `adopt` transitions an unmanaged project to managed.

**Non-git layer**:  
A composition layer whose template source has no git history (a plain filesystem directory or an archive). Records `commit: null` in the lock; `update` skips it with a warning — Copier has no built-in fallback merge for it — and `copier recopy` is the manual refresh. See design 06.

**PEP**:  
Python Enhancement Proposal — the standards process for the Python language. Referenced PEPs: 440 (versioning), 508 (dependency specifiers), 517/518 (build system), 621 (project metadata), 660 (editable installs), 723 (inline script metadata).

**PEP discipline**:  
The convention that when a PEP defines the canonical way, first-party templates use it — no custom conventions that duplicate or contradict a PEP.

**plural-shape architecture**:  
Authoring shape that admits future siblings (e.g., `ci-azure-pipelines` today, `ci-github-actions` later) by extending the answer-value enum, not by introducing a breaking schema change.

**post-render validation**:  
Out-of-scope content verdicts performed against generated projects after Boilerplate hands off (detecting drift between shipped defaults and user-edited config). Not enforced; structurally outside Boilerplate's reach.

**Project Layout**:  
The standard project structure — `src/`, `tests/`, and their conventions. A part of the **Development Environment**; see the Development Environment guide.

**Reference model**:  
The model of what Boilerplate is: **Curation** picks the **Toolchain** from the **Tool landscape**; the **Development Environment** and the **Starter templates** carry it; **golden paths** run on it; **Guardrails** check the work. Owned by Developer platform architecture. Every other statement of what Boilerplate is derives from it.

**RenderEngine**:  
The proper-noun class that orchestrates Copier across composition layers.

**Restore marker**:  
The file under the project's git directory, paired with the ref `refs/worktree/boilerplate/restore`, that keeps the state of a copy back cut off midway so a rerun can finish it or the user can set it aside. See design 06 §Interrupted copy back and §Setting a partial update aside.

**safe update**:  
The conflict-detected update workflow Boilerplate provides over Copier's per-layer merge: it runs in a staging worktree and pauses on conflict. See design 04 §Safe update for the implementation.

**slot**:  
One recurring role in a development environment (linter, type checker, test runner, …), per the Development Environment Landscape guide. Each first-party template fills the slots its ecosystem's **dev loop** uses with one opinionated tool each; the template then fills slots *within* those slots (each tool's per-project configuration).

**Starter templates**:  
An element of the reference model, answering *how do we start?*: the **Templates**, each a **golden path** to a starting point that carries the **Toolchain**'s project and editor picks. Outside the reference model, say **Template**. See Developer platform architecture §Starter templates.

**substrate**:  
A layer's enforcement mode — `enforced` (Boilerplate's own runtime gates and rejects on violation, with no opt-out) or `preconfigured` (defaults are shipped; user-runnable gating scaffolding executes the check in third-party venues; the user MAY opt out). Per-layer assignments live in PROD-001 `enforcement_layers`.

**TOFU**:  
Trust-on-first-use — a security model where the first interaction with a remote source is trusted, and subsequent interactions are verified against the initial state.

**Tool landscape**:  
An element of the reference model, answering *what exists?*: the descriptive catalog of the tools, technologies and practices available in a domain, organized by **slot**; the **Toolchain** is curated from it. Boilerplate keeps it as the Development Environment Landscape guide. See Developer platform architecture §The tool landscape.

**Toolchain**:  
The development tools Boilerplate picks and sets up, one per **slot** (uv, Ruff, Pyright, pytest, …), chosen by **Curation** from the **Tool landscape**, whether or not their versions are pinned. **Environment Provisioning** pins them through an **EnvironmentProfile**; not every pick is pinned (the editor and git are not). An element of the reference model, answering *what do we use?*; see Developer platform architecture §The toolchain. A part of the **Development Environment**, **not** a synonym for it, and not an application's own framework stack.  
_Avoid_: curated stack, dev stack, tech stack  
_Carve-out_: the slogan "Less Yak. More Stack." puns on the toolchain handed to you and templates stacking; outside it, a template **layers** on another. The reference model page names "curated stack" once, as platform engineering's term.

**Trust Level**:  
Binary classification for a template's origin: *trusted* or *untrusted*. Untrusted code is default-deny and requires explicit consent. The lock's optional `trust_tier` field is a free-form string field reserved for future richer tiers. See design 03.

**Unmanaged project**:  
A project with Copier answers file(s) (`.copier-answers.*`) but no `boilerplate.lock` — e.g. a plain `copier copy` project, or one after `eject`. Contrast **Managed project**. `adopt` transitions it to managed.

**schema v1**:  
The first generation of this design suite's on-disk contracts (`schema_version` major `1`, e.g. `"1"` / `"boilerplate/lock@1"`). Independent of the tool's release version (SemVer `0.x` until the first stable `1.0`), which tracks implementation maturity, not contract generation.

**WASM**:  
WebAssembly — the plugin architecture used by proto for cross-platform tool installation.

**workflow**:  
The steps taken to get a job done. A **golden path** is a workflow whose decisions are already made. GitHub Actions workflow files keep their own name.
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
