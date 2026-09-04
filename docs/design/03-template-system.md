# Template System and Discovery

## Purpose

This document specifies the structure of Boilerplate templates, the `boilerplate.yml` metadata schema, how Copier is configured, how templates are discovered, classified, ranked, and presented to the user, and how the catalog is built from one or more federated sources. Templates are structured so Copier can render them natively; `boilerplate.yml` adds only what Copier doesn't provide — composition, versioning, and dependency metadata. Catalog discovery extends "orchestrate, don't replace" to the template ecosystem — Boilerplate federates sources without owning them.

See [02-data-models.md](02-data-models.md) for entity definitions (TemplateMeta, TemplateInfo, TemplateCatalog, CatalogEntry, etc.).

---

## Template Directory Layout

A Boilerplate-compatible template is a directory on the filesystem with the following required structure:

```text
{template-name}/
├── boilerplate.yml          # REQUIRED — Boilerplate metadata
├── copier.yml               # REQUIRED — Copier questionnaire and tasks
└── {template content}/      # Files rendered into the destination project
```

Additional files and directories are permitted. Copier renders files according to its own conventions (e.g., Jinja2 templating, exclusion rules).

### Path Safety

Boilerplate MUST verify, after staging, that all rendered file paths are contained within the staging root. Absolute output paths and `..` components that resolve outside the staging root MUST be rejected with a clear error. Symlinks in rendered output that point outside the staging directory MUST be rejected with a clear error. Templates containing absolute output paths MUST be rejected at validate time.

**Symlinks in template source directories**: Template source directories MAY contain symlinks. During per-layer rendering (see [04-composition-engine.md](04-composition-engine.md)), symlinks within a template's tree MUST be resolved (copied as regular files) rather than preserved when the source is materialized for Copier. This ensures consistent output across platforms regardless of symlink support. Symlinks pointing outside the template directory MUST be rejected during `boilerplate validate`.

### Required files

| File | Owner | Purpose |
|------|-------|---------|
| `boilerplate.yml` | Boilerplate | Declares name, version, description, and parent templates |
| `copier.yml` | Copier | Declares questions (variables), tasks, exclusions, and other Copier directives |

