# Boilerplate: Product Overview

## What Boilerplate solves

Python projects accumulate friction at four points:

- **Environment drift** — tools, versions, and configurations diverge across machines and contributors.
- **Configuration sprawl** — every new project re-discovers and re-wires linter, formatter, type-checker, and test-runner settings.
- **Onboarding friction** — new contributors spend hours on setup before their first commit.
- **Inconsistent toolchains** — no team-level authority decides which tools and versions win.

These problems compound at organizational scale, where dozens of repositories each accumulate their own configuration debt.

## What Boilerplate is

A catalog of golden paths, Python first. Each derived template is one kind of project done the textbook way — a Typer CLI, a Streamlit or React web app, an MCP server — on a base layer its ecosystem shares, which carries the common standards. A template brings the toolchain its kind of project needs, secondary ones included (a containerized app declares Docker); patterns with a marked place for your code; and its ecosystem's published standards, the PEPs for Python. The environment installs and verifies what the template declares, so a secondary toolchain needs no setup script of its own. Templates compose by `extends`, and a project created from them updates layer by layer as the templates move.

> **Start fast. Stay consistent. Reproduce anywhere.**

Boilerplate has two surfaces:

- **Managed development environment** — the toolchain each template's profile declares (for Python: `uv`, `ruff`, `pyright`, `pytest`, and VS Code workspace settings), installed and version-pinned via `boilerplate env apply`.
- **CLI and template system** — `boilerplate new` scaffolds a project from a curated template; `boilerplate update` applies upstream template changes to existing projects safely; `boilerplate list` and `boilerplate compose` make the catalog navigable.

