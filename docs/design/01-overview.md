# Boilerplate: Product Overview

## What Boilerplate solves

Python projects accumulate friction at four points:

- **Environment drift** — tools, versions, and configurations diverge across machines and contributors.
- **Configuration sprawl** — every new project re-discovers and re-wires linter, formatter, type-checker, and test-runner settings.
- **Onboarding friction** — new contributors spend hours on setup before their first commit.
- **Inconsistent toolchains** — no team-level authority decides which tools and versions win.

These problems compound at organizational scale, where dozens of repositories each accumulate their own configuration debt.

## What Boilerplate is

A curated scaffolder paired with a managed development environment. Lock files keep both reproducible.

> **Start fast. Stay consistent. Reproduce anywhere.**

Boilerplate has two surfaces:

- **Managed development environment** — preconfigured `uv`, `ruff`, `pyright`, `pytest`, and VS Code workspace settings, installed and version-pinned via `boilerplate env apply`.
- **CLI and template system** — `boilerplate new` scaffolds a project from a curated template; `boilerplate update` applies upstream template changes to existing projects safely; `boilerplate list` and `boilerplate compose` make the catalog navigable.

**The slot model.** A development environment decomposes into recurring roles — **slots** — catalogued in [The Development Environment Landscape](dev-environment-landscape.md). Boilerplate fills the inner-loop slots with one opinionated, preconfigured tool each; its templates then fill slots *within* those slots, pre-wiring each tool's per-project configuration (rule sets, strictness, markers, workspace settings). Slots Boilerplate does not opine on are out of scope by design — "should Boilerplate also do X?" is answered by whether X is an inner-loop slot.

Principle enforcement spans two substrates: Boilerplate's runtime *enforces* its own invariants, and the artifacts it ships *preconfigure* principles as machine-checkable defaults. Per-layer assignments are specified in PROD-001 `enforcement_layers`; shipped vs planned gating content lives in PROD-001 `shipped_gating_scaffolding`.

**Python-native with an extensible template system.** The reference implementation is written in Python and first-party templates target Python projects, but the template system, composition engine, and CLI impose no language requirements on template content. Teams may author templates for any language or framework. PEP 440 is the default versioning standard; SemVer-compatible versions (e.g., `1.2.3`) are valid PEP 440 and work without modification.

### When to use Copier directly

Boilerplate orchestrates Copier — it does not replace it. For some use cases, Copier alone is the right choice:

| Use case | Recommended tool |
|----------|-----------------|
| Single template, no composition | Copier |
| Single-template projects — `copier update` covers their updates | Copier |
| Layered templates with `extends` chains | Boilerplate |
| Reproducible project creation with lock files | Boilerplate |
| Multi-layer template updates with three-way merge | Boilerplate |
| CI/CD drift detection (`lock verify`) | Boilerplate |
| Environment provisioning (`env apply`) | Boilerplate |

Existing Copier templates work with `boilerplate new` without modification — Boilerplate adds a `boilerplate.yml` metadata file alongside `copier.yml` but does not modify or replace it. The `boilerplate.lock` file is informational; if you stop using Boilerplate, your projects and their Copier answers files are untouched.

## Core Principles

These principles are non-negotiable. Every implementation decision MUST honor them.

### Reproducibility is mandatory

Every created or managed project MUST be reproducible across machines and time. Lock files, pinned tool versions, and deterministic configuration are required at every stage. Changes that reduce determinism MUST be rejected.

> **Scope**: Reproducibility is guaranteed at the *project* level via lock files — a locked project can be reconstructed identically. At the *template declaration* level, unversioned `extends` references (e.g., `extends: [project]`) resolve to the latest available version at resolution time, which may differ across invocations. The lock file captures the exact resolution, ensuring reproducibility from the point of creation forward.

### Templates and environments are both first-class surfaces

The template system is the primary surface; the managed development environment is a real, deliberately thin companion surface. A change to one MUST keep the other aligned: a new CLI behavior that affects scaffolding MUST be reflected in template guidance; a new toolchain capability MUST be reflected in environment profiles; documentation MUST update alongside both.

> *In practice:* `boilerplate new` and `boilerplate env apply` are independent operations, not phases of one workflow. Templates declare what gets rendered; profiles declare what tools render and run it. The first-party `project` template ships with both a `boilerplate.yml` (template surface) and a corresponding `boilerplate-env.yml` (environment surface).

### Safety-first operations

