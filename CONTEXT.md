# Boilerplate — Domain Glossary

The project's domain vocabulary, one concept per entry, grouped in six modules: `core` for concepts every module uses, then `model` (the reference model), `composition`, `customization`, `provisioning` and `trust`. Definitions name the design's concepts; `docs/status.md` records which are built. Each entry opens with an anchor, the term in bold and its identifier, `module:Name`, then one or two sentences of definition and these labeled lines, in this order, each left out when it does not apply: **Kind of**, **Part of**, **Related**, **Not to be confused with**, **Stored in**, **Defined in**, **See**, **Avoid**, **Carve-out**, **Matches**. **Related** lines need not be reciprocal; **Not to be confused with** lines always are. The anchor, `<a id="term-…"></a>`, is `term-` plus the term in lowercase, backticks dropped, and every run of other characters turned into `-`, and leading and trailing `-` dropped. Rename the id with the term, keep the old id beside the new one so inbound links still resolve, then fix the links the strict docs build reports. [ADR-016](docs/design/adr-016-project-vocabulary.md) records the format.

## Language

<!-- --8<-- [start:language] -->
### `core`

Concepts every module uses.

<a id="term-copier"></a>**Copier** · `core:Copier`  
The external tool ([Copier](https://copier.readthedocs.io/)) responsible for file rendering, answer collection, and task execution. Boilerplate orchestrates Copier without replacing it.

- **Related:** `core:Template`, `core:Question`, `composition:AnswersFile`, `composition:RenderEngine`, `customization:Task`
- **Defined in:** `src/boilerplate/integrations/copier_types.py` (the single audited import point for the Copier internals Boilerplate uses)
- **See:** `docs/design/adr-001-build-vs-adopt.md`; `docs/design/adr-002-copier-internals-shim.md`

<a id="term-template"></a><a id="term-boilerplate-yml"></a><a id="term-copier-yml"></a>**Template** · `core:Template`  
A directory containing `boilerplate.yml` (name, version, `extends`) and `copier.yml` that boilerplate renders into a project — a Copier scaffold. Its filesystem location is the **template root**.

- **Related:** `core:Copier`, `core:Question`, `core:TemplateSpecifier`, `composition:Layer`, `customization:Task`, `model:StarterTemplates`, `model:GoldenPath`
- **Stored in:** `boilerplate.yml`, Boilerplate-specific metadata (name, version, and dependencies through `extends`), and `copier.yml`, Copier's questionnaire (questions and tasks), both at the template root, for example `src/boilerplate/templates/project/boilerplate.yml` and `src/boilerplate/templates/project/copier.yml`. Copier owns `copier.yml`; Boilerplate reads it and MUST NOT write to it.
- **Defined in:** `src/boilerplate/models/template_meta.py` (`TemplateMeta`, the `boilerplate.yml` schema), `src/boilerplate/models/template_info.py`
- **See:** design 02 §TemplateMeta; design 03 §`boilerplate.yml` Schema
- **Avoid:** generator, skeleton, blueprint
- **Carve-out:** "template skeleton" names the `init-template` command's scaffold output, not this term.
- **Matches:** template, in Copier's documentation (close: Copier's template is a directory, usually a Git repository's root, with an optional `copier.yml`; a Template here also carries `boilerplate.yml`)

<a id="term-first-party-templates"></a>**first-party templates** · `core:FirstPartyTemplates`  
Templates Boilerplate publishes as their own git repositories, extracted from the authoring monorepo at release time — the canonical first-party distribution channel (versus user-provided or third-party templates).

- **Kind of:** `core:Template`
- **Related:** `model:StarterTemplates`, `trust:TrustLevel`, `trust:FirstPartyGatingScaffolding`, `trust:PEPDiscipline`, `core:PEP`
- **Stored in:** `src/boilerplate/templates/` (the authoring monorepo's copies)
- **See:** `docs/design/adr-006-template-distribution.md`; design 03 §First-Party Templates

<a id="term-template-specifier"></a>**Template Specifier** · `core:TemplateSpecifier`  
A `name@version` string uniquely identifying a template — the resolved form.

- **Related:** `core:Template`, `composition:DependencyGraph`
- **Not to be confused with:** `composition:TemplateReference` (the unresolved input form, which may omit the version)
- **Defined in:** `src/boilerplate/types/template_specifier.py`
- **See:** design 02 §TemplateSpecifier

<a id="term-question"></a>**Question** · `core:Question`  
A Copier-declared input on a Template, whose answer fills the rendered output; a Template declares zero or more in `copier.yml`.

- **Part of:** `core:Template`
- **Related:** `core:Copier`, `composition:AnswersFile`, `composition:HiddenQuestion`, `composition:ScopedView`, `composition:FullMergedSchema`, `customization:Profile`, `customization:AnswerPreset`
- **Stored in:** the declaring template's `copier.yml` (owned by Copier; Boilerplate reads it and MUST NOT write to it)
- **Defined in:** `src/boilerplate/integrations/copier_types.py` (Copier's `Question`, imported), `src/boilerplate/composition/merging/strategies.py` (`merge_questions`)
- **Avoid:** variable, prompt, field
- **Matches:** question, in Copier's documentation (exact)

<a id="term-schema-v1"></a>**schema v1** · `core:SchemaV1`  
The first generation of this design suite's on-disk contracts (`schema_version` major `1`, e.g. `"1"` / `"boilerplate/lock@1"`). Independent of the tool's release version (SemVer `0.x` until the first stable `1.0`), which tracks implementation maturity, not contract generation.

- **Related:** `core:Template`, `composition:LockFile`
- **Stored in:** the `schema_version` field of `boilerplate.yml` and of `boilerplate.lock`
- **Defined in:** `src/boilerplate/models/template_meta.py`, `src/boilerplate/models/boilerplate_lock.py`
- **See:** design 03 §Schema Evolution

<a id="term-pep"></a>**PEP** · `core:PEP`  
Python Enhancement Proposal — the standards process for the Python language. Referenced PEPs: 440 (versioning), 508 (dependency specifiers), 517/518 (build system), 621 (project metadata), 660 (editable installs), 723 (inline script metadata).

- **Related:** `trust:PEPDiscipline`, `core:FirstPartyTemplates`
- **See:** design 01 §Standards compliance in first-party templates

<a id="term-atomic-staged-write-pattern"></a>**Atomic Staged Write Pattern** · `core:AtomicStagedWritePattern`  
Boilerplate's stage-then-rename file-emission discipline: stage in an isolated directory, validate, then atomically move into place.

- **Related:** `composition:SafeUpdate`, `provisioning:EnvironmentProvisioning`
- **Defined in:** `src/boilerplate/project_state/atomic_write.py`, `src/boilerplate/composition/staging/staging_worktree.py`, `src/boilerplate/composition/staging/intent_journal.py`, `src/boilerplate/composition/staging/stale_cleanup.py`
- **See:** design 07 §Atomic Staged Write Pattern (canonical definition)

<a id="term-settings"></a>**Settings** · `core:Settings`  
Boilerplate's own runtime configuration: one immutable object, loaded once at CLI startup and passed to every application service.

- **Related:** `customization:Profile`
- **Not to be confused with:** `model:Configuration` (the Toolchain's settings in a generated project, not Boilerplate's own)
- **Stored in:** compiled-in defaults, overridden by a `.env` file in the current directory, then by `BOILERPLATE_*` environment variables
- **Defined in:** `src/boilerplate/settings/settings.py`
- **See:** design 09 §Settings

### `model`

The reference model: what Boilerplate is.

<a id="term-reference-model"></a>**Reference model** · `model:ReferenceModel`  
The model of what Boilerplate is: **Curation** picks the **Toolchain** from the **Tool landscape**; the **Toolchain** is a part of the **Development Environment**, and the **Starter templates** carry it too; **golden paths** run on it; **Guardrails** check the work. Every other statement of what Boilerplate is derives from it.

- **Related:** `model:Curation`
- **See:** Developer platform architecture §The model (`docs/reference/platform/index.md`), which owns it

<a id="term-environment"></a>**Environment** · `model:Environment`  
The problem domain — a developer's setup and its tendency to diverge across machines and time ("environment drift") — and the umbrella over the **Development Environment** (the thing) and **Environment Provisioning** (the subsystem). In prose, avoid the bare word where one specific sense is meant.

- **Related:** `model:DevelopmentEnvironment`, `provisioning:EnvironmentProvisioning`

<a id="term-tool-landscape"></a>**Tool landscape** · `model:ToolLandscape`  
The descriptive catalog of the tools, technologies and practices available in a domain, organized by **slot**, answering *what exists?*; the **Toolchain** is curated from it. Boilerplate keeps it as the Development Environment Landscape guide.

- **Part of:** `model:ReferenceModel`
- **Related:** `model:Slot`, `model:Curation`, `model:Toolchain`
- **Stored in:** `docs/design/dev-environment-landscape.md`
- **See:** Developer platform architecture §The tool landscape (`docs/reference/platform/index.md`)

<a id="term-slot"></a>**slot** · `model:Slot`  
One recurring role in a development environment (linter, type checker, test runner, …). Each first-party template fills the slots its ecosystem's **dev loop** uses with one opinionated tool each; the template then fills slots *within* those slots (each tool's per-project configuration).

- **Part of:** `model:ToolLandscape`
- **Related:** `model:Toolchain`, `model:Configuration`, `model:DevLoop`, `core:FirstPartyTemplates`
- **See:** design 01 §What Boilerplate is (the slot model); `docs/design/dev-environment-landscape.md`, which catalogues the slots

<a id="term-curation"></a>**Curation** · `model:Curation`  
Choosing the **Toolchain**'s picks from the **Tool landscape** as a set, each for how it works with the others, then configuring them together and maintaining them together. It joins the **Development Environment** and the **Starter templates**, which carry the same picks.

- **Related:** `model:ReferenceModel`, `model:ToolLandscape`, `model:Toolchain`, `model:DevelopmentEnvironment`, `model:StarterTemplates`

<a id="term-toolchain"></a>**Toolchain** · `model:Toolchain`  
The development tools Boilerplate picks and sets up, one per **slot** (uv, Ruff, Pyright, pytest, …), chosen by **Curation** from the **Tool landscape**, whether or not their versions are pinned; it answers *what do we use?* and is not an application's own framework stack. **Environment Provisioning** pins the tools through an **EnvironmentProfile**, and not every pick is pinned (the editor and git are not).

- **Part of:** `model:DevelopmentEnvironment`
- **Related:** `model:Slot`, `model:Curation`, `model:ToolLandscape`, `model:Configuration`, `model:StarterTemplates`, `provisioning:EnvironmentProvisioning`, `provisioning:EnvironmentProfile`
- **Not to be confused with:** `model:DevelopmentEnvironment` (which contains the Toolchain; not a synonym)
- **See:** Developer platform architecture §The toolchain (`docs/reference/platform/index.md`)
- **Avoid:** curated stack, dev stack, tech stack
- **Carve-out:** the slogan "Less Yak. More Stack." puns on the toolchain handed to you and templates stacking; outside it, a template **layers** on another. The reference model page names "curated stack" once, as something the toolchain is sometimes called.
- **Matches:** curated stack, in platform engineering per `docs/reference/platform/index.md` (close)

<a id="term-development-environment"></a>**Development Environment** · `model:DevelopmentEnvironment`  
The setup a developer works in, on the machine, in the project and in the editor: the **Toolchain**, its **Configuration** (`pyproject.toml`, `.vscode/`), the **Project Layout**, and the **dev loop**. In the reference model the **Toolchain** is a part of it, and the **Starter templates** sit beside it.

- **Part of:** `model:ReferenceModel`
- **Related:** `model:Environment`, `model:StarterTemplates`, `model:Configuration`, `model:ProjectLayout`, `model:DevLoop`
- **Not to be confused with:** `model:Toolchain` (one of its parts, not a synonym), `provisioning:EnvironmentProvisioning` (the subsystem that installs it and pins the Toolchain's versions)
- **See:** the Development Environment guide (`docs/environment/index.md`)

<a id="term-configuration"></a>**Configuration** · `model:Configuration`  
The settings that wire the **Toolchain** into a project — `pyproject.toml` and `.vscode/`.

- **Part of:** `model:DevelopmentEnvironment`
- **Related:** `model:Toolchain`, `model:Slot`, `provisioning:EnvironmentProfile`
- **Not to be confused with:** `core:Settings` (Boilerplate's own runtime configuration, not a generated project's)
- **Stored in:** a generated project's `pyproject.toml` and `.vscode/`, rendered from `src/boilerplate/templates/project/pyproject.toml.jinja` and `src/boilerplate/templates/project/.vscode/`
- **See:** the Development Environment guide §Configuration (`docs/environment/index.md`)

<a id="term-project-layout"></a>**Project Layout** · `model:ProjectLayout`  
The standard project structure — `src/`, `tests/`, and their conventions.

- **Part of:** `model:DevelopmentEnvironment`
- **Stored in:** `src/boilerplate/templates/project/` (its `src/` and `tests/` scaffold)
- **See:** the Development Environment guide §Project layout (`docs/environment/index.md`)

<a id="term-workflow"></a>**workflow** · `model:Workflow`  
The steps taken to get a job done. GitHub Actions workflow files keep their own name.

- **Related:** `model:GoldenPath`

<a id="term-golden-path"></a>**golden path** · `model:GoldenPath`  
A **workflow** whose decisions are already thought out for you: the supported, opinionated route through one job, answering *how do we work?* Golden paths nest: each template is a golden path to a starting point, solving the plumbing so a project starts ready for work, and the **dev loop** is the golden path for the everyday work that follows.

- **Kind of:** `model:Workflow`
- **Part of:** `model:ReferenceModel`
- **Related:** `model:DevLoop`, `model:StarterTemplates`, `core:Template`
- **See:** Developer platform architecture §The golden path (`docs/reference/platform/index.md`)
- **Avoid:** paved road, paved path
- **Matches:** paved road, in Netflix's vocabulary per `docs/reference/platform/index.md` (exact)

<a id="term-dev-loop"></a>**dev loop** · `model:DevLoop`  
The cycle you repeat inside a project, which is test-driven development's red-green-refactor: write a failing test (red), make it pass with the least code (green), refactor with the tests still green, then run the checks and commit. Many turns make one pull request, and a release gathers many pull requests.

- **Kind of:** `model:GoldenPath`
- **Part of:** `model:DevelopmentEnvironment`
- **Related:** `model:Slot`
- **Avoid:** inner loop, developer workflow, development workflow

<a id="term-starter-templates"></a>**Starter templates** · `model:StarterTemplates`  
The **Templates**, answering *how do we start?*: each a **golden path** to a starting point that carries the **Toolchain**'s project and editor picks. Outside the reference model, say **Template**.

- **Part of:** `model:ReferenceModel`
- **Related:** `core:Template`, `core:FirstPartyTemplates`, `model:GoldenPath`, `model:Toolchain`, `model:DevelopmentEnvironment`, `model:Curation`
- **See:** Developer platform architecture §Starter templates (`docs/reference/platform/index.md`)

<a id="term-guardrails"></a>**Guardrails** · `model:Guardrails`  
The automated checks that verify a project against the standards its templates configure — dev-time in a **Development Environment** (format-on-save, live type-checking) and in CI — answering *how do we comply?*

- **Part of:** `model:ReferenceModel`
- **Related:** `model:DevelopmentEnvironment`, `trust:FirstPartyGatingScaffolding`, `trust:PostRenderValidation`, `trust:PreconfiguredSubstrate`
- **See:** Developer platform architecture §Guardrails (`docs/reference/platform/index.md`)

### `composition`

How templates layer into one project, and the lock, answers and update mechanics.

<a id="term-extends-based-composition"></a>**extends-based composition** · `composition:ExtendsBasedComposition`  
The static `extends:` mechanism in template metadata that drives composition. Not a runtime feature; resolved at composition time.

- **Related:** `composition:Layer`, `composition:DependencyGraph`, `core:Template`
- **Stored in:** the `extends` field of `boilerplate.yml`
- **Defined in:** `src/boilerplate/models/template_meta.py`, `src/boilerplate/composition/resolution/resolver.py`
- **See:** design 03 §`extends` syntax; design 04 §Stage 1 — Resolver

<a id="term-layer"></a>**Layer** · `composition:Layer`  
One template rendered at a node of the **Dependency Graph**, each with its own **Answers File**; a derived Layer (also "derived template" in prose) `extends` another Template to add or override its files. As a verb, a template *layers* on the template it `extends`; in plain prose, templates build on one another.

- **Kind of:** `core:Template`
- **Part of:** `composition:DependencyGraph`
- **Related:** `composition:ExtendsBasedComposition`, `composition:AnswersFile`, `composition:ScopedView`, `customization:Profile`, `customization:Task`
- **Not to be confused with:** `trust:Substrate` (an enforcement area's mode; PROD-001's `enforcement_layers` key is not a composition Layer)
- **Stored in:** its `LockLayer` record in `boilerplate.lock` and its own `.copier-answers.<layer>.yml`, both in the generated project
- **Defined in:** `src/boilerplate/composition/models/composition_layer.py`, `src/boilerplate/models/lock_layer.py`
- **Avoid:** plugin, overlay, mixin
- **Carve-out:** "overlay merge" names ADR-011's deep-merge strategy for downstream structured-file customization, not this term.

<a id="term-non-git-layer"></a>**Non-git layer** · `composition:NonGitLayer`  
A composition layer whose template source has no git history (a plain filesystem directory or an archive). It records `commit: null` in the lock; `update` skips it with a warning — Copier has no built-in fallback merge for it — and `copier recopy` is the manual refresh.

- **Kind of:** `composition:Layer`
- **Related:** `composition:LockFile`, `composition:SafeUpdate`, `core:Copier`
- **Defined in:** `src/boilerplate/project_state/lock_builder.py` (records no commit for a folder layer)
- **See:** design 06 §Step 4: Three-Way Merge

<a id="term-dependency-graph"></a><a id="term-dag-dependency-graph"></a>**Dependency Graph** · `composition:DependencyGraph`  
The directed acyclic graph (DAG) of template specifiers, derived from `extends` chains.

- **Related:** `core:TemplateSpecifier`, `composition:ExtendsBasedComposition`
- **Defined in:** `src/boilerplate/composition/models/graph.py` (`CompositionGraph`), `src/boilerplate/composition/graph/topology.py`, `src/boilerplate/composition/resolution/resolver.py`
- **See:** design 04 §Stage 2 — Dependency Graph and Topological Sort

<a id="term-template-reference"></a>**Template Reference** · `composition:TemplateReference`  
The input form of a **Template Specifier** — `name` or `name@version` — before resolution.

- **Not to be confused with:** `core:TemplateSpecifier` (the resolved form, always `name@version`)
- **Defined in:** `src/boilerplate/composition/resolution/resolver.py` (the resolver takes it as `template_ref`)
- **See:** design 04 §Template Reference Syntax

<a id="term-scoped-view"></a>**Scoped View** · `composition:ScopedView`  
A Layer's merged questions, secret-question list and Jinja extensions over itself and its ancestors; every render of that Layer, at compose and at update, uses it.

- **Related:** `composition:Layer`, `composition:HiddenQuestion`, `core:Question`
- **Not to be confused with:** `composition:FullMergedSchema` (every Layer's questions joined, not one Layer and its ancestors)
- **Defined in:** `src/boilerplate/composition/views/layer_view.py`, `src/boilerplate/composition/views/layer_view_builder.py`, `src/boilerplate/composition/views/scope_composition.py`
- **See:** design 04 §Scoped view

<a id="term-full-merged-schema"></a>**Full Merged Schema** · `composition:FullMergedSchema`  
Every Layer's questions joined; the questionnaire at compose uses it, and an update step takes each question's definition and default from it.

- **Related:** `core:Question`, `composition:SafeUpdate`
- **Not to be confused with:** `composition:ScopedView` (one Layer and its ancestors only)
- **Defined in:** `src/boilerplate/composition/merging/merger.py`, `src/boilerplate/composition/rendering/questionnaire.py`
- **See:** design 04 §Scoped view and §Safe Update

<a id="term-hidden-question"></a>**Hidden Question** · `composition:HiddenQuestion`  
A Question whose `when` evaluates false under the recorded answers, the literal `when: false` derived questions among them; no Answers File records it.

- **Kind of:** `core:Question`
- **Related:** `composition:AnswersFile`, `composition:ScopedView`
- **Defined in:** `src/boilerplate/composition/rendering/hidden_questions.py`
- **See:** design 04 §Safe Update

<a id="term-renderengine"></a>**RenderEngine** · `composition:RenderEngine`  
The proper-noun class that orchestrates Copier across composition layers.

- **Related:** `core:Copier`, `composition:Layer`, `composition:ScopedView`
- **Defined in:** `src/boilerplate/composition/rendering/engine.py`
- **See:** design 04 §Stage 4 — RenderEngine

<a id="term-plural-shape-architecture"></a>**plural-shape architecture** · `composition:PluralShapeArchitecture`  
Authoring shape that admits future siblings (e.g., `ci-azure-pipelines` today, `ci-github-actions` later) by extending the answer-value enum, not by introducing a breaking schema change.

- **Related:** `core:Question`, `core:FirstPartyTemplates`, `composition:Layer`
- **See:** `docs/intentions/INT-006.yaml`

<a id="term-answers-file"></a><a id="term-copier-answers-layer-yml"></a>**Answers File** · `composition:AnswersFile`  
Records answers given during render, one file per composition layer. Owned by Copier; Boilerplate MUST NOT write to it.

- **Related:** `core:Copier`, `core:Question`, `composition:Layer`, `composition:HiddenQuestion`, `composition:UnmanagedProject`
- **Not to be confused with:** `composition:LockFile` (`boilerplate.lock`, owned by Boilerplate), `customization:AnswerPreset` (a YAML file of answers passed into a render, not Copier's record of one)
- **Stored in:** `.copier-answers.<layer>.yml` in the generated project, where `<layer>` is the layer's invariant name (matches `LockLayer.name`)
- **Defined in:** `src/boilerplate/project_state/answers_file.py`
- **See:** design 04 §Per-Layer Render Loop (the per-layer `_answers_file:` contract) and §Render Behavior
- **Matches:** answers file, in Copier's documentation (exact)

<a id="term-lock-file"></a><a id="term-lock-file-boilerplate-lock"></a>**Lock File** · `composition:LockFile`  
Records exact versions, commit hashes, and checksums used. Owned by Boilerplate.

- **Related:** `composition:ManagedProject`, `composition:Layer`, `composition:NonGitLayer`, `trust:TOFU`, `trust:TrustLevel`
- **Not to be confused with:** `composition:AnswersFile` (owned by Copier; records answers, not versions)
- **Stored in:** `boilerplate.lock` in a managed project
- **Defined in:** `src/boilerplate/models/boilerplate_lock.py`, `src/boilerplate/models/lock_layer.py`, `src/boilerplate/project_state/lock_file.py`, `src/boilerplate/project_state/lock_builder.py`
- **See:** design 02 §Lock File Model; design 06 §Step 4: Lock File Generation

<a id="term-managed-project"></a>**Managed project** · `composition:ManagedProject`  
A project Boilerplate tracks and can update: it has a `boilerplate.lock`. `adopt` transitions an unmanaged project to managed.

- **Related:** `composition:LockFile`
- **Not to be confused with:** `composition:UnmanagedProject` (Copier answers files but no `boilerplate.lock`)
- **Defined in:** `src/boilerplate/composition/adding/layer_adder.py` (the lock-present precondition), `src/boilerplate/common/exceptions.py` (`ProjectNotManagedError`)
- **See:** design 06 §Part 2.5: Project Adoption

<a id="term-unmanaged-project"></a>**Unmanaged project** · `composition:UnmanagedProject`  
A project with Copier answers file(s) (`.copier-answers.*`) but no `boilerplate.lock` — e.g. a plain `copier copy` project, or one after `eject`. `adopt` transitions it to managed.

- **Related:** `composition:AnswersFile`, `composition:LockFile`
- **Not to be confused with:** `composition:ManagedProject` (has a `boilerplate.lock`; Boilerplate tracks and can update it)
- **See:** design 06 §Part 2.5: Project Adoption and §Part 2.6: Project Ejection

<a id="term-safe-update"></a>**safe update** · `composition:SafeUpdate`  
The conflict-detected update workflow Boilerplate provides over Copier's per-layer merge: it runs in a **Staging worktree** and pauses on conflict.

- **Related:** `core:Copier`, `composition:FullMergedSchema`, `composition:HiddenQuestion`, `composition:CopyBack`, `composition:RestoreMarker`
- **Defined in:** `src/boilerplate/composition/updating/updater.py`, `src/boilerplate/composition/staging/staging_worktree.py`
- **See:** design 04 §Safe Update for the implementation

<a id="term-staging-worktree"></a>**Staging worktree** · `composition:StagingWorktree`  
The detached git worktree of the project in which `update` and `add` run their per-layer walk, so the user's checkout changes only at the **Copy back**.

- **Related:** `composition:SafeUpdate`, `composition:CopyBack`, `composition:RestoreMarker`
- **Defined in:** `src/boilerplate/composition/staging/staging_worktree.py`
- **See:** design 06 §Staging worktree

<a id="term-copy-back"></a>**Copy back** · `composition:CopyBack`  
The step of `update` and `add` that reproduces the **Staging worktree**'s result in the user's checkout as uncommitted changes: `git restore --source=<commit> --worktree -- :/` from the worktree's last per-layer commit.

- **Related:** `composition:SafeUpdate`, `composition:RestoreMarker`
- **Defined in:** `src/boilerplate/composition/staging/copy_back.py`
- **See:** design 06 §Staging worktree

<a id="term-restore-marker"></a>**Restore marker** · `composition:RestoreMarker`  
The file under the project's git directory, paired with the ref `refs/worktree/boilerplate/restore`, that keeps the state of a copy back cut off midway so a rerun can finish it or the user can set it aside.

- **Related:** `composition:CopyBack`, `composition:SafeUpdate`
- **Stored in:** `boilerplate-restore.json` in the project's git directory, with the ref `refs/worktree/boilerplate/restore`
- **Defined in:** `src/boilerplate/composition/staging/restore_marker_file.py`, `src/boilerplate/models/restore_marker.py`
- **See:** design 06 §Interrupted copy back and §Setting a partial update aside

### `customization`

How a user changes what templates produce.

<a id="term-profile"></a>**Profile** · `customization:Profile`  
A user's default answers for Template Questions, read from `profile.toml` and merged into the render — global `[defaults]` plus per-Template `[templates.<name>]`.

- **Related:** `core:Question`, `core:Template`
- **Not to be confused with:** `provisioning:EnvironmentProfile` (`boilerplate-env.yml`, pinned tool versions; unrelated despite the shared word), `customization:AnswerPreset` (a YAML file of answers passed to one render, not a user's standing defaults)
- **Stored in:** `profile.toml` at the Boilerplate config root
- **Defined in:** `src/boilerplate/settings/profile.py`, `src/boilerplate/settings/paths.py`
- **See:** `docs/design/adr-010-profile.md`
- **Avoid:** typed Profile model, org profile, config

<a id="term-answer-preset"></a>**Answer Preset** · `customization:AnswerPreset`  
A set of answers applied to a render declaratively, as a YAML file — for CI/CD use.

- **Related:** `core:Question`
- **Not to be confused with:** `customization:Profile` (a user's standing defaults in `profile.toml`, not a file passed to one render), `composition:AnswersFile` (Copier's per-layer record of answers already given, not an input to a render)
- **Defined in:** `src/boilerplate/cli/commands/new.py` (loads a YAML mapping of answers from `--data-file`)
- **See:** design 05 §Answer Presets; design 10 §Answer Preset Safety

<a id="term-task"></a>**Task** · `customization:Task`  
A command declared in a Template's `_tasks` that runs after rendering — the escape hatch for arbitrary edits.

- **Part of:** `core:Template`
- **Related:** `core:Copier`, `composition:Layer`
- **Stored in:** `_tasks` in the declaring template's `copier.yml`
- **Defined in:** `src/boilerplate/composition/tasks.py`
- **See:** design 04 §Task Execution Order; `docs/design/adr-014-deferred-task-execution.md`
- **Avoid:** hook, script, post-gen step
- **Matches:** task, in Copier's documentation (exact)

### `provisioning`

Installing and pinning the Toolchain.

<a id="term-environment-provisioning"></a>**Environment Provisioning** · `provisioning:EnvironmentProvisioning`  
The subsystem that installs and version-pins a **Development Environment** — the `env apply` flow, providers, and the **EnvironmentProfile**.

- **Related:** `provisioning:EnvironmentProfile`, `provisioning:EnvironmentProvisionRecord`, `provisioning:WASM`, `model:Environment`, `model:Toolchain`, `core:AtomicStagedWritePattern`
- **Not to be confused with:** `model:DevelopmentEnvironment` (the setup itself, which this subsystem installs)
- **See:** design 08
- **Avoid:** Environment Pillar, Environments Pillar

<a id="term-environmentprofile"></a>**EnvironmentProfile** · `provisioning:EnvironmentProfile`  
The declarative input to **Environment Provisioning**: tool versions and configuration.

- **Related:** `provisioning:EnvironmentProvisioning`, `provisioning:EnvironmentProvisionRecord`, `model:Toolchain`, `core:Template`
- **Not to be confused with:** `customization:Profile` (`profile.toml`, a user's default answers to template questions, see ADR-010; the two are unrelated despite the shared word)
- **Stored in:** `boilerplate-env.yml`
- **See:** design 02 §EnvironmentProfile; design 08

<a id="term-environmentprovisionrecord"></a><a id="term-boilerplate-environment-yml"></a>**`EnvironmentProvisionRecord`** · `provisioning:EnvironmentProvisionRecord`  
The schema for the env-state record that **Environment Provisioning** writes. Use this name when discussing structure, and `.boilerplate/environment.yml` when discussing the file.

- **Related:** `provisioning:EnvironmentProvisioning`, `provisioning:EnvironmentProfile`
- **Stored in:** `.boilerplate/environment.yml` in the project
- **See:** design 02 §EnvironmentProvisionRecord; design 08 §State Files

<a id="term-wasm"></a>**WASM** · `provisioning:WASM`  
WebAssembly — the plugin architecture used by proto for cross-platform tool installation.

- **Related:** `provisioning:EnvironmentProvisioning`
- **See:** `docs/design/adr-001-build-vs-adopt.md`; design 10 §Trust Boundaries

### `trust`

What Boilerplate enforces and what it trusts.

<a id="term-substrate"></a>**substrate** · `trust:Substrate`  
The enforcement mode PROD-001 assigns to each area of the product it lists under `enforcement_layers` (the runtime, templates, tool configurations, environments, scaffolded projects) — `enforced` (Boilerplate's own runtime gates and rejects on violation, with no opt-out) or `preconfigured` (defaults are shipped; user-runnable **first-party gating scaffolding** executes the check in third-party venues; the user MAY opt out).

- **Related:** `trust:PostRenderValidation`, `trust:PEPDiscipline`
- **Not to be confused with:** `composition:Layer` (a rendered template; PROD-001's `enforcement_layers` key uses the word for an enforcement area, not a template)
- **Stored in:** `docs/products/PROD-001.yaml` (the `substrate` key of each `enforcement_layers` entry)
- **See:** design 01 §What Boilerplate is

<a id="term-enforced-substrate"></a>**enforced substrate** · `trust:EnforcedSubstrate`  
The `enforced` value of **substrate**: coerce-at-touch-points within Boilerplate's own runtime — schema/parse validation, path-safety (TOCTOU) re-validation, consent/task gating, and lock/checksum verification. Boilerplate rejects on violation with a `BP_*` code; there is no opt-out.

- **Kind of:** `trust:Substrate`
- **Related:** `trust:TrustLevel`, `trust:FirstPartyGatingScaffolding`, `composition:LockFile`
- **Defined in:** `src/boilerplate/common/exceptions.py` (`BP_*` codes), `src/boilerplate/models/boilerplate_lock.py` (lock `schema_version` validation), `src/boilerplate/repository/template_checksum.py` (computes the checksum the lock records; no verification against it found)
- **See:** `docs/products/PROD-001.yaml` `enforcement_layers.product`

<a id="term-preconfigured-substrate"></a>**preconfigured substrate** · `trust:PreconfiguredSubstrate`  
The `preconfigured` value of **substrate**: Boilerplate ships the defaults, and user-runnable **first-party gating scaffolding** executes the check in third-party tools' native venues (CI runners, hook runners); the user MAY opt out.

- **Kind of:** `trust:Substrate`
- **Related:** `trust:FirstPartyGatingScaffolding`, `model:Guardrails`, `trust:PostRenderValidation`
- **See:** `docs/products/PROD-001.yaml` `enforcement_layers.templates` and `enforcement_layers.tool_configurations`

<a id="term-first-party-gating-scaffolding"></a><a id="term-gating-scaffolding"></a>**first-party gating scaffolding** · `trust:FirstPartyGatingScaffolding`  
The CI pipelines, lint configs, and bundled **EnvironmentProfile** files shipped beside templates as user-runnable parts of the **preconfigured substrate**. The user opts in; gates execute in third-party tools' native venues (CI runners, hook runners).

- **Part of:** `trust:PreconfiguredSubstrate`
- **Related:** `core:FirstPartyTemplates`, `model:Guardrails`, `trust:EnforcedSubstrate`, `provisioning:EnvironmentProfile`
- **See:** `docs/products/PROD-001.yaml` `shipped_gating_scaffolding`

<a id="term-post-render-validation"></a>**post-render validation** · `trust:PostRenderValidation`  
Out-of-scope content verdicts performed against generated projects after Boilerplate hands off (detecting drift between shipped defaults and user-edited config). Not enforced; structurally outside Boilerplate's reach.

- **Related:** `trust:Substrate`, `model:Guardrails`
- **See:** `docs/products/PROD-001.yaml` `enforcement_layers.tool_configurations`; `docs/intentions/INT-006.yaml` (`not_included`)

<a id="term-pep-discipline"></a>**PEP discipline** · `trust:PEPDiscipline`  
The convention that when a **PEP** defines the canonical way, first-party templates use it — no custom conventions that duplicate or contradict a PEP.

- **Related:** `core:PEP`, `core:FirstPartyTemplates`, `trust:Substrate`
- **See:** design 01 §Standards compliance in first-party templates; `docs/products/PROD-001.yaml` `enforcement_layers.templates`

<a id="term-trust-level"></a>**Trust Level** · `trust:TrustLevel`  
Binary classification for a template's origin: *trusted* or *untrusted*. Untrusted code is default-deny and requires explicit consent.

- **Related:** `trust:TOFU`, `core:FirstPartyTemplates`, `customization:Task`, `composition:LockFile`
- **Stored in:** the `trust_level` field of each source entry in `boilerplate-sources.yml` in the user's data directory (the implicit first-party source is `trusted`); each lock layer's optional free-form `trust_tier` is a separate field, reserved for richer tiers, that resolution ignores
- **Defined in:** `src/boilerplate/models/lock_layer.py` (the reserved `trust_tier` field only; no code reads `trust_level`)
- **See:** design 03 §Trust and Verification Levels; design 09 §Catalog Source Configuration File

<a id="term-tofu"></a>**TOFU** · `trust:TOFU`  
Trust-on-first-use — a security model where the first interaction with a remote source is trusted, and subsequent interactions are verified against the initial state.

- **Related:** `trust:TrustLevel`, `composition:LockFile`
- **Stored in:** `boilerplate.lock` (the commit hash and checksum captured after the first fetch); the optional pin `expected_commit` on a source entry in `boilerplate-sources.yml`
- **See:** design 03 §Git Source; design 02 §CatalogSource (`expected_commit`)

<!-- --8<-- [end:language] -->

## Rules across modules

- A **Profile** supplies default answers to a Template's **Questions** by name — the key namespace is open; the only reserved grammar is `[defaults]` / `[templates.<name>]`.
- **Tasks** accumulate across composed **Layers** and run once, after the final render.
- Customization escalates in power: **Profile** (a value) < **Layer** (structure) < **Task** (behavior) — reach for the least powerful that works.

## Example dialogue

> **Dev:** "I always want my org's package index in generated projects — is that a Profile?"
> **Maintainer:** "Not the typed Profile model — that's retired. If `project` declares a `package_index_url` **Question**, set it once in your **profile** `[defaults]` and every render fills it. Need a whole file `project` doesn't ship? Author a **Layer** that `extends` it. Need to append to a file it didn't anticipate? Add a **Task**."

## Flagged ambiguities

- **Profile** (typed model) — retired. The pydantic `Profile`/`PackageIndex`/`Container` classes, their resolver, and the original `boilerplate config` command conflated a typed two-field config with a switchable named instance, stamping values through a `_boilerplate` namespace. Retired in favor of a plain default-answers file — the word **profile** is reused for that file (`profile.toml`; see the **Profile** term above), plus **Layers** (structure) and **Tasks** (behavior). Do not reintroduce a _typed_ customization model — "profile" now names a plain file, not a pydantic model.
- The `boilerplate config` command is retired; no `config` command exists today. A repurposed form — named, switchable **profile** **default sets** via `config list` / `config use <name>` / `config show` (kubectl-contexts pattern) — is designed but deferred (see [ADR-010](docs/design/adr-010-profile.md)). Its old typed-**Profile**-model role and `config validate` are gone for good, not deferred.
