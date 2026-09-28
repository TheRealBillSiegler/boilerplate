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

Core terms used throughout this document suite. For data model details see [02-data-models.md](02-data-models.md); for composition details see [04-composition-engine.md](04-composition-engine.md). Canonical definitions live in `CONTEXT.md` at the repository root; this section pulls them in unchanged.

--8<-- "CONTEXT.md:language"