Both files MUST exist. A directory containing only one of the two is not a valid Boilerplate template (though a directory with only `copier.yml` MAY be classified as a Copier-only template for catalog purposes; see [Template Classification](#template-classification)).

### YAML Parsing Rules

Both `boilerplate.yml` and `copier.yml` MUST be parsed as YAML 1.2 using the Core Schema (see [YAML 1.2 specification](https://yaml.org/spec/1.2.2/)). The following constraints apply to Boilerplate-owned files (`boilerplate.yml` and `boilerplate.lock`); `copier.yml` parsing is delegated to Copier:

- **Character encoding**: UTF-8 only
- **Anchors and aliases**: Permitted, but implementations MUST limit total alias expansion to prevent entity expansion attacks (e.g., "billion laughs"). A maximum of 1,000 resolved alias nodes is RECOMMENDED. If expansion exceeds the implementation's limit, parsing MUST fail with a clear error.
- **Custom YAML tags** (e.g., `!!python/object`): MUST NOT appear; if encountered, parsing MUST fail with a clear error
- **Duplicate keys**: MUST be treated as an error; if two keys at the same mapping level are identical, parsing MUST fail
- **Schema validation**: Load the full document first, then validate against the schema; do not validate field-by-field during parsing
- **Unrecognized fields**: MUST be silently ignored (forward-compatibility)

---

## `boilerplate.yml` Schema

The complete field reference for `boilerplate.yml` is defined in [02-data-models.md §TemplateMeta](02-data-models.md#templatemeta). This section covers authoring guidance and behavioral details for template authors.

### `extends` syntax

Each entry in `extends` is a template reference (`name` or `name@version`). See [02-data-models.md §TemplateSpecifier](02-data-models.md#templatespecifier) for syntax and resolution rules.

> **Version Ranges**: The current `extends` syntax supports exact version pins (`name@1.0.0`) and unversioned references (`name`). Version range specifiers (e.g., `name@>=1.0,<2.0`) are reserved for a future release.

Order matters: in the `extends` list, later-declared entries take file precedence over earlier entries when conflicts occur. The composition execution order is determined by topological sort of the dependency graph; within the sort, declaration order in `extends` determines edge priority and therefore file precedence when diamond dependencies exist. See [04-composition-engine.md](04-composition-engine.md) for the full precedence rules.

### `post_create_message`

When `post_create_message` is present and non-empty, the CLI MUST print each line to the user's terminal after a successful project creation. Lines are printed in order, separated by newlines. Lines MAY contain Jinja2 variable references. Boilerplate MUST render these through Copier's Jinja2 environment using the same variable context available during template rendering. Values from secret questions (`secret: true` in `copier.yml`) MUST be excluded from the rendering context for `post_create_message` to prevent accidental secret leakage in terminal output or logs.

### `requires_profile`

When `requires_profile` is non-null, it MUST be an object with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Profile identifier (e.g., `"python-dev"`, `"node"`) |
| `version` | string | No | PEP 440 version constraint against the **profile's own version** (e.g., `">=1.2"`, `"~=2.0"`). Validates against published profile versions in the catalog. |

**Tool-version requirements come from the profile's lineage, not from the template.** Profiles declare tool version constraints in their own `tools` map; profile authors bump the profile version when those constraints change (the profile version is the contract). A template that needs Python ≥ 3.12 requires a profile *version* whose tool map satisfies that — not a per-template tool override. This keeps the profile as the single source of truth for tool versions and prevents the same profile from producing different effective constraints depending on which template invokes it.

When the required profile is not present in the project's environment state (no `.boilerplate/environment.yml`, or its `profile_name` does not match) or its `profile_version` does not satisfy the `version` constraint, the outcome depends on whether the command mutates the project:

- **Mutating commands** (`boilerplate new`, `boilerplate update`, `boilerplate adopt`) MUST fail closed with `BP_RESOLVE_PROFILE_MISSING` and exit code `3` (`VALIDATION_ERROR`). The error message MUST name the required profile, the failing constraint, and the actual environment state (or its absence).
- **Read-only / inspection commands** (`compose`, `graph`, `validate`, `--render-to`, `test`) MUST emit a WARNING naming the same details but MUST NOT fail on this basis alone, so authors can inspect a template before its profile is provisioned.

This keeps the profile contract a hard precondition exactly where it affects on-disk state, while letting inspection remain usable on a not-yet-provisioned environment.

### Schema Evolution

Boilerplate MUST support all `boilerplate.yml` schema versions within the 1.x series. Any valid 1.x document — whether `"1"`, `"1.1"`, or a future `"1.9"` — MUST be loadable by any Boilerplate implementation that supports schema version 1. New 1.x versions MAY add optional fields but MUST NOT remove or change the semantics of existing fields. Unrecognized fields MUST be silently ignored, ensuring that a template authored against a newer 1.x schema still loads on an older Boilerplate version (forward-compatibility).

When Boilerplate encounters a `schema_version` with an unknown major version (e.g., `"2"`), it MUST reject the document with a clear error message indicating that the schema version is not supported and suggesting the user upgrade Boilerplate. This prevents silent misinterpretation of a fundamentally incompatible schema. Implementations MUST NOT attempt to partially parse or guess the semantics of an unknown major version.

### Example `boilerplate.yml` files

**A base template (no parent):**
```yaml
schema_version: "1"
name: project
version: "2.1.0"
description: A suitable base for any Python project.
post_create_message:
  - "Run 'cd {{ project_slug }}' to enter your project."
  - "Run 'uv sync' to install dependencies."
```

**A derived template (extends project):**
```yaml
schema_version: "1"
name: streamlit
version: "1.0.0"
description: Streamlit data application, extending the base project template.
extends:
  - project@2.1.0
requires_profile:
  name: python-dev
  version: ">=1.2"          # profile-version constraint (profile lineage is the tool-version contract)
```

**A deeply layered template (extends multiple parents):**
```yaml
schema_version: "1"
name: ml-api
version: "3.0.0"
description: ML inference API template.
extends:
  - fastapi@2.0.0
  - ml-base@1.5.0
```

---

## Copier Configuration

The Copier configuration file (`copier.yml`) declares the information that the composition engine and Copier need to render a template. Boilerplate treats this file as Copier-owned; the composition engine merges it across layers using the strategies defined in [04-composition-engine.md](04-composition-engine.md).

### Configuration Concepts

The `copier.yml` file contains four categories of configuration that Boilerplate's composition engine understands:

| Concept | Description | Composition behavior |
|---------|-------------|---------------------|
| **Questions** | User-facing prompts that collect variable values (name, type, default, help text, conditional visibility, constrained choices) | Derived template questions override base template questions of the same key; new questions are appended |
| **Tasks** | Commands executed after rendering (post-generation hooks) | Accumulated from all layers; executed after final rendering |
| **Extensions** | Jinja2 extensions (custom filters) | Union across all layers, deduplicated |
| **Directives** | Copier-specific configuration (minimum Copier version, exclusion patterns, subdirectory settings) | Layer-local by default; specific directives have explicit merge strategies |

### Copier YAML Schema

[Copier](https://copier.readthedocs.io/) uses the following YAML schema in `copier.yml`:

**Questions** — Any key in `copier.yml` not starting with `_` is a user question. Questions are dictionaries with the following fields:

| Sub-field | Purpose |
|-----------|---------|
| `type` | Data type: `str`, `bool`, `int`, `float`, `json`, `yaml` |
| `help` | Prompt text shown to the user |
| `default` | Default value (supports Jinja2 expressions) |
| `when` | Boolean expression; if `false`, the question is skipped |
| `choices` | List of allowed values (optional) |

**Directives** — Underscore-prefixed keys configure Copier's own behavior. Each Copier directive key is assigned a merge strategy. See [04-composition-engine.md §Merge Rules](04-composition-engine.md#merge-rules) for the complete key-to-strategy mapping.

#### Task Execution Safety

Task execution is **default-deny**: tasks never run without explicit operator consent. Before executing any accumulated tasks, Boilerplate MUST display the full list of tasks that will run (template layer name + command) and prompt the user for confirmation unless `--yes` or `--non-interactive` is passed. A `--no-tasks` flag (canonical name) MUST be supported to suppress all task execution without prompting. All executed tasks MUST be logged at INFO level including: task command string, source template layer, execution order index, exit code, and duration. Task stdout and stderr MUST be captured and logged at DEBUG level. This audit trail enables post-incident investigation of what tasks ran and what they produced.

Under the current binary trust model, the consent requirement splits into two rows:

| Template trust | Requirement to run tasks                                       |
|----------------|----------------------------------------------------------------|
| trusted        | User confirmation (or `--yes` / `--non-interactive`)           |
| untrusted      | User confirmation AND `--allow-tasks` (or `--allow-untrusted`) |

If an untrusted template's tasks are not authorized by `--allow-tasks` (or `--allow-untrusted`), those tasks MUST be skipped with a warning listing the skipped commands.

**Security warning**: Template tasks execute shell commands with the invoking user's full privileges. Boilerplate provides no sandboxing or isolation for task execution. Users SHOULD review task commands before confirming.

#### Jinja2 Extension Safety

When any composition layer declares `_jinja_extensions`, Boilerplate MUST display which extensions will be loaded and from which template layer, and prompt the user for confirmation unless `--allow-extensions` (or `--allow-untrusted`) is explicitly passed on the CLI. The `--allow-extensions` flag is required to enable extension loading in non-interactive mode; auto-escalating to `allow_extensions=true` without user consent is not permitted. Extensions MUST be logged at INFO level (extension name, source template) when loaded.

The user consent prompt for Jinja2 extensions MUST be displayed BEFORE any extension module is imported. Extension modules may execute arbitrary code at import time (`__init__` side effects), so consent must precede loading.

Boilerplate MUST reject extension module paths that resolve to standard library modules (`os`, `sys`, `subprocess`, `importlib`, `shutil`, `pathlib`) or any module outside the template's own directory tree and explicitly allowed extension packages.

**Extension allowlist**: Two lists govern whether an extension loads. They serve different purposes and are not interchangeable:

| List | Where declared | Role | Gating? |
|------|----------------|------|---------|
| `allowed_extensions` | Template's `boilerplate.yml` (per-template) | **Declarative**: names what the template intends to load; narrows the consent prompt and surfaces the requirement to the user. | No — does not grant consent and does not relax the package-allowlist check. |
| `allowed_extension_packages` | Global Boilerplate configuration (system-wide) | **Package-level allowlist**: the set of packages whose extensions may be loaded at all. | Yes. |

An extension module loads only when ALL three of the following hold:

1. Its import path is NOT in the standard library blocklist (`os`, `sys`, `subprocess`, `importlib`, `shutil`, `pathlib`, etc.).
2. It resolves to a file within the template's own directory tree, OR its package name appears in the system-wide `allowed_extension_packages` list.
3. The user has consented to extension loading (via `--allow-extensions`, `--allow-untrusted`, or interactive confirmation).

Extensions from packages not on the allowlist MUST be rejected with `BP_RENDER_UNSAFE_EXTENSION` and a remediation message listing the package name and how to add it to the allowlist.

#### Jinja2 Sandbox

Boilerplate MUST use Jinja2's `SandboxedEnvironment` (not the standard `Environment`) for all template rendering. The `SandboxedEnvironment` restricts attribute access on objects, preventing common Server-Side Template Injection (SSTI) techniques such as traversing `__class__.__mro__` or `__subclasses__()` to reach dangerous built-in functions.

The module import blocklist (above) and the `SandboxedEnvironment` are complementary controls: the blocklist prevents loading dangerous modules as Jinja2 extensions at import time; the sandbox prevents template expressions from reaching dangerous functionality at render time via Python's object model.

The **system-wide extension allowlist plus explicit user consent** is the enforced policy boundary for what code may run; `SandboxedEnvironment` is defense-in-depth that hardens execution within that boundary, not a control relied upon as the security boundary itself.

The sandbox MUST also cover `post_create_message` rendering, regardless of whether Copier's own environment is sandboxed. This makes the security guarantee unconditional across every Jinja2 rendering path Boilerplate touches.

### Example `copier.yml`

```yaml
project_name:
  type: str
  help: "Human-readable name of the project (e.g. My Project)"
  default: "{{ _folder_name }}"

project_slug:
  default: "{{ project_name | slugify }}"
  when: false

description:
  type: str
  help: "Brief description of the project."
  default: "A new Python project."

dependencies:
  type: json
  default: []
  help: "Runtime dependencies"

dev_dependencies:
  type: json
  default:
    - pytest
    - ruff
  help: "Development dependencies"

_tasks:
  - ["python", "_scripts/post_generation.py"]
```

**Overriding a question in a derived template:** A derived template's `copier.yml` MAY redeclare any question key. When layers are merged, the derived template's value overrides the base for scalar and dict types (see merge strategy in [04-composition-engine.md](04-composition-engine.md)).

```yaml
# streamlit/copier.yml — overrides the default for 'dependencies'
dependencies:
  default: ["streamlit", "pydantic"]
```

---

## Copier Integration Contract

Boilerplate orchestrates Copier; Copier renders. This section specifies the boundary contract — what each side does, what each side never does, and the invariants that hold across the boundary.

### Ownership boundaries

| Artifact / state | Owner | Mutability | Notes |
|---|---|---|---|
| `.copier-answers.<layer>.yml` (one per layer) | Copier | Mutable (Copier only) | Boilerplate reads; never writes. See [04 §Render Behavior](04-composition-engine.md#render-behavior) for the `_answers_file:` contract. |
| `boilerplate.lock` | Boilerplate | Mutable (regenerated on update) | Full dependency graph + integrity |
| Template submodules | Git | Initialized by Boilerplate before render | MUST exist before YAML parsing |
| Merged `copier.yml` | Boilerplate composition engine | Derived | `!include` directives processed before Copier sees the file |
| Rendered project files | Copier | Written to staging during render | Atomically moved on success |
| `MigrationRecord` entries | Boilerplate | Append-only | Written post-update or post-adopt |

### Preconditions (before invoking Copier)

All of the following MUST hold before Boilerplate invokes Copier for a render or update operation. A precondition violation MUST fail fast with a Boilerplate-attributed error, not an opaque downstream Copier or YAML parse error:

- All template dependencies resolved and locked (`DependencyGraph` built and validated).
- Template artifacts fetched; `git submodule update --init --recursive` completed for every layer referenced as a submodule.
- YAML `!include` paths validated for existence (parse-time check).
- Destination path validated (empty or `--force` explicitly passed).
- Answers payload prepared (initial user-supplied answers for `new`; existing answers + new resolution for `update`).

### Postconditions

**On render success**: each layer's `.copier-answers.<layer>.yml` written by Copier with `_commit` and `_src_path`; `boilerplate.lock` written by Boilerplate after Copier returns successfully; all rendered files present in destination; no conflict markers.

**On render failure**: no partial `.copier-answers.<layer>.yml` files in destination; no partial `boilerplate.lock`; staging directory removed; error raised with attribution `Copier` and phase `render`.

**On update success**: each affected layer's `.copier-answers.<layer>.yml` updated by Copier with new `_commit` (if that layer's version changed); `boilerplate.lock` regenerated; `MigrationRecord` appended (per §06); backup removed.

**On update abort**: backup restored to original project state; no new `MigrationRecord` written.

### Non-responsibilities

Boilerplate explicitly does NOT:

- Mutate any `.copier-answers.<layer>.yml` contents (Copier exclusivity, per the per-layer pattern).
- Execute Jinja2 rendering logic or template-specific tasks (Copier owns rendering; Boilerplate orchestrates task confirmation gates per §Task Execution Safety above).
- Process YAML `!include` directives (the YAML parser handles include resolution before Copier is invoked).
- Implement three-way merge mechanics (delegated fully to Copier on update).

Copier explicitly does NOT:

- Resolve template dependency graphs.
- Generate or validate `boilerplate.lock`.
- Initialize git submodules.

### Boundary invariants

These invariants MUST hold across the Boilerplate ↔ Copier boundary; violation of any is a contract bug, not a feature interaction:

- Every submodule reachable from the root template's `extends` chain MUST be initialized before Copier is invoked.
- Boilerplate MUST never write any layer's `.copier-answers.<layer>.yml`; only Copier does.
- Render MUST leave no partial destination state on failure (staging-then-move, per §07 Atomic Staged Write Pattern).
- `boilerplate.lock` MUST be written only after Copier returns success.
- On `update`, the project backup MUST exist from the start of the operation until terminal status (success or rollback).

Failure attribution for boundary violations follows the [§07 Error Attribution table](07-operational-quality.md#error-attribution): infrastructure failures (missing submodule, invalid YAML include) attribute to `Git` or `YAML`; render conflicts attribute to `Copier`; lock or migration record failures attribute to `Boilerplate`.

### Submodule Federation and Tool Ownership

This subsection explains how a template's `extends` parents are made available on disk before render, and draws the broader ownership lines across the full toolchain (Copier, Boilerplate, uv, the quality tools, and Git). It complements the per-artifact [Ownership boundaries](#ownership-boundaries) table above, which scopes specifically to the Boilerplate ↔ Copier render boundary.

#### Fetching `extends` parents

When a template's `extends` parents live in separate repositories, a template repository MAY reference them as Git submodules (`.gitmodules` maps each parent to a submodule path). Boilerplate initializes those submodules recursively before parsing YAML or invoking Copier, so the full template source is present on disk (the submodule-initialization-before-render rule above). Each parent template owns its own semantic versioning and Git tags; on update, each layer's own `copier update -a .copier-answers.<layer>.yml` reads that layer's per-layer answers file, finds its recorded `_commit`, fetches from the original template repository, and uses the tag as the baseline for that layer's three-way merge ([ADR-015 point 2](adr-015-idiomatic-artifacts.md)) — there is no single shared answers file to read.

> **Reserved for Phase 4 (remote / third-party sources).** A catalog *monorepo that aggregates many independently versioned template repositories* into a single federated source — the broader "submodule federation" organization convention — is deferred. Today, Boilerplate fetches a template and its `extends` parents directly (filesystem, a single `git` source, or `archive`; the deferred `wheel_bundle` seed cache would also apply here once built); the per-template submodule initialization above is the current mechanism and remains in scope.

#### Tool ownership boundaries

The wider toolchain divides responsibilities as follows. Each tool owns a distinct slice of the workflow and explicitly does not own the others':

| Component | Owns | Does NOT own |
|-----------|------|--------------|
| **Copier** | Template input validation, variable interpolation, answers file | Dependency resolution, rendering orchestration |
| **Boilerplate** | Composition orchestration, lock file, atomic rendering, quality gates | Package management, linting, type checking |
| **uv** | Dependency resolution, lock file, Python environment | Template selection, composition logic |
| **ruff/pyright/pytest** | Linting, type checking, testing | Quality gate orchestration |
| **Git** | Version control, artifact storage | Rendering decisions, composition logic |

**Key boundaries**:

- Migrations may transform rendered outputs AFTER composition; outputs ≠ answers.

---

## Template Authoring Lifecycle

This section describes the recommended workflow for creating, testing, and publishing templates.

### Authoring workflow

The typical lifecycle is: scaffold a skeleton (`boilerplate init-template`), add template content and questions, validate (`boilerplate validate`), test locally (`boilerplate new --dry-run`), iterate, and publish to a Git repository or catalog source directory.

#### Validation Surface

`boilerplate validate` verifies template invariants before publication. The authoritative check registry — stable check IDs, severities, and output format — lives in [05 §validate](05-cli-reference.md); IDs are stable once assigned and may be cited in error messages and CI output.

Validation is idempotent and read-only: it MUST NOT modify the template directory or perform any installation work.

#### Template Testing

The `boilerplate test` command provides automated regression testing for templates. See [05-cli-reference.md](05-cli-reference.md) for the full CLI specification (flags, output formats, exit codes). A template test consists of a **fixture**: pre-seeded answers and an expected rendered output snapshot.

**Fixture layout**: Place fixtures in a `tests/` subdirectory within the template:

```text
{template-name}/
├── boilerplate.yml
├── copier.yml
└── tests/
    ├── defaults/               # fixture name
    │   ├── answers.yml         # pre-seeded answers
    │   └── expected/           # expected rendered output tree
    │       ├── pyproject.toml
    │       └── src/
    └── with-extras/            # another fixture
        ├── answers.yml
        └── expected/
```

**Test execution**: `boilerplate test` renders the template to a temp directory using each fixture's `answers.yml`, then diffs the output against `expected/`. Mismatches are reported per-file with unified diffs.

**Snapshot update**: Run `boilerplate test --update-snapshots` to regenerate all `expected/` directories from current render output. Use this to create initial fixtures or update them after intentional template changes.

Template authors SHOULD maintain at least one fixture per template. Fixtures SHOULD cover the common-case answer set and any conditional branches in the template.

### Version Management

Template authors manage versions by editing the `version` field in `boilerplate.yml`. Boilerplate does not auto-increment versions or infer them from external sources.

To bump a version, update the `version` field in `boilerplate.yml`, validate, run snapshot tests, and tag the commit.

**Git tag integration**: For `git` catalog sources, Boilerplate discovers template versions from git tags matching `v{version}` or `{name}@{version}`. The version in `boilerplate.yml` SHOULD match the git tag version. If they disagree, the git tag version takes precedence for catalog discovery, and `boilerplate validate` MUST emit a warning.

For `filesystem` catalog sources, only the `boilerplate.yml` version is used — there is no git tag integration.

**Downstream discovery**: When a template author publishes a new version (by pushing a git tag or updating the filesystem directory), downstream projects discover it via:

- `boilerplate status` — shows "Updates: template 1.0.0 -> 1.1.0 available"
- `boilerplate update --dry-run` — shows the update plan without applying
- `boilerplate list --all-versions` — shows all available versions

**Version deprecation**: To deprecate an old version, set `lifecycle_state: deprecated` and optionally `successor: template-name@2.0.0` in the old version's `boilerplate.yml`. Users who reference the deprecated version will see a warning.

### Composition rules quick reference

| Concept | Behavior |
|---------|----------|
| File overlay | Later layers completely replace earlier layers' files at the same path |
| Question merge | Shallow merge: later layer's top-level keys override; nested dicts replaced wholesale |
| `_exclude`, `_subdirectory` | Layer-local: each layer retains its own Copier directives |
| Task accumulation | Tasks from all layers are collected and executed in dependency order after final render |
| Diamond dependencies | Each template is rendered once. The template appearing latest in the topological render order wins file conflicts. Topological order follows `extends` declaration order (later entries rendered later). Use `boilerplate graph` to verify the render sequence. |

> **Authoring tip**: Use `boilerplate compose <template> --section layers` to inspect per-layer contributions and identify unintentional file collisions before publishing.

#### Shared File Authoring Guide

When multiple layers need to contribute to the same output file (e.g., `pyproject.toml`, `README.md`), use one of these patterns:

**Pattern 1: Single Owner (Recommended)** Designate one layer as the sole owner of the file. Other layers declare their requirements as template questions that the owning layer's template incorporates.

Example: The `project` base template owns `pyproject.toml`. A derived `streamlit` template adds a `streamlit_version` question. The base template's `pyproject.toml.jinja` includes:

```jinja
[project]
dependencies = [
    {% if streamlit_version is defined %}"streamlit>={{ streamlit_version }}",{% endif %}
]
```

**Pattern 2: Post-Render Task** Use a `_tasks` entry to modify the file programmatically after rendering (e.g., `toml` or `json` manipulation scripts).

**Avoid**: Having multiple layers each provide their own copy of the same file. The last layer in topological order silently replaces earlier layers' versions with no merge.

---

## Template Classification

Every template in the catalog MUST be classified into one of two types:

| Classification | Criteria |
|----------------|----------|
| **Boilerplate-enabled** | Contains both `boilerplate.yml` and `copier.yml`; supports composition, versioning, and lock files |
| **Copier-only** | Contains `copier.yml` but no `boilerplate.yml`; can be scaffolded but does not support composition or lock files |

Classification MUST be deterministic and based solely on file presence. A template's classification MUST NOT change without a change to its files.

### Classification Algorithm

At sync time, each template directory or remote entry MUST be classified based on file presence: directories with both `boilerplate.yml` and `copier.yml` are Boilerplate-enabled; directories with only `copier.yml` are Copier-only; all others are skipped. Classification is deterministic: same files produce the same classification across all runs.

### Copier-Only Template Behavior

When `boilerplate new` is invoked with a Copier-only template:

1. The template is rendered using Copier directly (single invocation, no composition)
2. No `boilerplate.lock` is written (no composition metadata to record)
3. No `extends` resolution occurs (Copier-only templates cannot participate in composition)
4. Post-creation guidance is limited to default guidance (`cd {destination}`)
5. The `list` command MUST show Copier-only templates with a `Copier` type indicator, clearly distinguishing them from Boilerplate-enabled templates

This allows Boilerplate to serve as a unified entry point for both composed and simple templates without requiring every template to adopt the full Boilerplate metadata format.

---

## Trust and Verification Levels

Trust is **binary**: a template is either **trusted** or **untrusted**. Trust reflects confidence in a template's origin — whether it came from a source the operator configured as authoritative.

| Level | Description | Who grants |
|-------|-------------|-----------|
| **trusted** | Came from a trusted source — a first-party `git` source (the published per-template repositories, [ADR-006](adr-006-template-distribution.md)), or a `git` source with `trust_level: trusted` explicitly configured | Source configuration |
| **untrusted** | Default for any source not configured as trusted, including local filesystem and `archive` templates | Implicit |

The binary model is the current enforcement surface. The richer multi-tier taxonomy (Official / Verified / Community / Local) is **reserved for Phase 4 (remote / third-party sources)**. The lock's `trust_tier` field is an OPTIONAL free-form string field so Phase 4 can reintroduce richer tiers without a schema change; its absence MUST NOT fail resolution (see the lock provenance and integrity rule in [10-security.md](10-security.md)). Source URL and commit-or-checksum remain mandatory regardless of trust.

**Invariants**:

- A template's trust is inherited from its source: a template is trusted only when its source is trusted (a first-party published-repo `git` source, or any `git` source configured as trusted).
- Local filesystem and `archive` templates are untrusted by default.

### Trust ceiling per source type

Under binary trust, first-party `git` sources — the published per-template repositories ([ADR-006](adr-006-template-distribution.md)) — are trusted by default; any other `git` source MAY be configured as trusted; `filesystem` and `archive` sources are untrusted. The deferred `wheel_bundle` source type would be trusted when built.

| Source type                                                 | Maximum trust        |
| ----------------------------------------------------------- | -------------------- |
| `git` (first-party, published per-template repository)      | trusted              |
| `git` (third-party, with `trust_level: trusted` configured) | trusted              |
| `git` (third-party, default)                                | untrusted            |
| `filesystem`                                                | untrusted            |
| `archive`                                                   | untrusted            |
| `wheel_bundle` (deferred seed cache)                        | trusted (when built) |

These ceilings are enforced during catalog registration. A source configured with `trust_level: trusted` on a `filesystem` or `archive` type is rejected at validation time. The CLI only reads trust values; it cannot modify them.

### Emergency Revocation

> **Reserved for Phase 4 (remote / third-party sources).** An out-of-band revocation mechanism — a system-wide revoked-templates list (`revoked_templates_path`), its read protocol, the `BP_RESOLVE_TEMPLATE_REVOKED` rejection, and the matching `status` / `update` / `lock verify` / `new --force` behaviors — is deferred until Boilerplate consumes remote third-party sources. For first-party and operator-configured sources, incident response is handled by removing or replacing the offending source and re-resolving; there is no separate revocation list. The concept is retained here so Phase 4 can reintroduce it without redesigning the trust model.

### Content Verification

The trust model verifies template *origin* (which source provided it) but not template *content* (tamper detection between publication and use). The `expected_commit` field on `CatalogSource` plus per-layer `commit` and `checksum` fields in `boilerplate.lock` provide a post-creation integrity chain; pre-use signature verification is not yet supported.

`boilerplate lock verify` SHOULD be included as a CI gate step to detect template content drift between catalog refreshes. See §07 Operational Quality for the CI/CD Quick Reference.

### Filesystem Source Defaults

When templates are discovered from filesystem sources (the `DirectoryTemplateRepository`), `CatalogEntry` fields that are only available from remote registries receive the following defaults:

| Field | Default | Rationale |
|-------|---------|-----------|
| `trust_level` | `untrusted` | Filesystem templates have no external trust attestation |
| `lifecycle_state` | `published` (when absent from `boilerplate.yml`) | See note below |
| `tags` | `[]` | No tagging metadata available from filesystem |
| `category` | `""` | No category metadata available from filesystem |
| `last_updated` | Filesystem mtime of `boilerplate.yml` | Best available proxy for modification time |
| `successor` | `null` | No deprecation metadata available from filesystem |

The `DirectoryTemplateRepository` MUST respect the `lifecycle_state` declared in `boilerplate.yml`. The default value of `published` is applied only when the field is absent from the file, not when it is present with any value. Templates with `lifecycle_state: draft` are excluded from `boilerplate list` output by default but remain renderable via direct path reference (`boilerplate new ./path/to/template`).

These defaults ensure that filesystem templates appear in `list` output and participate in ranking without requiring registry metadata. The `list` command SHOULD suppress empty columns (e.g., `Tags`) when all results have default values.

### .copier-answers.&lt;layer&gt;.yml Integrity

Boilerplate MUST record the SHA-256 hex digest of each layer's `.copier-answers.<layer>.yml` file contents in the `copier_answers_file_hashes` mapping of `boilerplate.lock` (key = template name, value = digest). This per-layer mapping captures the literal answers-file contents and is the sole answers-integrity mechanism that `lock verify` uses. Each first-party template's `copier.yml` declares its own answers file via Copier's `_answers_file:` directive (see [04-composition-engine.md §Render Behavior](04-composition-engine.md#render-behavior)). Boilerplate MUST NOT write or mutate any `.copier-answers.<layer>.yml`; those files are read-only from Boilerplate's perspective and are written exclusively by Copier. On update, if any layer's hash does not match, Boilerplate MUST warn the user that answer state for that layer may have been externally modified.

When `--save-answers` is used, questions marked with `secret: true` are excluded from saved answer files. A placeholder comment is included to indicate the omission (see [§10 Privacy](10-security.md#privacy) for details).

---

## Lifecycle States

| State | Description | Visible by default |
|-------|-------------|-------------------|
| **draft** | Not yet published; under development | No |
| **published** | Stable and recommended for use | Yes |
| **deprecated** | Still works but superseded; users are warned | Yes (with warning indicator) |
| **archived** | No longer maintained; not suitable for new use | No (requires `--include-archived`) |

**Deprecation successor**: When a template enters the `deprecated` state, it SHOULD declare a `successor` field in its catalog metadata — a template reference (e.g., `"new-template@2.0.0"` or `"new-template"`) pointing to the recommended replacement. When the CLI displays a deprecated template (in `list` or during `new`), it MUST include the successor reference in the warning if one is declared:

```text
!  template 'old-api' is deprecated. Use 'new-api@2.0.0' instead.
```

**Deprecation triggers**. A template version SHOULD enter the `deprecated` state when ANY of:

- A security vulnerability cannot be fixed via PATCH release.
- A breaking semantic change is required for future capabilities.
- The version has been superseded by a major release with improved architecture or contracts.
- Integrity or provenance concerns surface that warrant warning users away from the version.

**Removal policy** (deprecated → archived):

- A version SHOULD remain `deprecated` long enough for downstream projects to migrate before it is marked `archived`; the template author chooses the interval. Critical security issues MAY transition `deprecated` → `archived` immediately, and the catalog entry MUST document the rationale at the same time.

Lifecycle state is advisory: deprecated templates warn but remain usable, and archived templates are hidden by default. (Hard out-of-band blocking via revocation is reserved for Phase 4; see [§Emergency Revocation](#emergency-revocation).)

---

## Template Discovery and Catalog Sources

The catalog is federated: it is built from one or more **catalog sources**. Each source has a type, location, and priority.

### Supported Source Types

| Type | Description |
| ---- | ----------- |
| `filesystem` | Local directory |
| `git` | Git repository, local or remote (see [Git Source](#git-source)) |
| `archive` | Compressed archive (.zip, .tar.gz); enables offline and air-gapped distribution (see [Archive Source](#archive-source)) |
| `wheel_bundle` | Git bundle (`.bundle`) packaged inside a Python wheel; first-party-only; carries Git history (see [Wheel Bundle Source](#wheel-bundle-source)) |

The source type enum is extensible. Additional types (e.g., `http`, `github`, `oci`) are specified when built. Implementations encountering an unknown source type SHOULD log a warning and skip the source gracefully.

### CatalogSource

See [02-data-models.md](02-data-models.md) for the full `CatalogSource` schema. Key fields: `name`, `type`, `location`, `priority`, `trust_level`, `expected_commit` (optional — when set, the initial Git clone is validated against this commit hash; see [TOFU warning](#git-source)). Authentication is delegated to Git's credential helper system (see [§Authentication](#authentication)); a per-source `credentials` field is reserved for Phase 4 (remote / third-party sources).

Priority determines conflict resolution: lower number = higher priority. If two sources share the same `priority` value, the one registered first (earlier in the configuration list) takes precedence.

### CatalogEntry

See [02-data-models.md](02-data-models.md) for the full `CatalogEntry` schema. A `CatalogEntry` is the catalog's record for one template from one source, including classification, trust level, lifecycle state, and dependency information.

### Discovery Algorithm (DirectoryTemplateRepository)

The `DirectoryTemplateRepository` scans each configured directory for immediate subdirectories containing both `boilerplate.yml` and `copier.yml`. Each valid candidate is parsed into a `TemplateInfo` record. Candidates are processed in lexicographic order by absolute path for determinism. Invalid candidates (unparseable metadata, invalid specifiers) are skipped with a warning.

Per template name, the highest PEP 440 version wins. If two directories provide identical `name@version`, the first encountered (lexicographically earlier path) wins. The `TemplateCatalog` enforces first-wins deduplication across multiple repositories.

**Important limitation**: The `DirectoryTemplateRepository` keeps only one version per name when scanning unversioned subdirectories. Teams managing multiple template versions on the filesystem SHOULD use versioned subdirectories (see below).

### Versioned Subdirectory Convention

A directory source MAY provide multiple versions of the same template using the versioned subdirectory naming convention: a subdirectory named `{name}@{version}` (e.g., `base@1.0.0/`) is treated as a specific version of template `{name}`. The name portion must be alphanumeric with hyphens and underscores; the version must be valid PEP 440. When versioned subdirectories are present, all discovered versions are registered in the catalog (not just the highest).

This allows pinned `extends` references (e.g., `extends: [base@1.0.0]`) to resolve correctly within a filesystem source. The catalog's first-wins deduplication still applies for identical `name@version` pairs across multiple sources.

**Resolution determinism**: A Resolver instance caches resolved templates by specifier string. A specifier that has been resolved once always returns the same `TemplateInfo` for the lifetime of that Resolver instance. All transitive references to the same `name@version` resolve to the same object within a single resolution run.

### Template Directory Resolution Order

When building the catalog, directories are searched in this order:

1. `--templates-dir` (CLI override, if provided — highest priority)
2. `default_templates_dir` (the user's default template directory)
3. Each path in `extra_template_dirs` in declaration order
4. First-party templates (the published per-template git repositories, per [ADR-006](adr-006-template-distribution.md); implicit source, lowest priority — org-local clones or mirrors of those repositories, or the deferred wheel-bundled seed cache (see [Wheel Bundle Source](#wheel-bundle-source)), serve as the offline path)

The first template registered for a given canonical tag wins. User-provided templates via `--templates-dir` or `extra_template_dirs` can shadow built-in templates of the same name and version.

### Catalog Build Process

The catalog is built by iterating directories in resolution order (see above), loading templates from each via `DirectoryTemplateRepository`, and registering them in the catalog. First-wins deduplication ensures that higher-priority sources shadow lower-priority ones for the same `name@version`.

---

## Environment Profile Discovery

Environment profile discovery follows the same directory scan pattern as template discovery (see [Discovery Algorithm](#discovery-algorithm-directorytemplaterepository) above). Where template discovery looks for `boilerplate.yml`, profile discovery looks for `boilerplate-env.yml`:

- A directory containing `boilerplate-env.yml` is a **profile source**. The `DirectoryProfileRepository` scans configured directories for immediate subdirectories containing `boilerplate-env.yml`, parses each into an `EnvironmentProfile` record (see [02-data-models.md](02-data-models.md) for the `ProfileCatalog` schema), and registers them in the `ProfileCatalog`.
- **Registration policy**: The same first-wins deduplication policy applies. Per profile name, the first registered entry wins across repositories. Within a single directory source, the highest-versioned record is kept (identical to template behavior).
- **Versioned subdirectories**: The `{name}@{version}/` naming convention is supported for profiles, enabling multiple profile versions to coexist in a single directory source.
- **Search order**: Profile directories are searched in the same order as template directories: `--templates-dir` (CLI override) → `default_templates_dir` → `extra_template_dirs` → bundled profiles.
- **Validation**: Each discovered `boilerplate-env.yml` MUST be parsed and validated. Invalid files are skipped with a warning log.

See [02-data-models.md](02-data-models.md) for `ProfileCatalog` operations and [08-environment-provisioning.md](08-environment-provisioning.md) for profile resolution and activation.

---

## Git Source

Templates MAY be sourced from any Git repository — remote or local. Git treats local paths and remote URLs identically (`git clone` works with both), so a single `git` source type covers all Git-based template distribution.

### Fetch Behavior

Boilerplate clones the repository at a specific version tag using a shallow clone (depth 1). If no tag is specified, the default branch is cloned and the latest version tag is used. After clone, the local directory is treated as a standard filesystem source for discovery.

For local paths, `boilerplate doctor` MUST verify the path is a valid git repository and warn if it is not.

**Trust-on-first-use (TOFU) warning**: The first clone of a remote template source trusts whatever the Git server returns. No out-of-band verification of repository content occurs on initial fetch. After the first successful fetch, the lock file captures the commit hash and content checksum, providing integrity verification for subsequent operations. To mitigate TOFU risk:

- Prefer HTTPS URLs over SSH for auditability
- Use `expected_commit` in `CatalogSource` configuration to pin the initial fetch to a known-good commit
- Review template content after first fetch before running `--allow-untrusted` operations

### Supported URL Formats

| Format | Example |
|--------|---------|
| HTTPS | `https://github.com/user/repo.git` |
| SSH | `git@github.com:user/repo.git` |
| Local path | `/home/user/my-template-repo` |
| Shorthand (`gh:`) | `gh:user/repo` (expanded to GitHub HTTPS) |
| Shorthand (`gl:`) | `gl:user/repo` (expanded to GitLab HTTPS) |
| Shorthand (`ado:`) | `ado:org/project/repo` (expanded to Azure DevOps HTTPS) |

Implementations MUST support HTTPS, SSH, and local paths. Shorthands are expanded to HTTPS before cloning. Additional shorthands MAY be added in future versions.

### Authentication

Boilerplate delegates all credential handling to Git's credential helper system. See [10-security.md §Credential Handling](10-security.md#credential-handling) for credential safety requirements.

If authentication fails, the CLI MUST report the failure with remediation guidance and the error code `BP_GIT_AUTH_FAILED`.

### Version Tag Convention

Version tags MUST follow one of these patterns:

- `v<version>` — e.g., `v1.2.0` (single-template repositories)
- `<template-name>@<version>` — e.g., `project@2.1.0` (multi-template repositories)

Version discovery enumerates tags matching these patterns, parses them as PEP 440 versions, and selects the best match for the requested constraint.

---

## Archive Source

Templates MAY be distributed as compressed archives. The `archive` source type extracts a `.zip`, `.tar.gz`, or `.tgz` archive and treats the extracted contents as a filesystem source.

### Use cases

- Air-gapped environments where neither network access nor local git repos are available
- Simple distribution: share a set of templates as a single file without requiring a git server
- Checksum-verified snapshots: a checksum-protected archive provides tamper-evident template distribution

### Archive structure

The archive MUST contain template directories as immediate children of the archive root:

```text
my-catalog.zip
├── project/
│   ├── boilerplate.yml
│   └── copier.yml
├── streamlit/
│   ├── boilerplate.yml
│   └── copier.yml
└── boilerplate-archive.yml   # optional manifest
```

An optional `boilerplate-archive.yml` manifest at the root MAY declare:

- `name`: archive display name
- `version`: archive version
- `created_at`: ISO 8601 creation timestamp
- `template_checksums`: map of template name → SHA-256 checksum of template directory contents

### Extraction and caching

Archives are extracted to `{user_data_dir}/boilerplate/archives/{source-name}/` on first use. Re-extraction occurs when the archive checksum changes or `--refresh` is passed. HTTPS archive downloads use the same Git credential helper mechanism as remote git sources.

### Checksum verification

If `checksum` is configured in the archive source, it MUST be validated against the archive file before extraction. Mismatch raises `BP_BUNDLE_CHECKSUM_FAILED`.

### Example configuration

```yaml
sources:
  - name: airgapped-catalog
    type: archive
    location: /mnt/shared/boilerplate-catalog-2026-03-20.zip
    checksum: sha256:abc123...
```

Currently an `archive` source is `untrusted` (only `git` sources may be configured as trusted; see [Trust ceiling per source type](#trust-ceiling-per-source-type)). Its tamper-evidence comes from the `checksum`, not from a trust tier.

---

## Wheel Bundle Source

> **Deferred.** Per [ADR-006](adr-006-template-distribution.md), the canonical first-party channel is the **published per-template git repositories** — ordinary `git` sources with `vX.Y.Z` tags, extracted from the authoring monorepo at release time. The `wheel_bundle` source type below is retained in the taxonomy as a deferred offline seed-cache option, built only on demonstrated demand.

A Git bundle file (`.bundle`) packaged inside the Boilerplate Python wheel as binary asset data — one bundle per first-party template, carrying that template's full extracted Git history and tags. Distinct from the `archive` source type (which extracts compressed archives without Git history). If built: the build pipeline produces per-template bundles from the extracted repos, the wheel ships them as package data, and first use clones each to a per-user cache directory (`{user_data_dir}/boilerplate/cache/templates/<bundle-version>/`) that Copier sees as a normal local Git repository (no `_subdirectory:` — each bundle is a single template at its root). The cache is invalidated when the installed Boilerplate version changes, since the bundles ship with the wheel. The cache is a seed, not a source of record: Copier records the source it actually used, and per [ADR-015](adr-015-idiomatic-artifacts.md) Boilerplate MUST NOT rewrite an answers file to mask that — so a cache-seeded layer's answers file records the cache path itself, which is machine-local and does not resolve on another machine. Rehoming to the published repository is a deliberate one-line `_src_path` edit the user makes; the seed cache trades portability for offline capability, and that is the honest trade. `LockLayer.source_bundle` records the bundle's wheel-relative path for cache invalidation and audit.

**Trust**: `trusted` — first-party templates shipped inside the Boilerplate wheel. (The richer multi-tier taxonomy is reserved for Phase 4; see [Trust and Verification Levels](#trust-and-verification-levels).)

**Distinct from**:

- `archive` — `.zip`/`.tar.gz`/`.tgz` extraction; no Git history; not Copier-`update`-friendly for multi-layer projects.
- `git` — remote Git URL; requires network on first use; the canonical first-party channel.
- `filesystem` — local directory; may or may not have `.git/`.

---

## Local Catalog Cache

Remote sources are cached locally so that discovery operations do not require network access on every invocation.

**Invariants**:

- Discovery MUST default to cached data. Remote sync MUST require explicit `--refresh`.
- Stale caches (older than 24 hours) SHOULD warn the user but MUST NOT block operations.
- Sync operations MUST be idempotent and safe to retry.
- Cache storage format is implementation-defined (YAML, JSON, or SQLite are all acceptable).
- Cached template artifacts MUST match their recorded checksum. A cached artifact whose recomputed checksum does not match its lock-file checksum MUST be treated as missing (re-fetched on next access); stale or corrupt cache entries MUST NOT be reused silently.

The cache directory (`{user_data_dir}/boilerplate/`) is a security-sensitive location. On POSIX systems, implementations MUST set directory permissions to `0700` (owner-only access). On Windows, implementations SHOULD restrict access to the current user via ACLs. Cache poisoning by other users or processes could lead to execution of malicious template content.

For local sources (`filesystem` and local `git` paths), discovery re-scans the source directory on each invocation; the scan is cheap at the catalog sizes targeted, so no separate mtime-based index is maintained.

---

## First-Party Templates

Boilerplate ships with first-party templates. These serve as the authoritative reference for what valid templates look like.

### First-Run Experience

On a fresh installation, `boilerplate list` MUST display first-party templates with a clear header (e.g., "First-party templates"). When no remote sources are configured, the output MUST include guidance: "Configure additional template sources in `boilerplate-sources.yml` or use `--templates-dir` to add template directories." When `boilerplate new` is invoked without a template argument and no template can be resolved, the CLI MUST list the available first-party templates and the same guidance rather than presenting an empty list with a diagnostic dead-end.

### `project` template

A base template for any Python project. Collects standard project metadata (name, description, author, dependencies) and runs a post-generation script. See the template's `copier.yml` for the full question set.

### `streamlit` template

A Streamlit data application template that **extends** `project`. Overrides dependency defaults to include Streamlit-specific packages. All other questions are inherited from `project` via composition — at compose time only; a per-layer `copier update` sees only the layer's own `copier.yml`, so a layer must redeclare any inherited question its files reference ([ADR-015](adr-015-idiomatic-artifacts.md)). See the template's `copier.yml` for details.

---

## Commands

### `boilerplate list`

The `list` command is the primary interface for template discovery. Its full specification — arguments, options, output formats, ranking, and behavior — is in [05-cli-reference.md](05-cli-reference.md).

This section documents the result-ordering and template classification logic that the `list` command depends on.

---

## Result Ordering

List and search results MUST use a plain deterministic ordering: **source priority (lower `priority` number first), then `name`, then `version` (descending)**. The same catalog state always produces the same order; there is no weighted relevance score. Trust state MUST NOT participate in result ordering; it is a displayed and filterable property only.

**Query filtering**: When a query string is provided, it acts as a case-insensitive substring *filter* — a template is included when the query is a substring of its `name`, `description`, or any `tags` entry. Filtering decides inclusion only; it does not reorder results. The deterministic ordering above still applies to the filtered set.

**Duplicate resolution**: When two sources provide the same template name and version, the entry from the higher-priority source (lower `priority` number) is shown. The duplicate is suppressed.

---

## Selection and Handoff to Project Creation

When the user selects a template (via `boilerplate new`), the discovery system resolves the template reference to a `TemplateSpecifier` (see [02-data-models.md](02-data-models.md)) and passes it to the project creation workflow (see [06-project-lifecycle.md](06-project-lifecycle.md)). If the user specified a version constraint rather than an exact version, the catalog resolves it to the highest matching version before constructing the specifier.

---

## Template Authoring Constraints

An implementation MUST enforce the following when loading templates:

1. `boilerplate.yml` MUST be present. If absent, the directory is not a valid Boilerplate template.
2. `copier.yml` MUST be present. If absent, the directory is not a valid Boilerplate template.
3. `name` in `boilerplate.yml` MUST contain only alphanumeric characters, hyphens, and underscores.
4. `version` MUST be a valid PEP 440 version.
5. `extends` is a list. The list MAY be empty (`[]`). If non-empty, each entry MUST be a non-empty string. Existence of referenced templates is validated at resolution time, not at load time.
6. Circular dependencies (`A → B → A`) MUST be detected during resolution and reported as `DependencyCycleError`. They are not validated at load time.
7. First-party (official) templates MUST include a `.gitattributes` file with `* text=auto` to normalize line endings across platforms. Third-party templates SHOULD include this file. Without line ending normalization, the same template checked out on Windows (CRLF) and Linux (LF) will produce different checksums, breaking cross-platform reproducibility.
8. The `validate` command SHOULD report file path collisions when validating a template with `extends` dependencies: files that exist in multiple layers, noting which layer's version will take precedence. This is a warning, not an error — file overlay is by design, but unintentional collisions are a common authoring mistake.

---

## Constraints and Invariants

1. Classification MUST be based solely on file presence, not content.
2. Archived templates MUST be excluded from default results.
3. Duplicate templates (same name+version from multiple sources) MUST resolve to the highest-priority source.
4. Source priority MUST be configured explicitly; no implicit ordering.
5. Search results MUST be stable for the same query, filters, and catalog state.