Operations that modify or remove existing managed state (`update`, `env apply`, `eject`) MUST preview the planned changes and require explicit user confirmation before applying. Operations that create or advance managed state MUST record provenance: project operations write a `MigrationRecord`, and `env apply` writes the `EnvironmentProvisionRecord`. `eject` removes that managed state and records nothing; recovery is to re-`adopt`.

**Forward-looking (no current referent):** Bulk operations MUST require confirmation.

> *In practice:* `boilerplate update` and `boilerplate env apply` display a plan and prompt for confirmation before applying changes. `boilerplate new` writes directly because creating a project into a new directory is not destructive. Provenance is recorded across two domains: `MigrationRecord` entries in `.boilerplate/migrations.yml` cover project-domain operations (create / update / adopt), and the `EnvironmentProvisionRecord` in `.boilerplate/environment.yml` records the last applied environment state (`env apply`).

### Atomic Staged Write Pattern and lock ownership

Template rendering MUST follow the [Atomic Staged Write Pattern](07-operational-quality.md#atomic-staged-write-pattern): render to a staging area, validate, then commit with no partial state left behind. On failure, the staging area MUST be cleaned up and the destination MUST remain untouched. The `boilerplate.lock` file is owned by Boilerplate and MUST be written only after a successful commit.

> **Platform caveat**: Windows directory rename is not atomic; Boilerplate provides best-effort crash recovery (see [06-project-lifecycle.md](06-project-lifecycle.md)).

### Environment lifecycle is managed

Boilerplate manages the toolchain across its full lifecycle — installation, version verification, updates, and cleanup — not just initial scaffolding. Environment setup operations MUST be idempotent (safe to re-run) and fail-fast (halt with diagnostic on error before partial work persists). Tools MUST be verified to exist and meet declared version requirements before any operation that depends on them proceeds.

> *In practice:* `boilerplate env apply` re-runs deterministically — applying the same profile twice produces the same `.protolock` state. Tool-version checks happen before invocation, not lazily during; missing or mismatched tools fail with `BP_ENV_*` codes and remediation guidance, not with downstream subprocess errors.

### Orchestrate tools, do not replace them

Boilerplate MUST orchestrate established external tools (Copier, package managers, version checkers) instead of reimplementing their responsibilities. Ownership boundaries between Boilerplate and integrated tools MUST be explicit in every operation.

### Versioning and compatibility

The Boilerplate tool itself follows Semantic Versioning 2.0.0. Breaking changes MUST be accompanied by a major version bump and documented migration path. Templates use PEP 440 — a SemVer-compatible superset that PEP 440 itself endorses for the `MAJOR.MINOR.PATCH` (clauses 1-8) public-version part. Templates carry versions in this scheme and declare their compatibility constraints.

> *In practice:* PEP 440 is the wire format (see §02 Version). Plain `X.Y.Z` versions are valid in both grammars and order identically; PEP 440 adds Python-ecosystem-specific syntax for pre-release (`1.0a1`), post-release (`1.0.post1`), dev (`1.0.dev1`), and epoch (`1!2.0`) identifiers — those identifiers MUST be expressed in PEP 440 form (not SemVer's `1.0.0-alpha.1` / `1.0.0+abc` forms) because the two grammars order incompatibly outside the X.Y.Z subset. Lock files record exact resolved versions so updates are explicit, never silent.

### PEP compliance in first-party templates

First-party (official) templates MUST conform to the relevant Python Enhancement Proposals for every pattern they implement. This includes but is not limited to: PEP 440 (versioning), PEP 508 (dependency specifiers), PEP 517/518 (build system), PEP 621 (project metadata in `pyproject.toml`), PEP 660 (editable installs), and PEP 723 (inline script metadata). When a PEP defines the canonical way to do something, the template MUST use it — no custom conventions that duplicate or contradict a PEP. Third-party templates are not bound by this requirement, though they are encouraged to follow it.

### Trust-gated catalog federation

Templates are sourced from a federated catalog. Trust is binary — a source is either *trusted* or *untrusted* — and behavioral, not cosmetic: it gates what a template MAY do (execute tasks, load Jinja2 extensions, install plugins), default-deny for untrusted code. Untrusted code requires explicit per-operation consent. The full model — the trusted/untrusted boundary, default-deny task gating, and consent gates — is specified in [03-template-system.md §Trust and Verification Levels](03-template-system.md#trust-and-verification-levels).

### Security and privacy defaults

- No secrets in code, configuration, or logs. Use environment variables or a vault.
- Validate and sanitize all external inputs at trust boundaries.
- Redact personal data in logs.
- Fail closed: errors MUST not leak sensitive internal details to the user.

See [10-security.md](10-security.md) for the full security specification.

---

## Platform Portability

Boilerplate supports Windows, macOS, and Linux. See [07-operational-quality.md §Platform Portability](07-operational-quality.md#platform-portability) for platform-specific rules and constraints.

---

> **Precedence policies**: Boilerplate uses two distinct precedence rules in different contexts. *Catalog registration* uses first-wins: the first source to register a template name+version owns it — see [02-data-models.md §TemplateCatalog](02-data-models.md#templatecatalog). *Composition merging* uses last-wins: later layers override earlier layers' values — see [04-composition-engine.md §Merge Rules](04-composition-engine.md#merge-rules).

Persisted artifacts (data models, the lock schema, merge and checksum semantics) are specified most carefully because they outlive any single implementation.

## System Boundaries and External Dependencies

This table covers cross-system boundaries — which tool owns which concern across Boilerplate's external integrations. For per-domain state-file inventories, see [06 §Project State Files](06-project-lifecycle.md#project-state-files) (project domain) and [08 §State Files](08-environment-provisioning.md#state-files) (environment domain).

| Concern | Owner | Notes |
|---------|-------|-------|
| Template file rendering | Copier | Boilerplate orchestrates; Copier renders. See [04-composition-engine.md](04-composition-engine.md). |
| Answer collection | Copier | Interactive or defaults mode |
| Copier answers files (per-layer `.copier-answers.<layer>.yml`; singular `.copier-answers.yml` for legacy projects) | Copier | Boilerplate MUST NOT write or mutate these files |
| `boilerplate.lock` | Boilerplate | Written after successful render commit |
| Git submodule initialization | Boilerplate | Initialized recursively before Copier invocation |
| Package / dependency resolution | External package manager | Out of scope for the core tool |
| Environment toolchain management | proto | Boilerplate orchestrates; proto installs tools. See [ADR-001](adr-001-build-vs-adopt.md). |
| `.prototools` | proto | proto's native toolchain declaration; Boilerplate generates from merged profiles |
| `.protolock` | proto | proto's native lock file recording exact tool versions and checksums; enabled by Boilerplate |
| `.boilerplate/environment.yml` | Boilerplate | Records which profile was applied and the resolved `extends` chain |
| Git initialization | Git | Boilerplate MAY invoke; does not own |

---

## Feature Slices

The product is organized into five vertical slices, each independently deliverable.

| Slice | Name | Acceptance Criteria | CLI Commands | Design Docs |
| ----- | ---- | ------------------- | ------------ | ----------- |
| 001 | Template Discovery | `list`, `graph`, `validate` return correct results for first-party and filesystem templates | `list`, `graph`, `validate`, `test`, `cache warm` | [03](03-template-system.md), [05](05-cli-reference.md) |
| 002 | Project Creation | `new` renders multi-layer compositions atomically with lock file generation | `new`, `compose`, `init-template` | [02](02-data-models.md), [03](03-template-system.md), [04](04-composition-engine.md), [05](05-cli-reference.md), [06](06-project-lifecycle.md) |
| 003 | Project Update & Adoption | `update` performs three-way merge; `adopt` imports Copier-only projects; `eject` stops Boilerplate management (inverse of `adopt`) | `update`, `adopt`, `eject`, `status`, `lock verify` | [05](05-cli-reference.md), [06](06-project-lifecycle.md) |
| 004 | Environment Profiles | `env apply` provisions tools via proto and records the applied state; re-running `env apply` is the recovery path | `env apply`, `env status` | [08](08-environment-provisioning.md) |
| 005 | Operational Quality | `doctor` validates system health; structured logging and error codes operational | `doctor` | [07](07-operational-quality.md) |
| — | Developer Experience | — | — | [05](05-cli-reference.md) |

See [Implementation Status](../status.md).

### Environment Profiles

Declarative profiles (`boilerplate-env.yml`) pin the development toolchain per project and compose via `extends`. Boilerplate resolves the chain and writes `.prototools` (proto's native input); proto installs tools and writes `.protolock` (exact versions + checksums). Boilerplate writes `.boilerplate/environment.yml` for profile provenance. Same "orchestrate, don't replace" pattern as Copier — see [ADR-001](adr-001-build-vs-adopt.md). Operational contract: [§08 Environment Provisioning](08-environment-provisioning.md).

---

## High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                                CLI                                   │
│  Project:  new | update | status | adopt | eject                     │
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

---

## Runtime Configuration (Settings)

The runtime is configured by a `Settings` object loaded from environment variables and an optional `.env` file. See [09-settings-and-configuration.md](09-settings-and-configuration.md) for the complete Settings specification, including all fields, env var names, types, and defaults, and for the `boilerplate-sources.yml` configuration file.

---

## Glossary

Core terms used throughout this document suite. For data model details see [02-data-models.md](02-data-models.md); for composition details see [04-composition-engine.md](04-composition-engine.md).

| Term | Definition |
|------|-----------|
| **Answer Preset** | A YAML file supplying answers to template questions declaratively for CI/CD. Passed via `--answers`. |
| **Answers File** | Records answers given during render. Owned by Copier; Boilerplate MUST NOT write to it. See [04-composition-engine.md §Render Behavior](04-composition-engine.md#render-behavior) for the per-layer `_answers_file:` contract. |
| **Atomic Staged Write Pattern** | Boilerplate's stage-then-rename file-emission discipline: stage in an isolated directory, validate, then atomically move into place. Canonical definition in [07-operational-quality.md §Atomic Staged Write Pattern](07-operational-quality.md#atomic-staged-write-pattern). |
| **`.boilerplate/environment.yml`** | On-disk filesystem path holding the `EnvironmentProvisionRecord`. Use this name when discussing the file. |
| **boilerplate.yml** | Boilerplate-specific metadata file inside a template directory. Declares name, version, and dependencies. See [02-data-models.md §TemplateMeta](02-data-models.md#templatemeta). |
| **Configuration** | The settings that wire a **Development Environment**'s toolchain — `pyproject.toml` and `.vscode/`. A part of the Development Environment; see the [Development Environment](../environment/index.md) guide. Distinct from Boilerplate's own runtime configuration (the `Settings` object — see [§Runtime Configuration](#runtime-configuration-settings)). |
| **`.copier-answers.<layer>.yml`** | The per-layer answers file Copier writes; `<layer>` is the layer's invariant name (matches `LockLayer.name`). One file per composition layer. |
| **Copier** | The external tool ([Copier](https://copier.readthedocs.io/)) responsible for file rendering, answer collection, and task execution. Boilerplate orchestrates Copier without replacing it. |
| **copier.yml** | Copier questionnaire file. Declares questions (variables) and tasks. Owned by Copier; Boilerplate reads but MUST NOT write to it. |
| **DAG / Dependency Graph** | Directed Acyclic Graph of template specifiers, derived from `extends` chains. |
| **Development Environment** | The setup a developer works in — its **Toolchain**, its **Configuration** (`pyproject.toml`, `.vscode/`), **Project Layout**, **Workflow**, and **Guardrails**. What a generated project ships with (INT-001). Distinct from **Environment Provisioning**, the subsystem that installs and pins it. |
| **enforced substrate** | The `enforced` value of **substrate**: coerce-at-touch-points within Boilerplate's own runtime — schema/parse validation, path-safety (TOCTOU) re-validation, consent/task gating, and lock/checksum verification. Boilerplate rejects on violation with a `BP_*` code; there is no opt-out. |
| **Environment** | The problem domain — a developer's setup and its tendency to diverge across machines and time ("environment drift"). Umbrella over **Development Environment** (the thing) and **Environment Provisioning** (the subsystem); in prose, avoid the bare word where one specific sense is meant. |
| **Environment Provisioning** | The subsystem that installs and version-pins a **Development Environment** — the `env apply` flow, providers, and the `EnvironmentProfile`. Target design (INT-004; see [§08](08-environment-provisioning.md)). Supersedes the informal label "Environment(s) Pillar." |
| **EnvironmentProfile** | `boilerplate-env.yml` — the declarative input to **Environment Provisioning** (tool versions + configuration). Not **Profile** (`profile.toml`, a user's default answers to template questions — see [ADR-010](adr-010-profile.md)); the two are unrelated despite the shared word. |
| **`EnvironmentProvisionRecord`** | The schema for the env-state record. Use this name when discussing structure (the file on disk is `.boilerplate/environment.yml`). |
| **extends-based composition** | The static `extends:` mechanism in template metadata that drives composition. Not a runtime feature; resolved at composition time. |
| **first-party gating scaffolding** | The CI pipelines, lint configs, and profile assets shipped beside templates as user-runnable parts of the **preconfigured** substrate. User opts in; gates execute in third-party tools' native venues (CI runners, hook runners). |
| **first-party templates** | Templates Boilerplate publishes as their own git repositories, extracted from the authoring monorepo at release time — the canonical first-party distribution channel (vs user-provided or third-party); see [ADR-006](adr-006-template-distribution.md). |
| **gating scaffolding** | See **first-party gating scaffolding**. |
| **Guardrails** | Where quality is enforced across a **Development Environment** — dev-time (format-on-save, live type-checking) and CI. A part of the Development Environment; see the [Development Environment](../environment/index.md) guide. |
| **layer** | One rendered template in a composition graph; the composition unit. Each layer has its own answers file. |
| **Lock File (`boilerplate.lock`)** | Records exact versions, commit hashes, and checksums used. Owned by Boilerplate. |
| **Managed project** | A project Boilerplate tracks and can update: it has a `boilerplate.lock`. Contrast **Unmanaged project**. `adopt` transitions an unmanaged project to managed. |
| **Non-git layer** | A composition layer whose template source has no git history (a plain filesystem directory or an archive). Records `commit: null` in the lock; `update` skips it with a warning — Copier has no built-in fallback merge for it — and `copier recopy` is the manual refresh. See [06-project-lifecycle.md](06-project-lifecycle.md). |
| **PEP** | Python Enhancement Proposal — the standards process for the Python language. Referenced PEPs: 440 (versioning), 508 (dependency specifiers), 517/518 (build system), 621 (project metadata), 660 (editable installs), 723 (inline script metadata). |
| **PEP discipline** | The convention that when a PEP defines the canonical way, first-party templates use it — no custom conventions that duplicate or contradict a PEP. |
| **plural-shape architecture** | Authoring shape that admits future siblings (e.g., `ci-azure-pipelines` today, `ci-github-actions` later) by extending the answer-value enum, not by introducing a breaking schema change. |
| **post-render validation** | Out-of-scope content verdicts performed against generated projects after Boilerplate hands off (detecting drift between shipped defaults and user-edited config). Not enforced; structurally outside Boilerplate's reach. |
| **Project Layout** | The standard project structure — `src/`, `tests/`, and their conventions. A part of the **Development Environment**; see the [Development Environment](../environment/index.md) guide. |
| **RenderEngine** | The proper-noun class that orchestrates Copier across composition layers. |
| **safe update** | The conflict-detected, atomically-rolled-back update workflow Boilerplate provides over Copier's per-layer merge. See [04 §Safe Update](04-composition-engine.md#safe-update) for the implementation. |
| **slot** | One recurring role in a development environment (linter, type checker, test runner, …), per [The Development Environment Landscape](dev-environment-landscape.md). Boilerplate fills the inner-loop slots with one opinionated tool each; templates fill slots *within* those slots (each tool's per-project configuration). |
| **substrate** | A layer's enforcement mode — `enforced` (Boilerplate's own runtime gates and rejects on violation, with no opt-out) or `preconfigured` (defaults are shipped; user-runnable gating scaffolding executes the check in third-party venues; the user MAY opt out). Per-layer assignments live in PROD-001 `enforcement_layers`. |
| **Template** | A directory containing `boilerplate.yml` and `copier.yml` that can be scaffolded into a project. Its filesystem location is the **template root**. |
| **Template Specifier** | A `name@version` string uniquely identifying a template. A **Template Reference** is the input form (`name` or `name@version`); a specifier is the resolved form. |
| **TOFU** | Trust-on-first-use — a security model where the first interaction with a remote source is trusted, and subsequent interactions are verified against the initial state. |
| **Toolchain** | The tool *set* within a **Development Environment**: uv, ruff, pyright, pytest, VS Code, git. A part of the environment, **not** a synonym for it. |
| **Trust Level** | Binary classification for a template's origin: *trusted* or *untrusted*. Untrusted code is default-deny and requires explicit consent. The lock's optional `trust_tier` field is a free-form string field reserved for future richer tiers. See [03-template-system.md](03-template-system.md). |
| **Unmanaged project** | A project with Copier answers file(s) (`.copier-answers.*`) but no `boilerplate.lock` — e.g. a plain `copier copy` project, or one after `eject`. Contrast **Managed project**. `adopt` transitions it to managed. |
| **schema v1** | The first generation of this design suite's on-disk contracts (`schema_version` major `1`, e.g. `"1"` / `"boilerplate/lock@1"`). Independent of the tool's release version (SemVer `0.x` until the first stable `1.0`), which tracks implementation maturity, not contract generation. |
| **WASM** | WebAssembly — the plugin architecture used by proto for cross-platform tool installation. |
| **Workflow** | The everyday developer loop within a **Development Environment** — sync → edit → check → test → commit. A part of the Development Environment; see the [Development Environment](../environment/index.md) guide. |