**The slot model.** A development environment decomposes into recurring roles — [slots](#term-slot) — catalogued in [The Development Environment Landscape](https://therealbillsiegler.github.io/boilerplate/0.4/design/dev-environment-landscape/index.md). Each first-party template declares, through its required profile, the slots its kind of project needs, with one opinionated, preconfigured tool per slot:

- **Declared slots** — the slots its ecosystem's dev loop uses, plus any secondary toolchain.
- **Slots within those slots** — the template pre-wires each tool's per-project configuration (rule sets, strictness, markers, workspace settings).

The environment installs and verifies what the profile declares. Slots no first-party template requires are out of scope; the [landscape page](https://therealbillsiegler.github.io/boilerplate/0.4/design/dev-environment-landscape/#how-boilerplate-maps-onto-the-landscape) states the rule.

Principle enforcement spans two substrates: Boilerplate's runtime *enforces* its own invariants, and the artifacts it ships *preconfigure* principles as machine-checkable defaults. Per-layer assignments are specified in PROD-001 `enforcement_layers`; shipped vs planned gating content lives in PROD-001 `shipped_gating_scaffolding`.

**Python first, with an extensible template system.** The reference implementation is written in Python; most of the first-party catalog is Python, and first-party templates for other ecosystems (a React web app) follow their own ecosystem's standards the way the Python ones follow PEPs. The template system, composition engine, and CLI impose no language requirements on template content. Teams may author templates for any language or framework. PEP 440 is the default versioning standard; SemVer-compatible versions (e.g., `1.2.3`) are valid PEP 440 and work without modification.

### When to use Copier directly

Boilerplate orchestrates Copier — it does not replace it. For some use cases, Copier alone is the right choice:

| Use case                                                        | Recommended tool |
| --------------------------------------------------------------- | ---------------- |
| Single template, no composition                                 | Copier           |
| Single-template projects — `copier update` covers their updates | Copier           |
| Layered templates with `extends` chains                         | Boilerplate      |
| Reproducible project creation with lock files                   | Boilerplate      |
| Multi-layer template updates with three-way merge               | Boilerplate      |
| CI/CD drift detection (`lock verify`)                           | Boilerplate      |
| Environment provisioning (`env apply`)                          | Boilerplate      |

Existing Copier templates work with `boilerplate new` without modification — Boilerplate adds a `boilerplate.yml` metadata file alongside `copier.yml` but does not modify or replace it. The `boilerplate.lock` file is informational; if you stop using Boilerplate, your projects and their Copier answers files are untouched.

## Core Principles

These principles are non-negotiable. Every implementation decision MUST honor them.

### Reproducibility is mandatory

Every created or managed project MUST be reproducible across machines and time. Lock files, pinned tool versions, and deterministic configuration are required at every stage. Changes that reduce determinism MUST be rejected.

> **Scope**: Reproducibility is guaranteed at the *project* level via lock files — a locked project can be reconstructed identically. At the *template declaration* level, unversioned `extends` references (e.g., `extends: [project]`) resolve to the latest available version at resolution time, which may differ across invocations. The lock file captures the exact resolution, ensuring reproducibility from the point of creation forward.

### Templates and environments are both first-class surfaces

The template system is the primary surface; the managed development environment is a real companion surface, scoped to installing and verifying what templates declare. A change to one MUST keep the other aligned: a new CLI behavior that affects scaffolding MUST be reflected in template guidance; a new toolchain capability MUST be reflected in environment profiles; documentation MUST update alongside both.

> *In practice:* `boilerplate new` and `boilerplate env apply` are independent operations, not phases of one workflow. Templates declare what gets rendered; profiles declare what tools render and run it. The first-party `project` template ships with both a `boilerplate.yml` (template surface) and a corresponding `boilerplate-env.yml` (environment surface).

### Safety-first operations

Operations that modify or remove existing managed state (`update`, `add`, `env apply`, `eject`) MUST preview the planned changes and require explicit user confirmation before applying. Operations that create or advance managed state MUST record provenance: project operations write a `MigrationRecord`, and `env apply` writes the `EnvironmentProvisionRecord`. `eject` removes that managed state and records nothing; recovery is to re-`adopt`.

**Forward-looking (no current referent):** Bulk operations MUST require confirmation.

> *In practice:* `boilerplate update`, `boilerplate add` and `boilerplate env apply` display a plan and prompt for confirmation before applying changes. `boilerplate new` writes directly because creating a project into a new directory is not destructive. Provenance is recorded across two domains: `MigrationRecord` entries in `.boilerplate/migrations.yml` cover project-domain operations (create / update / add / adopt), and the `EnvironmentProvisionRecord` in `.boilerplate/environment.yml` records the last applied environment state (`env apply`).

### Atomic Staged Write Pattern and lock ownership

Template rendering MUST follow the [Atomic Staged Write Pattern](https://therealbillsiegler.github.io/boilerplate/0.4/design/07-operational-quality/#atomic-staged-write-pattern): render to a staging area, validate, then commit with no partial state left behind. On failure, the staging area MUST be cleaned up and the destination MUST remain untouched. The `boilerplate.lock` file is owned by Boilerplate and MUST be written only after a successful commit.

> **Platform caveat**: Windows directory rename is not atomic; Boilerplate provides best-effort crash recovery (see [06-project-lifecycle.md](https://therealbillsiegler.github.io/boilerplate/0.4/design/06-project-lifecycle/index.md)).

### Environment lifecycle is managed

Boilerplate manages the toolchain across its full lifecycle — installation, version verification, updates, and cleanup — not just initial scaffolding. Environment setup operations MUST be idempotent (safe to re-run) and fail-fast (halt with diagnostic on error before partial work persists). Tools MUST be verified to exist and meet declared version requirements before any operation that depends on them proceeds.

> *In practice:* `boilerplate env apply` re-runs deterministically — applying the same profile twice produces the same `.protolock` state. Tool-version checks happen before invocation, not lazily during; missing or mismatched tools fail with `BP_ENV_*` codes and remediation guidance, not with downstream subprocess errors.

### Orchestrate tools, do not replace them

Boilerplate MUST orchestrate established external tools (Copier, package managers, version checkers) instead of reimplementing their responsibilities. Ownership boundaries between Boilerplate and integrated tools MUST be explicit in every operation.

Boilerplate MUST use all of its underlying technologies idiomatically, as each technology's own documentation describes, and set the example of doing so. Where the design departs from a technology's idiom, it MUST name the departure and the reason. [ADR-015](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-015-idiomatic-artifacts/index.md) is the principle's worked instance.

### Versioning and compatibility

The Boilerplate tool itself follows Semantic Versioning 2.0.0. Breaking changes MUST be accompanied by a major version bump and documented migration path. Templates use PEP 440 — a SemVer-compatible superset that PEP 440 itself endorses for the `MAJOR.MINOR.PATCH` (clauses 1-8) public-version part. Templates carry versions in this scheme and declare their compatibility constraints.

> *In practice:* PEP 440 is the wire format (see §02 Version). Plain `X.Y.Z` versions are valid in both grammars and order identically; PEP 440 adds Python-ecosystem-specific syntax for pre-release (`1.0a1`), post-release (`1.0.post1`), dev (`1.0.dev1`), and epoch (`1!2.0`) identifiers — those identifiers MUST be expressed in PEP 440 form (not SemVer's `1.0.0-alpha.1` / `1.0.0+abc` forms) because the two grammars order incompatibly outside the X.Y.Z subset. Lock files record exact resolved versions so updates are explicit, never silent.

### Standards compliance in first-party templates

First-party (official) Python templates MUST conform to the relevant Python Enhancement Proposals for every pattern they implement. This includes but is not limited to: PEP 440 (versioning), PEP 508 (dependency specifiers), PEP 517/518 (build system), PEP 621 (project metadata in `pyproject.toml`), PEP 660 (editable installs), and PEP 723 (inline script metadata). When a PEP defines the canonical way to do something, the template MUST use it — no custom conventions that duplicate or contradict a PEP. A first-party template for another ecosystem MUST conform to that ecosystem's published standards and MUST name them in its template guide. Third-party templates are not bound by this requirement, though they are encouraged to follow it.

### Trust-gated catalog federation

Templates are sourced from a federated catalog. Trust is binary — a source is either *trusted* or *untrusted* — and behavioral, not cosmetic: it gates what a template MAY do (execute tasks, load Jinja2 extensions, install plugins), default-deny for untrusted code. Untrusted code requires explicit per-operation consent. The full model — the trusted/untrusted boundary, default-deny task gating, and consent gates — is specified in [03-template-system.md §Trust and Verification Levels](https://therealbillsiegler.github.io/boilerplate/0.4/design/03-template-system/#trust-and-verification-levels).

### Security and privacy defaults

- No secrets in code, configuration, or logs. Use environment variables or a vault.
- Validate and sanitize all external inputs at trust boundaries.
- Redact personal data in logs.
- Fail closed: errors MUST not leak sensitive internal details to the user.

See [10-security.md](https://therealbillsiegler.github.io/boilerplate/0.4/design/10-security/index.md) for the full security specification.

______________________________________________________________________

## Platform Portability

Boilerplate supports Windows, macOS, and Linux. See [07-operational-quality.md §Platform Portability](https://therealbillsiegler.github.io/boilerplate/0.4/design/07-operational-quality/#platform-portability) for platform-specific rules and constraints.

______________________________________________________________________

> **Precedence policies**: Boilerplate uses two distinct precedence rules in different contexts. *Catalog registration* uses first-wins: the first source to register a template name+version owns it — see [02-data-models.md §TemplateCatalog](https://therealbillsiegler.github.io/boilerplate/0.4/design/02-data-models/#templatecatalog). *Composition merging* uses last-wins: later layers override earlier layers' values — see [04-composition-engine.md §Merge Rules](https://therealbillsiegler.github.io/boilerplate/0.4/design/04-composition-engine/#merge-rules).

Persisted artifacts (data models, the lock schema, merge and checksum semantics) are specified most carefully because they outlive any single implementation.

## System Boundaries and External Dependencies

This table covers cross-system boundaries — which tool owns which concern across Boilerplate's external integrations. For per-domain state-file inventories, see [06 §Project State Files](https://therealbillsiegler.github.io/boilerplate/0.4/design/06-project-lifecycle/#project-state-files) (project domain) and [08 §State Files](https://therealbillsiegler.github.io/boilerplate/0.4/design/08-environment-provisioning/#state-files) (environment domain).

| Concern                                                                                                            | Owner                    | Notes                                                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------ | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Template file rendering                                                                                            | Copier                   | Boilerplate orchestrates; Copier renders. See [04-composition-engine.md](https://therealbillsiegler.github.io/boilerplate/0.4/design/04-composition-engine/index.md). |
| Answer collection                                                                                                  | Copier                   | Interactive or defaults mode                                                                                                                                          |
| Copier answers files (per-layer `.copier-answers.<layer>.yml`; singular `.copier-answers.yml` for legacy projects) | Copier                   | Boilerplate MUST NOT write or mutate these files                                                                                                                      |
| `boilerplate.lock`                                                                                                 | Boilerplate              | Written after successful render commit                                                                                                                                |
| Git submodule initialization                                                                                       | Boilerplate              | Initialized recursively before Copier invocation                                                                                                                      |
| Package / dependency resolution                                                                                    | External package manager | Out of scope for the core tool                                                                                                                                        |
| Environment toolchain management                                                                                   | proto                    | Boilerplate orchestrates; proto installs tools. See [ADR-001](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-001-build-vs-adopt/index.md).           |
| `.prototools`                                                                                                      | proto                    | proto's native toolchain declaration; Boilerplate generates from merged profiles                                                                                      |
| `.protolock`                                                                                                       | proto                    | proto's native lock file recording exact tool versions and checksums; enabled by Boilerplate                                                                          |
| `.boilerplate/environment.yml`                                                                                     | Boilerplate              | Records which profile was applied and the resolved `extends` chain                                                                                                    |
| Git initialization                                                                                                 | Git                      | Boilerplate MAY invoke; does not own                                                                                                                                  |

______________________________________________________________________

## Feature Slices

The product is organized into five vertical slices, each independently deliverable.

| Slice | Name                      | Acceptance Criteria                                                                                                                                                                            | CLI Commands                                               | Design Docs                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ----- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 001   | Template Discovery        | `list`, `graph`, `validate` return correct results for first-party and filesystem templates                                                                                                    | `list`, `graph`, `validate`, `test`, `cache warm`          | [03](https://therealbillsiegler.github.io/boilerplate/0.4/design/03-template-system/index.md), [05](https://therealbillsiegler.github.io/boilerplate/0.4/design/05-cli-reference/index.md)                                                                                                                                                                                                                                                                                               |
| 002   | Project Creation          | `new` renders multi-layer compositions atomically with lock file generation                                                                                                                    | `new`, `compose`, `init-template`                          | [02](https://therealbillsiegler.github.io/boilerplate/0.4/design/02-data-models/index.md), [03](https://therealbillsiegler.github.io/boilerplate/0.4/design/03-template-system/index.md), [04](https://therealbillsiegler.github.io/boilerplate/0.4/design/04-composition-engine/index.md), [05](https://therealbillsiegler.github.io/boilerplate/0.4/design/05-cli-reference/index.md), [06](https://therealbillsiegler.github.io/boilerplate/0.4/design/06-project-lifecycle/index.md) |
| 003   | Project Update & Adoption | `update` performs three-way merge; `add` applies one more template layer to a managed project; `adopt` imports Copier-only projects; `eject` stops Boilerplate management (inverse of `adopt`) | `update`, `add`, `adopt`, `eject`, `status`, `lock verify` | [05](https://therealbillsiegler.github.io/boilerplate/0.4/design/05-cli-reference/index.md), [06](https://therealbillsiegler.github.io/boilerplate/0.4/design/06-project-lifecycle/index.md)                                                                                                                                                                                                                                                                                             |
| 004   | Environment Profiles      | `env apply` provisions tools via proto and records the applied state; re-running `env apply` is the recovery path                                                                              | `env apply`, `env status`                                  | [08](https://therealbillsiegler.github.io/boilerplate/0.4/design/08-environment-provisioning/index.md)                                                                                                                                                                                                                                                                                                                                                                                   |
| 005   | Operational Quality       | `doctor` validates system health; structured logging and error codes operational                                                                                                               | `doctor`                                                   | [07](https://therealbillsiegler.github.io/boilerplate/0.4/design/07-operational-quality/index.md)                                                                                                                                                                                                                                                                                                                                                                                        |
| —     | Developer Experience      | —                                                                                                                                                                                              | —                                                          | [05](https://therealbillsiegler.github.io/boilerplate/0.4/design/05-cli-reference/index.md)                                                                                                                                                                                                                                                                                                                                                                                              |

See [Implementation Status](https://therealbillsiegler.github.io/boilerplate/0.4/status/index.md).

### Environment Profiles

Declarative profiles (`boilerplate-env.yml`) pin the development toolchain per project and compose via `extends`. Boilerplate resolves the chain and writes `.prototools` (proto's native input); proto installs tools and writes `.protolock` (exact versions + checksums). Boilerplate writes `.boilerplate/environment.yml` for profile provenance. Same "orchestrate, don't replace" pattern as Copier — see [ADR-001](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-001-build-vs-adopt/index.md). Operational contract: [§08 Environment Provisioning](https://therealbillsiegler.github.io/boilerplate/0.4/design/08-environment-provisioning/index.md).

______________________________________________________________________

## High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                                CLI                                   │
│  Project:  new | update | add | status | adopt | eject               │
│  Template: list | compose | graph | validate | test | init-template  │
│  System:   doctor | env | lock | cache                               │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ commands invoke
               ┌────────────────▼────────────────┐
               │        Application Layer         │
               │  Resolver  Composer  Render       │
               │  Updater   Profiler               │
               └───────┬────────────────┬─────────┘
                       │                │
          Templates                Environment Provisioning
                       │                │
    ┌──────────────────▼───────┐  ┌─────▼──────────────────┐
    │      Template Catalog    │  │    ProfileCatalog       │
    │  TemplateCatalog         │  │  (profile index)        │
    │  (in-memory index)       │  └─────┬──────────────────┘
    └──────────────────┬───────┘        │ delegates to
                       │          ┌─────▼──────────────────┐
                       │          │      ProtoWorker        │
         populated by  │          │  (orchestrates proto)   │
                       │          └─────┬──────────────────┘
    ┌──────────────────▼───────┐        │ invokes
    │    Template Repository   │  ┌─────▼──────────────────┐
    │  DirectoryTemplateRepository │  │    proto (external)     │
    │  RemoteSource            │  │  tool install & manage  │
    └──────────────────┬───────┘  └────────────────────────┘
                       │ reads
    ┌──────────────────▼───────┐
    │   Template Files on Disk │
    │  boilerplate.yml         │
    │  copier.yml | src        │
    └──────────────────────────┘
```

### Layer responsibilities

**CLI** — Parses user input, bootstraps the runtime context (settings, logging, display), dispatches to application services, and renders output. The CLI MUST NOT contain business logic.

**Application Layer** — Contains all domain logic: resolving dependency graphs, merging configurations, orchestrating renders, computing update plans, and managing profiles.

**Template Catalog** — An in-memory index populated at startup from one or more repositories. Provides lookup by canonical tag (`name@version`) and by name (resolves to latest).

**Template Repository** — Discovers and loads templates from a source (local directory, remote registry). Produces `TemplateInfo` records for catalog registration.

**Template Files** — The on-disk artifacts. Each template MUST contain a `boilerplate.yml` (Boilerplate metadata) and a `copier.yml` (Copier questionnaire). Templates MAY extend other templates via `boilerplate.yml`.

______________________________________________________________________

## Runtime Configuration (Settings)

The runtime is configured by a `Settings` object loaded from environment variables and an optional `.env` file. See [09-settings-and-configuration.md](https://therealbillsiegler.github.io/boilerplate/0.4/design/09-settings-and-configuration/index.md) for the complete Settings specification, including all fields, env var names, types, and defaults, and for the `boilerplate-sources.yml` configuration file.

______________________________________________________________________

## Glossary

Core terms used throughout this document suite. For data model details see [02-data-models.md](https://therealbillsiegler.github.io/boilerplate/0.4/design/02-data-models/index.md); for composition details see [04-composition-engine.md](https://therealbillsiegler.github.io/boilerplate/0.4/design/04-composition-engine/index.md). Canonical definitions live in `CONTEXT.md` at the repository root.

Target-state vocabulary

These definitions describe the design. [Implementation status](https://therealbillsiegler.github.io/boilerplate/0.4/status/index.md) records which parts exist today.

### `core`

Concepts every module uses.

**Copier** · `core:Copier`\
The external tool ([Copier](https://copier.readthedocs.io/)) responsible for file rendering, answer collection, and task execution. Boilerplate orchestrates Copier without replacing it.

- **Related:** `core:Template`, `core:Question`, `composition:AnswersFile`, `composition:RenderEngine`, `customization:Task`
- **Defined in:** `src/boilerplate/integrations/copier_types.py` (the single audited import point for the Copier internals Boilerplate uses)
- **See:** `docs/design/adr-001-build-vs-adopt.md`; `docs/design/adr-002-copier-internals-shim.md`

**Template** · `core:Template`\
A directory containing `boilerplate.yml` (name, version, `extends`) and `copier.yml` that boilerplate renders into a project — a Copier scaffold. Its filesystem location is the **template root**.

- **Related:** `core:Copier`, `core:Question`, `core:TemplateSpecifier`, `composition:Layer`, `customization:Task`, `model:StarterTemplates`, `model:GoldenPath`
- **Stored in:** `boilerplate.yml`, Boilerplate-specific metadata (name, version, and dependencies through `extends`), and `copier.yml`, Copier's questionnaire (questions and tasks), both at the template root, for example `src/boilerplate/templates/project/boilerplate.yml` and `src/boilerplate/templates/project/copier.yml`. Copier owns `copier.yml`; Boilerplate reads it and MUST NOT write to it.
- **Defined in:** `src/boilerplate/models/template_meta.py` (`TemplateMeta`, the `boilerplate.yml` schema), `src/boilerplate/models/template_info.py`
- **See:** design 02 §TemplateMeta; design 03 §`boilerplate.yml` Schema
- **Avoid:** generator, skeleton, blueprint
- **Carve-out:** "template skeleton" names the `init-template` command's scaffold output, not this term.
- **Matches:** template, in Copier's documentation (close: Copier's template is a directory, usually a Git repository's root, with an optional `copier.yml`; a Template here also carries `boilerplate.yml`)

**first-party templates** · `core:FirstPartyTemplates`\
Templates Boilerplate publishes as their own git repositories, extracted from the authoring monorepo at release time — the canonical first-party distribution channel (versus user-provided or third-party templates).

- **Kind of:** `core:Template`
- **Related:** `model:StarterTemplates`, `trust:TrustLevel`, `trust:FirstPartyGatingScaffolding`, `trust:PEPDiscipline`, `core:PEP`
- **Stored in:** `src/boilerplate/templates/` (the authoring monorepo's copies)
- **See:** `docs/design/adr-006-template-distribution.md`; design 03 §First-Party Templates

**Template Specifier** · `core:TemplateSpecifier`\
A `name@version` string uniquely identifying a template — the resolved form.

- **Related:** `core:Template`, `composition:DependencyGraph`
- **Not to be confused with:** `composition:TemplateReference` (the unresolved input form, which may omit the version)
- **Defined in:** `src/boilerplate/types/template_specifier.py`
- **See:** design 02 §TemplateSpecifier

**Question** · `core:Question`\
A Copier-declared input on a Template, whose answer fills the rendered output; a Template declares zero or more in `copier.yml`.

- **Part of:** `core:Template`
- **Related:** `core:Copier`, `composition:AnswersFile`, `composition:HiddenQuestion`, `composition:ScopedView`, `composition:FullMergedSchema`, `customization:Profile`, `customization:AnswerPreset`
- **Stored in:** the declaring template's `copier.yml` (owned by Copier; Boilerplate reads it and MUST NOT write to it)
- **Defined in:** `src/boilerplate/integrations/copier_types.py` (Copier's `Question`, imported), `src/boilerplate/composition/merging/strategies.py` (`merge_questions`)
- **Avoid:** variable, prompt, field
- **Matches:** question, in Copier's documentation (exact)

**schema v1** · `core:SchemaV1`\
The first generation of this design suite's on-disk contracts (`schema_version` major `1`, e.g. `"1"` / `"boilerplate/lock@1"`). Independent of the tool's release version (SemVer `0.x` until the first stable `1.0`), which tracks implementation maturity, not contract generation.

- **Related:** `core:Template`, `composition:LockFile`
- **Stored in:** the `schema_version` field of `boilerplate.yml` and of `boilerplate.lock`
- **Defined in:** `src/boilerplate/models/template_meta.py`, `src/boilerplate/models/boilerplate_lock.py`
- **See:** design 03 §Schema Evolution

**PEP** · `core:PEP`\
Python Enhancement Proposal — the standards process for the Python language. Referenced PEPs: 440 (versioning), 508 (dependency specifiers), 517/518 (build system), 621 (project metadata), 660 (editable installs), 723 (inline script metadata).

- **Related:** `trust:PEPDiscipline`, `core:FirstPartyTemplates`
- **See:** design 01 §Standards compliance in first-party templates

**Atomic Staged Write Pattern** · `core:AtomicStagedWritePattern`\
Boilerplate's stage-then-rename file-emission discipline: stage in an isolated directory, validate, then atomically move into place.

- **Related:** `composition:SafeUpdate`, `provisioning:EnvironmentProvisioning`
- **Defined in:** `src/boilerplate/project_state/atomic_write.py`, `src/boilerplate/composition/staging/staging_worktree.py`, `src/boilerplate/composition/staging/intent_journal.py`, `src/boilerplate/composition/staging/stale_cleanup.py`
- **See:** design 07 §Atomic Staged Write Pattern (canonical definition)

**Settings** · `core:Settings`\
Boilerplate's own runtime configuration: one immutable object, loaded once at CLI startup and passed to every application service.

- **Related:** `customization:Profile`
- **Not to be confused with:** `model:Configuration` (the Toolchain's settings in a generated project, not Boilerplate's own)
- **Stored in:** compiled-in defaults, overridden by a `.env` file in the current directory, then by `BOILERPLATE_*` environment variables
- **Defined in:** `src/boilerplate/settings/settings.py`
- **See:** design 09 §Settings

### `model`

The reference model: what Boilerplate is.

**Reference model** · `model:ReferenceModel`\
The model of what Boilerplate is: **Curation** picks the **Toolchain** from the **Tool landscape**; the **Toolchain** is a part of the **Development Environment**, and the **Starter templates** carry it too; **golden paths** run on it; **Guardrails** check the work. Every other statement of what Boilerplate is derives from it.

- **Related:** `model:Curation`
- **See:** Developer platform architecture §The model (`docs/reference/platform/index.md`), which owns it

**Environment** · `model:Environment`\
The problem domain — a developer's setup and its tendency to diverge across machines and time ("environment drift") — and the umbrella over the **Development Environment** (the thing) and **Environment Provisioning** (the subsystem). In prose, avoid the bare word where one specific sense is meant.

- **Related:** `model:DevelopmentEnvironment`, `provisioning:EnvironmentProvisioning`

**Tool landscape** · `model:ToolLandscape`\
The descriptive catalog of the tools, technologies and practices available in a domain, organized by **slot**, answering *what exists?*; the **Toolchain** is curated from it. Boilerplate keeps it as the Development Environment Landscape guide.

- **Part of:** `model:ReferenceModel`
- **Related:** `model:Slot`, `model:Curation`, `model:Toolchain`
- **Stored in:** `docs/design/dev-environment-landscape.md`
- **See:** Developer platform architecture §The tool landscape (`docs/reference/platform/index.md`)

**slot** · `model:Slot`\
One recurring role in a development environment (linter, type checker, test runner, …). Each first-party template fills the slots its ecosystem's **dev loop** uses with one opinionated tool each; the template then fills slots *within* those slots (each tool's per-project configuration).

- **Part of:** `model:ToolLandscape`
- **Related:** `model:Toolchain`, `model:Configuration`, `model:DevLoop`, `core:FirstPartyTemplates`
- **See:** design 01 §What Boilerplate is (the slot model); `docs/design/dev-environment-landscape.md`, which catalogues the slots

**Curation** · `model:Curation`\
Choosing the **Toolchain**'s picks from the **Tool landscape** as a set, each for how it works with the others, then configuring them together and maintaining them together. It joins the **Development Environment** and the **Starter templates**, which carry the same picks.

- **Related:** `model:ReferenceModel`, `model:ToolLandscape`, `model:Toolchain`, `model:DevelopmentEnvironment`, `model:StarterTemplates`

**Toolchain** · `model:Toolchain`\
The development tools Boilerplate picks and sets up, one per **slot** (uv, Ruff, Pyright, pytest, …), chosen by **Curation** from the **Tool landscape**, whether or not their versions are pinned; it answers *what do we use?* and is not an application's own framework stack. **Environment Provisioning** pins the tools through an **EnvironmentProfile**, and not every pick is pinned (the editor and git are not).

- **Part of:** `model:DevelopmentEnvironment`
- **Related:** `model:Slot`, `model:Curation`, `model:ToolLandscape`, `model:Configuration`, `model:StarterTemplates`, `provisioning:EnvironmentProvisioning`, `provisioning:EnvironmentProfile`
- **Not to be confused with:** `model:DevelopmentEnvironment` (which contains the Toolchain; not a synonym)
- **See:** Developer platform architecture §The toolchain (`docs/reference/platform/index.md`)
- **Avoid:** curated stack, dev stack, tech stack
- **Carve-out:** the slogan "Less Yak. More Stack." puns on the toolchain handed to you and templates stacking; outside it, a template **layers** on another. The reference model page names "curated stack" once, as something the toolchain is sometimes called.
- **Matches:** curated stack, in platform engineering per `docs/reference/platform/index.md` (close)

**Development Environment** · `model:DevelopmentEnvironment`\
The setup a developer works in, on the machine, in the project and in the editor: the **Toolchain**, its **Configuration** (`pyproject.toml`, `.vscode/`), the **Project Layout**, and the **dev loop**. In the reference model the **Toolchain** is a part of it, and the **Starter templates** sit beside it.

- **Part of:** `model:ReferenceModel`
- **Related:** `model:Environment`, `model:StarterTemplates`, `model:Configuration`, `model:ProjectLayout`, `model:DevLoop`
- **Not to be confused with:** `model:Toolchain` (one of its parts, not a synonym), `provisioning:EnvironmentProvisioning` (the subsystem that installs it and pins the Toolchain's versions)
- **See:** the Development Environment guide (`docs/environment/index.md`)

**Configuration** · `model:Configuration`\
The settings that wire the **Toolchain** into a project — `pyproject.toml` and `.vscode/`.

- **Part of:** `model:DevelopmentEnvironment`
- **Related:** `model:Toolchain`, `model:Slot`, `provisioning:EnvironmentProfile`
- **Not to be confused with:** `core:Settings` (Boilerplate's own runtime configuration, not a generated project's)
- **Stored in:** a generated project's `pyproject.toml` and `.vscode/`, rendered from `src/boilerplate/templates/project/pyproject.toml.jinja` and `src/boilerplate/templates/project/.vscode/`
- **See:** the Development Environment guide §Configuration (`docs/environment/index.md`)

**Project Layout** · `model:ProjectLayout`\
The standard project structure — `src/`, `tests/`, and their conventions.

- **Part of:** `model:DevelopmentEnvironment`
- **Stored in:** `src/boilerplate/templates/project/` (its `src/` and `tests/` scaffold)
- **See:** the Development Environment guide §Project layout (`docs/environment/index.md`)

**workflow** · `model:Workflow`\
The steps taken to get a job done. GitHub Actions workflow files keep their own name.

- **Related:** `model:GoldenPath`

**golden path** · `model:GoldenPath`\
A **workflow** whose decisions are already thought out for you: the supported, opinionated route through one job, answering *how do we work?* Golden paths nest: each template is a golden path to a starting point, solving the plumbing so a project starts ready for work, and the **dev loop** is the golden path for the everyday work that follows.

- **Kind of:** `model:Workflow`
- **Part of:** `model:ReferenceModel`
- **Related:** `model:DevLoop`, `model:StarterTemplates`, `core:Template`
- **See:** Developer platform architecture §The golden path (`docs/reference/platform/index.md`)
- **Avoid:** paved road, paved path
- **Matches:** paved road, in Netflix's vocabulary per `docs/reference/platform/index.md` (exact)

**dev loop** · `model:DevLoop`\
The cycle you repeat inside a project, which is test-driven development's red-green-refactor: write a failing test (red), make it pass with the least code (green), refactor with the tests still green, then run the checks and commit. Many turns make one pull request, and a release gathers many pull requests.

- **Kind of:** `model:GoldenPath`
- **Part of:** `model:DevelopmentEnvironment`
- **Related:** `model:Slot`
- **Avoid:** inner loop, developer workflow, development workflow

**Starter templates** · `model:StarterTemplates`\
The **Templates**, answering *how do we start?*: each a **golden path** to a starting point that carries the **Toolchain**'s project and editor picks. Outside the reference model, say **Template**.

- **Part of:** `model:ReferenceModel`
- **Related:** `core:Template`, `core:FirstPartyTemplates`, `model:GoldenPath`, `model:Toolchain`, `model:DevelopmentEnvironment`, `model:Curation`
- **See:** Developer platform architecture §Starter templates (`docs/reference/platform/index.md`)

**Guardrails** · `model:Guardrails`\
The automated checks that verify a project against the standards its templates configure — dev-time in a **Development Environment** (format-on-save, live type-checking) and in CI — answering *how do we comply?*

- **Part of:** `model:ReferenceModel`
- **Related:** `model:DevelopmentEnvironment`, `trust:FirstPartyGatingScaffolding`, `trust:PostRenderValidation`, `trust:PreconfiguredSubstrate`
- **See:** Developer platform architecture §Guardrails (`docs/reference/platform/index.md`)

### `composition`

How templates layer into one project, and the lock, answers and update mechanics.

**extends-based composition** · `composition:ExtendsBasedComposition`\
The static `extends:` mechanism in template metadata that drives composition. Not a runtime feature; resolved at composition time.

- **Related:** `composition:Layer`, `composition:DependencyGraph`, `core:Template`
- **Stored in:** the `extends` field of `boilerplate.yml`
- **Defined in:** `src/boilerplate/models/template_meta.py`, `src/boilerplate/composition/resolution/resolver.py`
- **See:** design 03 §`extends` syntax; design 04 §Stage 1 — Resolver

**Layer** · `composition:Layer`\
One template rendered at a node of the **Dependency Graph**, each with its own **Answers File**; a derived Layer (also "derived template" in prose) `extends` another Template to add or override its files. As a verb, a template *layers* on the template it `extends`; in plain prose, templates build on one another.

- **Kind of:** `core:Template`
- **Part of:** `composition:DependencyGraph`
- **Related:** `composition:ExtendsBasedComposition`, `composition:AnswersFile`, `composition:ScopedView`, `customization:Profile`, `customization:Task`
- **Not to be confused with:** `trust:Substrate` (an enforcement area's mode; PROD-001's `enforcement_layers` key is not a composition Layer)
- **Stored in:** its `LockLayer` record in `boilerplate.lock` and its own `.copier-answers.<layer>.yml`, both in the generated project
- **Defined in:** `src/boilerplate/composition/models/composition_layer.py`, `src/boilerplate/models/lock_layer.py`
- **Avoid:** plugin, overlay, mixin
- **Carve-out:** "overlay merge" names ADR-011's deep-merge strategy for downstream structured-file customization, not this term.

**Non-git layer** · `composition:NonGitLayer`\
A composition layer whose template source has no git history (a plain filesystem directory or an archive). It records `commit: null` in the lock; `update` skips it with a warning — Copier has no built-in fallback merge for it — and `copier recopy` is the manual refresh.

- **Kind of:** `composition:Layer`
- **Related:** `composition:LockFile`, `composition:SafeUpdate`, `core:Copier`
- **Defined in:** `src/boilerplate/project_state/lock_builder.py` (records no commit for a folder layer)
- **See:** design 06 §Step 4: Three-Way Merge

**Dependency Graph** · `composition:DependencyGraph`\
The directed acyclic graph (DAG) of template specifiers, derived from `extends` chains.

- **Related:** `core:TemplateSpecifier`, `composition:ExtendsBasedComposition`
- **Defined in:** `src/boilerplate/composition/models/graph.py` (`CompositionGraph`), `src/boilerplate/composition/graph/topology.py`, `src/boilerplate/composition/resolution/resolver.py`
- **See:** design 04 §Stage 2 — Dependency Graph and Topological Sort

**Template Reference** · `composition:TemplateReference`\
The input form of a **Template Specifier** — `name` or `name@version` — before resolution.

- **Not to be confused with:** `core:TemplateSpecifier` (the resolved form, always `name@version`)
- **Defined in:** `src/boilerplate/composition/resolution/resolver.py` (the resolver takes it as `template_ref`)
- **See:** design 04 §Template Reference Syntax

**Scoped View** · `composition:ScopedView`\
A Layer's merged questions, secret-question list and Jinja extensions over itself and its ancestors; every render of that Layer, at compose and at update, uses it.

- **Related:** `composition:Layer`, `composition:HiddenQuestion`, `core:Question`
- **Not to be confused with:** `composition:FullMergedSchema` (every Layer's questions joined, not one Layer and its ancestors)
- **Defined in:** `src/boilerplate/composition/views/layer_view.py`, `src/boilerplate/composition/views/layer_view_builder.py`, `src/boilerplate/composition/views/scope_composition.py`
- **See:** design 04 §Scoped view

**Full Merged Schema** · `composition:FullMergedSchema`\
Every Layer's questions joined; the questionnaire at compose uses it, and an update step takes each question's definition and default from it.

- **Related:** `core:Question`, `composition:SafeUpdate`
- **Not to be confused with:** `composition:ScopedView` (one Layer and its ancestors only)
- **Defined in:** `src/boilerplate/composition/merging/merger.py`, `src/boilerplate/composition/rendering/questionnaire.py`
- **See:** design 04 §Scoped view and §Safe Update

**Hidden Question** · `composition:HiddenQuestion`\
A Question whose `when` evaluates false under the recorded answers, the literal `when: false` derived questions among them; no Answers File records it.

- **Kind of:** `core:Question`
- **Related:** `composition:AnswersFile`, `composition:ScopedView`
- **Defined in:** `src/boilerplate/composition/rendering/hidden_questions.py`
- **See:** design 04 §Safe Update

**RenderEngine** · `composition:RenderEngine`\
The proper-noun class that orchestrates Copier across composition layers.

- **Related:** `core:Copier`, `composition:Layer`, `composition:ScopedView`
- **Defined in:** `src/boilerplate/composition/rendering/engine.py`
- **See:** design 04 §Stage 4 — RenderEngine

**plural-shape architecture** · `composition:PluralShapeArchitecture`\
Authoring shape that admits future siblings (e.g., `ci-azure-pipelines` today, `ci-github-actions` later) by extending the answer-value enum, not by introducing a breaking schema change.

- **Related:** `core:Question`, `core:FirstPartyTemplates`, `composition:Layer`
- **See:** `docs/intentions/INT-006.yaml`

**Answers File** · `composition:AnswersFile`\
Records answers given during render, one file per composition layer. Owned by Copier; Boilerplate MUST NOT write to it.

- **Related:** `core:Copier`, `core:Question`, `composition:Layer`, `composition:HiddenQuestion`, `composition:UnmanagedProject`
- **Not to be confused with:** `composition:LockFile` (`boilerplate.lock`, owned by Boilerplate), `customization:AnswerPreset` (a YAML file of answers passed into a render, not Copier's record of one)
- **Stored in:** `.copier-answers.<layer>.yml` in the generated project, where `<layer>` is the layer's invariant name (matches `LockLayer.name`)
- **Defined in:** `src/boilerplate/project_state/answers_file.py`
- **See:** design 04 §Per-Layer Render Loop (the per-layer `_answers_file:` contract) and §Render Behavior
- **Matches:** answers file, in Copier's documentation (exact)

**Lock File** · `composition:LockFile`\
Records exact versions, commit hashes, and checksums used. Owned by Boilerplate.

- **Related:** `composition:ManagedProject`, `composition:Layer`, `composition:NonGitLayer`, `trust:TOFU`, `trust:TrustLevel`
- **Not to be confused with:** `composition:AnswersFile` (owned by Copier; records answers, not versions)
- **Stored in:** `boilerplate.lock` in a managed project
- **Defined in:** `src/boilerplate/models/boilerplate_lock.py`, `src/boilerplate/models/lock_layer.py`, `src/boilerplate/project_state/lock_file.py`, `src/boilerplate/project_state/lock_builder.py`
- **See:** design 02 §Lock File Model; design 06 §Step 4: Lock File Generation

**Managed project** · `composition:ManagedProject`\
A project Boilerplate tracks and can update: it has a `boilerplate.lock`. `adopt` transitions an unmanaged project to managed.

- **Related:** `composition:LockFile`
- **Not to be confused with:** `composition:UnmanagedProject` (Copier answers files but no `boilerplate.lock`)
- **Defined in:** `src/boilerplate/composition/adding/layer_adder.py` (the lock-present precondition), `src/boilerplate/common/exceptions.py` (`ProjectNotManagedError`)
- **See:** design 06 §Part 2.5: Project Adoption

**Unmanaged project** · `composition:UnmanagedProject`\
A project with Copier answers file(s) (`.copier-answers.*`) but no `boilerplate.lock` — e.g. a plain `copier copy` project, or one after `eject`. `adopt` transitions it to managed.

- **Related:** `composition:AnswersFile`, `composition:LockFile`
- **Not to be confused with:** `composition:ManagedProject` (has a `boilerplate.lock`; Boilerplate tracks and can update it)
- **See:** design 06 §Part 2.5: Project Adoption and §Part 2.6: Project Ejection

**safe update** · `composition:SafeUpdate`\
The conflict-detected update workflow Boilerplate provides over Copier's per-layer merge: it runs in a **Staging worktree** and pauses on conflict.

- **Related:** `core:Copier`, `composition:FullMergedSchema`, `composition:HiddenQuestion`, `composition:CopyBack`, `composition:RestoreMarker`
- **Defined in:** `src/boilerplate/composition/updating/updater.py`, `src/boilerplate/composition/staging/staging_worktree.py`
- **See:** design 04 §Safe Update for the implementation

**Staging worktree** · `composition:StagingWorktree`\
The detached git worktree of the project in which `update` and `add` run their per-layer walk, so the user's checkout changes only at the **Copy back**.

- **Related:** `composition:SafeUpdate`, `composition:CopyBack`, `composition:RestoreMarker`
- **Defined in:** `src/boilerplate/composition/staging/staging_worktree.py`
- **See:** design 06 §Staging worktree

**Copy back** · `composition:CopyBack`\
The step of `update` and `add` that reproduces the **Staging worktree**'s result in the user's checkout as uncommitted changes: `git restore --source=<commit> --worktree -- :/` from the worktree's last per-layer commit.

- **Related:** `composition:SafeUpdate`, `composition:RestoreMarker`
- **Defined in:** `src/boilerplate/composition/staging/copy_back.py`
- **See:** design 06 §Staging worktree

**Restore marker** · `composition:RestoreMarker`\
The file under the project's git directory, paired with the ref `refs/worktree/boilerplate/restore`, that keeps the state of a copy back cut off midway so a rerun can finish it or the user can set it aside.

- **Related:** `composition:CopyBack`, `composition:SafeUpdate`
- **Stored in:** `boilerplate-restore.json` in the project's git directory, with the ref `refs/worktree/boilerplate/restore`
- **Defined in:** `src/boilerplate/composition/staging/restore_marker_file.py`, `src/boilerplate/models/restore_marker.py`
- **See:** design 06 §Interrupted copy back and §Setting a partial update aside

### `customization`

How a user changes what templates produce.

**Profile** · `customization:Profile`\
A user's default answers for Template Questions, read from `profile.toml` and merged into the render — global `[defaults]` plus per-Template `[templates.<name>]`.

- **Related:** `core:Question`, `core:Template`
- **Not to be confused with:** `provisioning:EnvironmentProfile` (`boilerplate-env.yml`, pinned tool versions; unrelated despite the shared word), `customization:AnswerPreset` (a YAML file of answers passed to one render, not a user's standing defaults)
- **Stored in:** `profile.toml` at the Boilerplate config root
- **Defined in:** `src/boilerplate/settings/profile.py`, `src/boilerplate/settings/paths.py`
- **See:** `docs/design/adr-010-profile.md`
- **Avoid:** typed Profile model, org profile, config

**Answer Preset** · `customization:AnswerPreset`\
A YAML file of answers passed with `--data-file` to `new`, `update` or `add`, which forces those answers for one run — for CI/CD use or to repeat a project.

- **Related:** `core:Question`
- **Not to be confused with:** `customization:Profile` (a user's standing defaults in `profile.toml`, not a file passed to one render), `composition:AnswersFile` (Copier's per-layer record of answers already given; the template's answers file from a finished `new` can be passed as a preset)
- **Defined in:** `src/boilerplate/cli/commands/new.py` (loads a YAML mapping of answers from `--data-file`)
- **See:** design 05 §Answer Presets; design 10 §Answer Preset Safety

**Task** · `customization:Task`\
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

**Environment Provisioning** · `provisioning:EnvironmentProvisioning`\
The subsystem that installs and version-pins a **Development Environment** — the `env apply` flow, providers, and the **EnvironmentProfile**.

- **Related:** `provisioning:EnvironmentProfile`, `provisioning:EnvironmentProvisionRecord`, `provisioning:WASM`, `model:Environment`, `model:Toolchain`, `core:AtomicStagedWritePattern`
- **Not to be confused with:** `model:DevelopmentEnvironment` (the setup itself, which this subsystem installs)
- **See:** design 08
- **Avoid:** Environment Pillar, Environments Pillar

**EnvironmentProfile** · `provisioning:EnvironmentProfile`\
The declarative input to **Environment Provisioning**: tool versions and configuration.

- **Related:** `provisioning:EnvironmentProvisioning`, `provisioning:EnvironmentProvisionRecord`, `model:Toolchain`, `core:Template`
- **Not to be confused with:** `customization:Profile` (`profile.toml`, a user's default answers to template questions, see ADR-010; the two are unrelated despite the shared word)
- **Stored in:** `boilerplate-env.yml`
- **See:** design 02 §EnvironmentProfile; design 08

**`EnvironmentProvisionRecord`** · `provisioning:EnvironmentProvisionRecord`\
The schema for the env-state record that **Environment Provisioning** writes. Use this name when discussing structure, and `.boilerplate/environment.yml` when discussing the file.

- **Related:** `provisioning:EnvironmentProvisioning`, `provisioning:EnvironmentProfile`
- **Stored in:** `.boilerplate/environment.yml` in the project
- **See:** design 02 §EnvironmentProvisionRecord; design 08 §State Files

**WASM** · `provisioning:WASM`\
WebAssembly — the plugin architecture used by proto for cross-platform tool installation.

- **Related:** `provisioning:EnvironmentProvisioning`
- **See:** `docs/design/adr-001-build-vs-adopt.md`; design 10 §Trust Boundaries

### `trust`

What Boilerplate enforces and what it trusts.

**substrate** · `trust:Substrate`\
The enforcement mode PROD-001 assigns to each area of the product it lists under `enforcement_layers` (the runtime, templates, tool configurations, environments, scaffolded projects) — `enforced` (Boilerplate's own runtime gates and rejects on violation, with no opt-out) or `preconfigured` (defaults are shipped; user-runnable **first-party gating scaffolding** executes the check in third-party venues; the user MAY opt out).

- **Related:** `trust:PostRenderValidation`, `trust:PEPDiscipline`
- **Not to be confused with:** `composition:Layer` (a rendered template; PROD-001's `enforcement_layers` key uses the word for an enforcement area, not a template)
- **Stored in:** `docs/products/PROD-001.yaml` (the `substrate` key of each `enforcement_layers` entry)
- **See:** design 01 §What Boilerplate is

**enforced substrate** · `trust:EnforcedSubstrate`\
The `enforced` value of **substrate**: coerce-at-touch-points within Boilerplate's own runtime — schema/parse validation, path-safety (TOCTOU) re-validation, consent/task gating, and lock/checksum verification. Boilerplate rejects on violation with a `BP_*` code; there is no opt-out.

- **Kind of:** `trust:Substrate`
- **Related:** `trust:TrustLevel`, `trust:FirstPartyGatingScaffolding`, `composition:LockFile`
- **Defined in:** `src/boilerplate/common/exceptions.py` (`BP_*` codes), `src/boilerplate/models/boilerplate_lock.py` (lock `schema_version` validation), `src/boilerplate/repository/template_checksum.py` (computes the checksum the lock records)
- **See:** `docs/products/PROD-001.yaml` `enforcement_layers.product`

**preconfigured substrate** · `trust:PreconfiguredSubstrate`\
The `preconfigured` value of **substrate**: Boilerplate ships the defaults, and user-runnable **first-party gating scaffolding** executes the check in third-party tools' native venues (CI runners, hook runners); the user MAY opt out.

- **Kind of:** `trust:Substrate`
- **Related:** `trust:FirstPartyGatingScaffolding`, `model:Guardrails`, `trust:PostRenderValidation`
- **See:** `docs/products/PROD-001.yaml` `enforcement_layers.templates` and `enforcement_layers.tool_configurations`

**first-party gating scaffolding** · `trust:FirstPartyGatingScaffolding`\
The CI pipelines, lint configs, and bundled **EnvironmentProfile** files shipped beside templates as user-runnable parts of the **preconfigured substrate**. The user opts in; gates execute in third-party tools' native venues (CI runners, hook runners).

- **Part of:** `trust:PreconfiguredSubstrate`
- **Related:** `core:FirstPartyTemplates`, `model:Guardrails`, `trust:EnforcedSubstrate`, `provisioning:EnvironmentProfile`
- **See:** `docs/products/PROD-001.yaml` `shipped_gating_scaffolding`

**post-render validation** · `trust:PostRenderValidation`\
Out-of-scope content verdicts performed against generated projects after Boilerplate hands off (detecting drift between shipped defaults and user-edited config). Not enforced; structurally outside Boilerplate's reach.

- **Related:** `trust:Substrate`, `model:Guardrails`
- **See:** `docs/products/PROD-001.yaml` `enforcement_layers.tool_configurations`; `docs/intentions/INT-006.yaml` (`not_included`)

**PEP discipline** · `trust:PEPDiscipline`\
The convention that when a **PEP** defines the canonical way, first-party templates use it — no custom conventions that duplicate or contradict a PEP.

- **Related:** `core:PEP`, `core:FirstPartyTemplates`, `trust:Substrate`
- **See:** design 01 §Standards compliance in first-party templates; `docs/products/PROD-001.yaml` `enforcement_layers.templates`

**Trust Level** · `trust:TrustLevel`\
Binary classification for a template's origin: *trusted* or *untrusted*. Untrusted code is default-deny and requires explicit consent.

- **Related:** `trust:TOFU`, `core:FirstPartyTemplates`, `customization:Task`, `composition:LockFile`
- **Stored in:** the `trust_level` field of each source entry in `boilerplate-sources.yml` in the user's data directory (the implicit first-party source is `trusted`); each lock layer's optional free-form `trust_tier` is a separate field, reserved for richer tiers
- **Defined in:** `src/boilerplate/models/lock_layer.py` (the `trust_tier` field)
- **See:** design 03 §Trust and Verification Levels; design 09 §Catalog Source Configuration File

**TOFU** · `trust:TOFU`\
Trust-on-first-use — a security model where the first interaction with a remote source is trusted, and subsequent interactions are verified against the initial state.

- **Related:** `trust:TrustLevel`, `composition:LockFile`
- **Stored in:** `boilerplate.lock` (the commit hash and checksum captured after the first fetch); the optional pin `expected_commit` on a source entry in `boilerplate-sources.yml`
- **See:** design 03 §Git Source; design 02 §CatalogSource (`expected_commit`)
