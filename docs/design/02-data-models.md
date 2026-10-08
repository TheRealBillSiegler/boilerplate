# Data Models

## Purpose

This document defines every domain entity in the Boilerplate system: its fields, types, validation rules, and relationships.

All models are **immutable** once constructed unless otherwise noted. Validation MUST fail fast: reject invalid input at construction time, not lazily during use.

See [01-overview.md](01-overview.md) for the glossary.

---

## Primitive Types

### Version

A PEP 440-compliant version string. All versions in this system MUST conform to PEP 440 (see [PEP 440](https://peps.python.org/pep-0440/) for the full grammar and ordering rules).

**Non-Python implementations**: PEP 440 endorses SemVer clauses 1–8 — every plain `X.Y.Z` is valid in both grammars and orders identically. Implementations targeting non-Python ecosystems MAY use SemVer **only on the X.Y.Z release subset**. Pre-releases, build metadata, and post-releases MUST use PEP 440 syntax (`1.0a1`, `1.0.post1`, `1.0.dev1`, `1!2.0`), not SemVer (`1.0.0-alpha.1`, `1.0.0+abc`) — the orderings disagree (SemVer's lexicographic pre-release order conflicts with PEP 440's `aN < bN < rcN`). Lock file `version` fields MUST serialize as PEP 440 strings.

- Examples: `"1.0.0"`, `"2.0.0b1"`, `"0.0.1.post1"`, `"1.2"`, `"0.1.dev3"`
- Comparison: standard PEP 440 ordering (pre-releases sort before releases)
- Serialization: always a string
- Validation: MUST reject strings that are not valid PEP 440 versions

**Key ordering rules** (summary for implementers):
- Canonical form: `N[.N]+[{a|b|rc}N][.postN][.devN]`; `1.0` and `1.0.0` are equal
- Epoch: `E!N.N` sorts above all non-epoch versions
- Pre-release order: `aN < bN < rcN < release`
- Post-release: `1.0 < 1.0.post1`
- Dev release: `1.0.dev1 < 1.0a1 < 1.0`
- When comparing, normalize by treating missing numeric segments as `0` (e.g., `1.0` == `1.0.0`)

### JSON

The `JSON` type represents any value that can appear in a JSON or YAML document:

```text
JSON = string | integer | float | boolean | null | map[string, JSON] | list[JSON]
```

All fields of type `map[string, JSON]` MUST be serializable to both YAML and JSON without loss.

### TemplateSpecifier

A compound identifier uniquely addressing one version of one template.

| Field | Type | Constraints |
|-------|------|-------------|
| `name` | string | Alphanumeric characters, hyphens, and underscores only |
| `version` | Version | MUST be a valid PEP 440 version |

**String form**: `{name}@{version}` (e.g., `project@2.1.0`, `streamlit@1.0.0b2`)

**Parsing**: Split on the first `@` — left side is `name`, right side is `version`. Both MUST pass their respective validation.

**Ordering**: Compare by `name` lexicographically first; if equal, compare `version` by PEP 440 ordering.

**Equality**: Two specifiers are equal iff `name` and `version` are both equal.

**Errors**:
- `InvalidTemplateSpecifierError` — name fails pattern or string is not in `name@version` form
- `InvalidVersionError` — version is not PEP 440 compliant

---

## Template Domain Models

### TemplateMeta

The contents of a template's `boilerplate.yml` file. Represents Boilerplate-specific metadata about one template.

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `schema_version` | string | No | `"1"` | Schema major version. MUST have major version `1` (i.e., `"1"`, `"1.1"`, etc. are all valid within the 1.x series). See §03 Schema Evolution for forward-compatibility rules. Boilerplate MUST reject templates with an unrecognized major version and SHOULD silently ignore unknown fields within a recognized version. |
| `name` | string | Yes | — | Non-empty; identifies the template logically |
| `description` | string | No | `""` | Human-readable summary |
| `version` | Version | Yes | — | Semantic version of this template |
| `extends` | list of string | No | `[]` | Ordered list of parent template references |
| `post_create_message` | list of string | No | `[]` | Lines printed after successful project creation; MAY contain Jinja2 variable references. When a composition spans multiple layers, `post_create_message` from ALL layers in the dependency chain MUST be accumulated and displayed in topological order (base templates first, root template last). Each layer's message is displayed with a header identifying the template source. |
| `lifecycle_state` | string | No | `"published"` | Template lifecycle state. One of: `draft`, `published`, `deprecated`, `archived`. |
| `successor` | string or null | No | `null` | Template name to recommend when this template is deprecated. |
| `requires_profile` | object or null | No | `null` | Environment profile required by this template; see [requires_profile semantics](#requires_profile-semantics). |
| `checksum_excludes` | list of string | No | `[]` | Path prefixes to exclude from rendered output checksum computation, in addition to the built-in exclusions (`.git/`, `__pycache__/`, `.boilerplate/`). Template authors MAY use this to exclude generated artifacts (e.g., `.venv/`, `node_modules/`). |
| `allowed_extensions` | list of string | No | `[]` | Per-template Jinja2 extension allowlist; declarative and narrowing, never consent. See [allowed_extensions semantics](#allowed_extensions-semantics). |

Each entry in `extends` is a template reference in the form `name` or `name@version`. Unversioned references resolve to the latest available version at resolution time.

**Serialization format** (YAML):
```yaml
schema_version: "1"
name: project
description: Standard Python project template
version: "2.1.0"
extends:
  - base@1.0.0
  - standards
```

**Validation rules**:
- `name` MUST be non-empty
- `version` MUST be a valid PEP 440 version
- `schema_version` MUST be a recognized major version string
- `extends` entries MUST be non-empty strings; they are not validated for existence at parse time

**Load behavior**: Given a path, if the path is a directory, load `{path}/boilerplate.yml`. If it is a file, load that file directly. Raise `FileNotFoundError` if the file does not exist.

#### `requires_profile` semantics

When non-null, `requires_profile` MUST be an object with two fields:

- `name` (string, required) — the profile's logical name.
- `version` (string, optional) — a PEP 440 version constraint against the **profile's own version**, used to require a specific profile lineage.

The constraint targets the profile version, not the underlying tool versions. Tool-version requirements are expressed via the profile's own version lineage: profile authors bump the profile version when tool constraints change. Templates do not override individual tools.

See [03-template-system.md](03-template-system.md) for the full sub-field specification.

#### `allowed_extensions` semantics

`allowed_extensions` lists the import paths of Jinja2 extensions a template intends to load. The list is **declarative and narrowing**, not a consent grant: it scopes the consent prompt to exactly the listed extensions (rather than to anything the system-wide allowlist permits) and surfaces the requirement to the user before installation.

Consent is still required. An extension loads only when both conditions hold:

1. Its package appears in the system-wide `allowed_extension_packages` setting, AND
2. The user has consented via `--allow-extensions`, `--allow-untrusted`, or interactive confirmation per §03 Jinja2 Extension Safety.

Per-template `allowed_extensions` does NOT waive the user-consent requirement — template-author metadata cannot grant consent on the user's behalf. See [03-template-system.md](03-template-system.md) for the full Jinja2 extension safety model.

---

### TemplateInfo

A resolved template: metadata paired with its filesystem location.

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Template's logical name |
| `meta` | TemplateMeta | Parsed `boilerplate.yml` |
| `location` | path | Absolute filesystem path to the template root |
| `scaffolding_template` | opaque handle | An opaque reference passed to the render engine. Its internal structure is implementation-defined. Boilerplate treats it as a value object — it MUST NOT modify it after construction. |

**Computed**:
- `specifier` → derived from `name` and `meta.version`

---

## Composition Domain Models

### Resolution

The output of the Resolver. An immutable snapshot of the dependency traversal result.

| Field | Type | Notes |
|-------|------|-------|
| `deps` | DependencyMap | Maps each specifier string to its direct dependency specifier strings |
| `templates` | map of string → TemplateInfo | Maps specifier string to the resolved TemplateInfo |

**DependencyMap** is a map where:
- Key: canonical specifier string (e.g., `"project@2.1.0"`)
- Value: ordered list of direct dependency specifier strings

**Computed**:
- `execution_sequence` → topologically sorted specifier strings, dependencies first

**Invariant**: Every specifier referenced as a dependency MUST also appear as a key in `deps`. The Resolver guarantees this.

---

### CompositionGraph

The dependency graph artifact within a `CompositionArtifact`.

| Field | Type | Notes |
|-------|------|-------|
| `nodes` | map of string → GraphNode | All nodes keyed by specifier string |
| `edges` | map of string → list[string] | Adjacency list (specifier → its dependency specifiers), each list in declaration order, deduplicated |
| `sequence` | list[string] | Deterministic topological render sequence (dependencies first) |

**GraphNode**:

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Template name |
| `version` | string | Template version string |
| `path` | path | Filesystem path to template root |

**Operations**:
- `sequence_payload()` → map — structured representation for serialization

---

### CompositionLayer

A *layer* is a template participating in a composition. Each layer contributes files and configuration; the composition engine merges them in topological order.

One template's contribution to a composition.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | Yes | Template name |
| `version` | string | Yes | Template version string |
| `path` | path | Yes | Filesystem path to template root |
| `values` | map[string, JSON] | Yes | Question values contributed by this layer |
| `state_after` | map[string, JSON] or null | No | Cumulative merged state after this layer is applied (null if not tracked) |
| `delta` | map[string, JSON] or null | No | Keys added or changed by this layer vs previous state (null if not tracked) |

**Computed views**:
- `state` → `state_after` if present, else empty
- `delta_view` → `delta` if present, else empty

---

### CompositionArtifact

The complete, immutable artifact produced by the Composer. Contains everything needed to render a project.

| Field | Type | Notes |
|-------|------|-------|
| `graph` | CompositionGraph | The dependency graph (carries the topological `sequence`) |
| `layers` | list[CompositionLayer] | One entry per template, in execution order |
| `final` | map[string, JSON] | Fully merged Copier configuration (questions + directives) |
| `schema_version` | string | `"1"` — schema major version |

**Computed properties**:
- `merged_questions_schema` → `final` with all internal keys (prefixed `_`) removed — the canonical user questionnaire
- `stats` → `CompositionStats` (see below)
- `requires_unsafe` → `true` if `final` contains Jinja2 extensions requiring Copier's `unsafe=true` mode

---

### CompositionStats

Aggregate metrics derived from a `CompositionArtifact`. Used by the `compose --stats` command for debugging and introspection.

**Required fields** (all implementations MUST include):

| Field | Type | Description |
|-------|------|-------------|
| `layers_count` | integer | Number of template layers in the composition |
| `question_count` | integer | Number of user-facing questions in the merged questionnaire |
| `task_count` | integer | Number of tasks in the merged `_tasks` list |
| `template_names` | list[string] | Template names in execution order |

Additional fields are permitted and encouraged but not required.

---

## Catalog and Repository Models

### TemplateCatalog

An in-memory index of all available templates. Not a persistent store.

**Lookup strategy**: templates are indexed by two keys:
1. Canonical tag: `"{name}@{version}"` — for exact-version lookup
2. Name + version map: for latest-version resolution

**Registration policy**: "first one wins" — if two templates share the same canonical tag, the first registered is kept and subsequent duplicates are ignored; a DEBUG-level log message MUST be emitted recording the duplicate tag and the skipped source path.

**Operations**:

| Method | Input | Output | Notes |
|--------|-------|--------|-------|
| `register(template)` | TemplateInfo | void | First-wins deduplication |
| `register_many(templates)` | list[TemplateInfo] | void | Calls `register` for each |
| `get_by_tag(tag)` | string | TemplateInfo or null | Exact tag lookup |
| `resolve(name, version?)` | name + optional version | TemplateInfo or null | Null version returns the entry with the highest version by PEP 440 ordering (same as `resolve_latest`) |
| `resolve_latest(name)` | name | TemplateInfo or null | Returns the entry with the highest version by PEP 440 ordering; first-registered wins if versions compare equal |
| `list_all()` | — | list[TemplateInfo] | All registered templates |
| `list_tags()` | — | list[string] | All canonical tags |
| `len()` | — | integer | Count of registered templates |

---

### TemplateRepository (interface)

An abstract source of templates. Implementations discover and load templates from a specific origin (local directory, remote index, etc.) and return `TemplateInfo` records.

Required operation:
- `load_templates()` → `list[TemplateInfo]`

The repository does not register templates; the caller is responsible for populating a catalog.

---

### DirectoryTemplateRepository

A `TemplateRepository` implementation that scans local filesystem directories.

**Discovery algorithm**:
1. Given a list of directories, scan each directory for subdirectories containing both `boilerplate.yml` and `copier.yml`.
2. For each valid template directory: parse `boilerplate.yml` → `TemplateMeta`, construct a `TemplateInfo`.
3. Skip directories that fail validation (log a warning, continue).
4. Per template name, keep only the highest-versioned template found (PEP 440 ordering). If two directories provide the same template at the same version, the template from the lexicographically earlier directory path wins (first-encountered). Multiple versions of the same template in a single directory are not simultaneously available from one repository instance; only the highest is kept.

**Validation**: A template directory is valid iff:
- It contains `boilerplate.yml`
- It contains `copier.yml`
- `boilerplate.yml` parses without error

---

### CatalogEntry

A display and ranking model constructed on demand from a `TemplateInfo` + `CatalogSource` pair. Not stored in the catalog — the catalog stores `TemplateInfo` internally; `CatalogEntry` is computed when the `list` command or ranking algorithm needs source-aware metadata.

| Field | Type | Source |
|-------|------|--------|
| `name` | string | `TemplateInfo.name` |
| `version` | Version | `TemplateInfo.meta.version` |
| `description` | string | `TemplateInfo.meta.description` |
| `tags` | list[string] | Registry metadata; `[]` for filesystem sources |
| `category` | string | Registry metadata; `""` for filesystem sources |
| `source` | string | `CatalogSource.name` |
| `source_priority` | integer | `CatalogSource.priority` |
| `classification` | enum | `boilerplate-enabled` or `copier-only` (determined by file presence) |
| `trust_level` | enum | `CatalogSource.trust_level`; binary `trusted`/`untrusted`. Local filesystem sources are `untrusted` by default; first-party `git` sources — the published per-template repositories ([ADR-006](adr-006-template-distribution.md)) — are `trusted` by default, as is any other `git` source explicitly configured `trust_level: trusted`. The deferred `wheel_bundle` source type would be `trusted` when built. See [03-template-system.md](03-template-system.md#trust-ceiling-per-source-type). |
| `lifecycle_state` | enum | Registry metadata; `published` for filesystem sources |
| `last_updated` | ISO 8601 datetime | Registry metadata; filesystem mtime for filesystem sources |
| `dependencies` | list[string] | `TemplateInfo.meta.extends` |
| `successor` | string or null | Registry metadata; `null` for filesystem sources |

---

### CatalogSource

A configured origin from which the catalog discovers templates.

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Human-readable source identifier (e.g., `official`, `community`) |
| `type` | enum | Source type (`filesystem`, `git`, `archive`, `wheel_bundle`, `http`, `github`, `oci`). Implementable types: `filesystem`, `git`, and `archive` (`.zip`/`.tar.gz`/`.tgz` extraction; renamed from the legacy `bundle` type). `wheel_bundle` (Git bundle packaged inside the Boilerplate wheel) is deferred as a seed cache pending demonstrated demand ([ADR-006](adr-006-template-distribution.md)). The `http`, `github`, and `oci` types are reserved for future versions. |
| `location` | string | URI or path to the source |
| `credentials` | reference | Reserved for Phase 4 (remote / third-party sources). Credential reference (env var name, vault path, etc.) for authenticated remote sources. Until Phase 4, sources are local and ignore this field. |
| `priority` | integer | Lower number = higher priority; ties broken by registration order |
| `trust_level` | enum | Binary `trusted`/`untrusted` — the trust level this source can grant. Trusted by default for first-party `git` sources — the published per-template repositories ([ADR-006](adr-006-template-distribution.md)) — and for any other `git` source explicitly configured `trust_level: trusted`; `filesystem` and `archive` sources are `untrusted` by default. The deferred `wheel_bundle` type would be trusted when built. See [03-template-system.md](03-template-system.md#trust-ceiling-per-source-type). (The richer tiered model is reserved for Phase 4.) |
| `expected_commit` | string or null | TOFU (trust-on-first-use) pinning for `git` sources: the expected commit hash on first clone. When set, Boilerplate records the commit on first use and rejects later fetches whose tip does not descend from it. Ignored for `filesystem` and `archive` types. See [09-settings-and-configuration.md](09-settings-and-configuration.md#catalog-source-configuration-file). |

---

### ArchiveSource

A catalog source backed by a compressed archive containing template directories. Enables offline distribution and air-gapped environments.

| Field | Type | Required | Default | Description |
| ----- | ---- | -------- | ------- | ----------- |
| `type` | `"archive"` | Yes | — | Source type discriminator |
| `location` | string | Yes | — | Local file path or HTTPS URL to the archive |
| `name` | string | Yes | — | Display name for this source |
| `priority` | integer | No | `100` | Lower = higher priority |
| `trust_level` | enum | No | `untrusted` | Binary `trusted`/`untrusted` trust ceiling. An archive source is `untrusted` by default; its tamper-evidence comes from `checksum`, not from a trust tier. See [03-template-system.md](03-template-system.md#trust-ceiling-per-source-type). |
| `checksum` | string or null | No | `null` | Expected SHA-256 hex digest of the archive; validated before extraction |
| `credentials` | CredentialRef or null | No | `null` | Reserved for Phase 4 (remote / third-party sources). Credential reference for HTTPS downloads. |

Supported formats: `.zip`, `.tar.gz`, `.tgz`. The archive MUST contain template directories as immediate children of the archive root. An optional `boilerplate-archive.yml` manifest at the root MAY declare archive metadata (name, version, created_at). Archives are extracted to `{user_data_dir}/boilerplate/archives/{name}/` on first use; re-extracted when checksum changes or `--refresh` is passed. When present, the manifest's `name` and `version` are used for display in `boilerplate cache` output and diagnostic messages. They do not affect catalog registration or template resolution.

---

## Lock File Model

### BoilerplateLock

The `boilerplate.lock` file written into a project root after a successful creation or update.

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | string | `"boilerplate/lock@1"` — namespaced schema version identifier |
| `boilerplate_version` | string | Version of the Boilerplate tool that wrote the file |
| `copier_version` | string | Version of Copier used for rendering |
| `created_at` | ISO 8601 datetime | UTC timestamp of creation |
| `updated_at` | ISO 8601 datetime | UTC timestamp of last update |
| `root_template` | string | Specifier of the template used to create the project |
| `copier_answers_file_hashes` | map[string, string] or null | Per-layer SHA-256 hex digests, one entry per template layer that has an answers file. Key = template name (matches `LockLayer.name`); value = SHA-256 hex digest of that layer's `.copier-answers.<layer>.yml`. This is the sole answers-integrity mechanism `lock verify` consults for tamper detection on update. Optional; omitted when no answers files exist. |
| `layers` | list[LockLayer] | One entry per template layer, in execution order; at least one layer joined through `extends`, the root |

> **Hash format convention**: Hash fields that are fixed to SHA-256 by definition (`copier_answers_file_hashes` values, `proto_lock_hash`) use bare hex strings. Checksum fields that may support alternative algorithms in the future (`LockLayer.checksum`) use the `algorithm:hex` prefix format (e.g., `"sha256:{hex_digest}"`). This allows future algorithm migration for content checksums without a schema change.

**LockLayer**:

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Template name |
| `version` | string | Exact version used (PEP 440) |
| `joined_via` | enum | How the layer joined the project: `extends` for the root template and every layer its `extends` closure reaches, as `new` and `adopt` write them and as `update` writes a layer the closure newly reaches; `add` for a layer `boilerplate add` introduced. The value is fixed once written: a layer `add` introduced keeps `add` when a later root target reaches it through `extends`, and the `extends` constraint still bounds its version. `update` reads it to tell which layers the root's target governs ([06 §Step 3](06-project-lifecycle.md#step-3-build-updateplan)). |
| `source` | string | URI or filesystem path of the template |
| `commit` | string or null | Git commit hash of the template at render time |
| `checksum` | string | SHA-256 hex digest of the template source directory content (excluding `.git/`, `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `node_modules/`), prefixed with algorithm identifier (e.g., `"sha256:{hex}"`). Files are sorted lexicographically by relative path (forward slashes on all platforms), then path and content are concatenated and hashed. This is the authoritative definition of the checksum exclusion list. The source directory is a git checkout, so comparisons must be stated in git's content sense (line endings normalized), not raw bytes — Copier's git-based checkout rewrites line endings under `core.autocrlf=true` ([ADR-015 §Verification](adr-015-idiomatic-artifacts.md#verification-2026-07-28)). See [06-project-lifecycle.md](06-project-lifecycle.md) for computation details. |
| `subdirectory` | string or null | Deferred, conditional on the `wheel_bundle` seed cache ([ADR-006](adr-006-template-distribution.md)): when built, would hold the value of the layer's `_subdirectory:` Copier directive for a layer sourced from a shared Git bundle. Published per-template repositories carry no `_subdirectory:` — one repository, one template — so `null` for every layer today. |
| `source_bundle` | string or null | Deferred, conditional on the `wheel_bundle` seed cache ([ADR-006](adr-006-template-distribution.md)): when built, would hold the bundle's relative path within the wheel (e.g., `boilerplate/_template_bundles/templates.bundle`), used for cache invalidation and audit. `null` for every layer today — first-party layers render from the published Git repositories, not a wheel-packaged bundle. |
| `trust_tier` | string or null | Optional. The trust level of the layer's source at resolution time, recorded when the source declares one; `null` otherwise. With local sources the recorded value is `null` or `"local"`. Never consulted; reserved for the Phase 4 trust model. |
| `bundle_uri` | string or null | Optional; reserved. The external URI from which the layer's source bundle can be restored (populated by external/enterprise catalog infrastructure for air-gap restoration). `null` until that infrastructure populates it; never consulted. |
| `bundle_checksum` | string or null | Optional; reserved. Expected checksum of the bundle referenced by `bundle_uri`, used to verify a restored bundle (populated by external/enterprise catalog infrastructure for air-gap restoration). `null` until that infrastructure populates it; never consulted. |

**Invariants**:
- A lock file MUST hold at least one `layers` entry. A lock with an empty `layers` list does not match the schema, so reading it fails with `BP_LOCK_READ_FAILED`.
- The lock file MUST be written atomically: write to a temp file in the same directory as the target, then rename.
- The lock file MUST NOT exist in a partial state.
- The lock file MUST be written only after Copier has successfully committed the render.
- Boilerplate MUST be the exclusive writer of `boilerplate.lock`. External tools MUST NOT be expected to write it.
- Keys MUST be sorted deterministically (stable key order enables clean diffs).

> **Schema version format**: Schemas for files that Boilerplate writes as runtime state — `boilerplate.lock` (`"boilerplate/lock@1"`) and `.boilerplate/environment.yml` (`"boilerplate/environment@1"`) — use the namespaced format `namespace/schema@major`. Boilerplate MUST parse any such file sharing the same namespace and major version. Schemas for files that template or profile authors write — `boilerplate.yml` (TemplateMeta) and `boilerplate-env.yml` (EnvironmentProfile) — use a bare-major form (`"1"`, `"1.1"`) for authoring ergonomics; in those cases the namespace is implicit in the filename. The two formats are not interchangeable; each schema's `schema_version` row in this document is authoritative for that schema.

---

## Lifecycle Models

### UpdatePlan

The plan artifact produced by the update pipeline. Summarizes what will change if the update is applied.

| Field | Type | Notes |
|-------|------|-------|
| `current_root` | string | Current root template specifier |
| `target_root` | string | Target root template specifier |
| `layer_changes` | list[LayerChange] | Per-layer version changes |
| `classification` | enum | `PATCH`, `MINOR`, or `MAJOR` (highest wins) |
| `migrations_required` | list[string] | Populated when any of the trigger conditions in [06 §Migration trigger conditions](06-project-lifecycle.md#step-3-build-updateplan) hold; MUST be empty otherwise. 06 owns the authoritative trigger list and the MAJOR-update confirmation gate that consumes this field. |

**LayerChange**:

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Template name |
| `from_version` | string | Current version |
| `to_version` | string | Target version |
| `bump` | enum | `PATCH`, `MINOR`, or `MAJOR` |

---

### MigrationRecord

An entry in `.boilerplate/migrations.yml` recording one finished operation.

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Sequential integer starting at `"1"` (stored as string). The `created` record (when present) is always `id: "1"`. |
| `from_version` | string or null | Root template specifier before the operation (e.g., `"streamlit@0.1.0"`). `null` for `created` records (no prior state), `add` records (the added layer had no prior state) and `adopted` records (no prior Boilerplate state — the project existed under Copier but not under Boilerplate). |
| `to_version` | string | Root template specifier after the operation (e.g., `"streamlit@0.2.0"`). For `created` and `adopted` records, this is the template specifier the project is now bound to; for an `add` record, it is the specifier of the added layer. |
| `timestamp` | ISO 8601 datetime | UTC timestamp |
| `status` | enum | One of `success`, `failed`, `conflict`, `adopted`, `created`; see [MigrationRecord status state machine](#migrationrecord-status-state-machine) for the exit-code mapping and when each value is written. |
| `error` | string or null | Error message if status is not `success` (or `created`/`adopted`, both of which are success-shaped terminal values) |
| `classification` | enum or null | `PATCH`, `MINOR`, or `MAJOR` for `update` records; `null` for `created`, `adopted` and `add` records (no prior-version comparison applies). |
| `targets` | map[string, string] or null | On a `conflict` record, each layer of the paused walk keyed by `LockLayer.name` with the version the walk was updating it to. `null` on every other record. |
| `finished` | list[string] or null | On a `conflict` record, the names of the layers whose steps the paused walk completed, in walk order; the layer whose merge left conflict markers is among them. The run builds it from the [RestoreMarker](#restoremarker): the marker's `finished` followed by its `paused_layer` ([06 §Interrupted copy back](06-project-lifecycle.md#interrupted-copy-back)). `null` on every other record. |

**Invariants**: Entries MUST be append-only, and an existing entry MUST NOT be modified. A `conflict` record MUST be appended when a conflict pauses an update, and a `failed` record when a task fails after the copy back.

#### MigrationRecord status state machine

`status` carries five values, each written once when the operation ends. They map to CLI exit codes:

| Status | Exit code | Meaning |
| --- | --- | --- |
| `success` | 0 | Normal completion of an update. |
| `conflict` | 4 (ACTION_REQUIRED) | Merge conflicts requiring user resolution. The record names each layer's target version and the layers the paused walk finished, which is what `update` resumes from ([04 §Safe Update](04-composition-engine.md#safe-update)). |
| `failed` | 1 | A task failed after the copy back of an `update` or an `add` and the files were kept, under `--non-interactive` or by a terminal user's choice. A failure before the copy back leaves the checkout unchanged and appends no record. |
| `adopted` | 0 | Written by the adoption pipeline to distinguish adopted projects from created or updated projects in the audit trail. See §06 Part 2.5. |
| `created` | 0 | Written by `boilerplate new` as the first record on successful project creation. See §06 Part 1 Step 5. |

**Single write when the operation ends**: Every operation appends its record once, with its final status, when the operation ends, and never modifies an entry afterwards. `update` and `add` append a `success` record after the lock file has been written. An operation that leaves the checkout unchanged, such as one that fails before the copy back or whose copy back fails and is undone, appends no record. The state of a copy back cut off midway is kept in the [RestoreMarker](#restoremarker), not in the log. `adopt` and `create` write only Boilerplate-owned state files and have no merge-conflict path.

---

### IntentJournal

An intent journal records the in-progress state of a mutating operation for crash recovery. Written before the operation begins and deleted on successful completion.

| Field | Type | Description |
|-------|------|-------------|
| `operation` | enum | One of: `create`, `update`, `add`, `adopt`, `env_apply`. Identifies which mutating operation owns the journal so crash-recovery logic can dispatch to the operation-specific handler. The set MUST cover every command that participates in journal-based recovery. |
| `phase` | string | Current phase. Free-form string at the schema level; valid identifiers are operation-specific. See [IntentJournal phase vocabularies](#intentjournal-phase-vocabularies). |
| `started_at` | ISO 8601 | When the operation began |
| `staging_dir` | string | Path to the staging directory |
| `destination` | string | Path to the target project or environment |
| `template_ref` | string or null | Template reference (for create/update/add) |
| `profile_ref` | string or null | Profile reference (for env_apply) |

**File locations**: Project operations use `.boilerplate-commit-intent.json` in the staging directory. For `update` and `add`, the staging directory is the uniquely named temp folder that holds the worktree, and the journal sits beside the worktree so `git add -A` in the worktree never picks it up. Environment operations use `.boilerplate-env-intent.json` in the staging directory.

#### IntentJournal phase vocabularies

`phase` is a free-form string at the schema level so each operation's recovery handler can interpret its own phases. Per-operation vocabularies:

| Operation | Phase identifiers | Phase semantics |
| --- | --- | --- |
| `create`, `adopt` | `staging`, `committing`, `locking` | `locking` corresponds to writing `boilerplate.lock`. |
| `env_apply` | `staging`, `committing`, `locking` | Same three identifiers as project operations, but `locking` names the Record Write stage (Stage 6) — `environment.yml` is a provenance record, not a lock file. See [EnvironmentProvisionRecord](#environmentprovisionrecord) and §08 Stage 6. |

**Recovery behavior**: See [06-project-lifecycle.md](06-project-lifecycle.md) and [08-environment-provisioning.md](08-environment-provisioning.md) for how each operation dispatches on the phase identifiers above. `update` and `add` have no phase vocabulary of their own: the journal identifies the staging folder for stale cleanup only, and recovery of a cut-off copy back reads the [RestoreMarker](#restoremarker), whose `phase` is their one recovery vocabulary.

---

### RestoreMarker

A restore marker keeps the state of an `update` or `add` run that is copying its result back, so a run cut off there can be finished or set aside ([06 §Interrupted copy back](06-project-lifecycle.md#interrupted-copy-back)). Written before the copy back changes a file and removed after the run appends its record.

| Field | Type | Description |
|-------|------|-------------|
| `operation` | enum | `update` or `add` |
| `kind` | enum | `complete` when the walk finished every layer, `paused` when a conflict paused it |
| `phase` | enum | `copy_back` until the copy back ends, then `tasks` (a `complete` run's tasks run), then `recording` (the lock and the record remain). `update` and `add` pass the same phases. |
| `start_commit` | string | The commit HEAD pointed at when the run began |
| `result_commit` | string | The staging worktree's last per-layer commit, `start_commit` when no layer finished |
| `targets` | map[string, string] | Each layer of the walk keyed by `LockLayer.name` with the version the walk was updating it to, as in a `conflict` record |
| `finished` | list[string] | The names of the layers whose steps the walk finished, in walk order, the paused layer excluded. Empty when `kind` is `complete`. |
| `paused_layer` | string | The name of the layer whose merge left conflict markers, which no commit holds and which follows the finished layers in walk order. Absent when `kind` is `complete`. |
| `started_at` | ISO 8601 | When the run began |

**File location**: `git rev-parse --git-path boilerplate-restore.json`, which resolves under the git directory of the worktree the command runs in.

**Ref**: `refs/worktree/boilerplate/restore`, set with `git update-ref` to `result_commit` and removed with `git update-ref -d`. A `refs/worktree/` ref is per worktree, keeps the commit reachable after the stale-staging cleanup removes the staging folder, and is not shared with other worktrees. The ref is set before the marker is written and removed after the marker is removed. The marker is written with the same tmp-then-rename recipe as the other single-file state ([07 §Atomic Staged Write Pattern](07-operational-quality.md#atomic-staged-write-pattern)); a marker that does not parse stops the command with `BP_UPDATE_INTERRUPTED`.

The marker differs from the `IntentJournal`: the journal sits in the staging folder, which the stale cleanup removes, and the marker sits in the git directory so it outlives that folder.

---

## Environment Domain Models

### EnvironmentProfile

A declarative specification of the development toolchain required by a project or team. Profiles use proto's `.prototools` schema for tool version declarations and add Boilerplate-specific composition via `extends`.

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | — | Non-empty; identifies the profile logically |
| `version` | Version | Yes | — | Semantic version of this profile |
| `schema_version` | string | No | `"1"` | Schema major version. MUST be `"1"` for the current schema. Boilerplate MUST reject profiles with an unrecognized major version and SHOULD silently ignore unknown fields within a recognized version. |
| `extends` | list of string | No | `[]` | Ordered list of parent profile references |
| `tools` | map[string, string] | No | `{}` | Tool name → version constraint (proto-compatible) |
| `packages` | map[string, list[PackageRequirement]] | No | `{}` | Platform-keyed package requirements |
| `allowed_proto_plugins` | list of string | No | `[]` | Allowlist of proto tool/plugin identifiers permitted for this profile. When non-empty, proto MUST only install tools whose identifiers appear in this list. An empty list means no restriction. Plugin identifiers use proto's canonical tool names (e.g., `node`, `go`, `rust`, `python`). Violation raises `BP_ENV_PLUGIN_NOT_ALLOWED`. |

**Computed**:
- `specifier` → `{name}@{version}`, derived from the `name` and `version` fields

> **Enterprise deployments** SHOULD define an explicit `allowed_proto_plugins` list in their base environment profile to prevent unauthorized WASM plugin execution.

**`tools`** entries follow proto's version constraint syntax and are written to `.prototools` during provisioning. Example: `{"python": ">=3.11", "node": ">=18"}`.

**`packages`** entries are keyed by platform (`windows`, `wsl2`, `linux`, `macos`) and list platform-specific package requirements.

**PackageRequirement**:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | Yes | Human-readable package name |
| `source` | string | Yes | Package manager (`winget`, `scoop`, `apt`, `brew`, `dnf`) |
| `id` | string | No | Package manager-specific identifier (e.g., `Git.Git` for winget) |
| `version` | string | No | Version constraint |

### Environment Lock Strategy

Tool-level version locking and checksum verification are delegated to proto via its native `.protolock` file. Boilerplate enables this by setting `settings.unstable-lockfile = true` in the generated `.prototools`. Proto's lock file records exact resolved versions, checksums, and platform (OS/arch) for each tool — this is the reproducibility mechanism for Environment Provisioning.

Boilerplate does NOT maintain a separate `environment.lock` file for tool versions. Doing so would duplicate what proto already provides and violate "orchestrate, don't replace." Instead, Boilerplate records only what proto does not know: which profile was applied and how the `extends` chain was resolved.

### EnvironmentProvisionRecord

Written to `.boilerplate/environment.yml` after successful provisioning. Records the profile resolution and provisioning provenance. Tool-level version locking and checksums are in `.protolock` (owned by proto). See [08-environment-provisioning.md Part 5](08-environment-provisioning.md) for the full operational specification.

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | string | `"boilerplate/environment@1"` — namespaced schema version (same convention as `boilerplate/lock@1`) |
| `boilerplate_version` | string | Version of the Boilerplate tool that performed provisioning |
| `profile_name` | string | The root profile's name (e.g., `python-dev`) |
| `profile_version` | string | The root profile's version, PEP 440 (e.g., `1.2.0`) |
| `extends_chain` | list[string] | Ordered list of profile specifiers in topological order (base first, root last) |
| `applied_at` | ISO 8601 datetime | UTC timestamp of when provisioning completed |
| `tools` | map[string, string] | `{tool_name: exact_version}` for all installed tools |
| `proto_lock_hash` | string or null | SHA-256 hex digest of `.protolock` at time of apply; `null` if proto did not write `.protolock` |

**Invariants**:

- Written atomically (same pattern as `boilerplate.lock`).
- Written only after proto has successfully provisioned all tools and `.protolock` exists.
- Keys MUST be sorted deterministically.

**Ownership boundary**: Boilerplate owns `.boilerplate/environment.yml` (profile provenance). Proto owns `.protolock` (tool versions and checksums). The `boilerplate env status` command reads both to report the full environment state.

> **State, not audit**: `.boilerplate/environment.yml` is the single env-domain state file — a current-state projection holding the most recently applied state. `EnvironmentProvisionRecord` is overwritten in place on each successful `env apply`, not appended; the recovery story is simply "run `env apply` again". The env domain MUST NOT add a migrations-style append-only audit log: provisioning is idempotent and re-runnable, so it needs only the current-state record.

---

### Profile File

An environment profile is declared in a standalone YAML file named `boilerplate-env.yml`. This file is the profile definition; the `.prototools` file is the generated output written during provisioning.

**File locations**:

- **Profile definitions** (reusable, versioned): Stored in template directories alongside templates, discovered by a dedicated profile scanner that follows the same directory traversal pattern as `DirectoryTemplateRepository`. A directory containing `boilerplate-env.yml` is a profile source, analogous to a directory containing `boilerplate.yml` being a template source.
- **Project-local profile**: A `boilerplate-env.yml` in the project root applies to that project. Created by `boilerplate env apply` or manually by the developer.

**Discovery**: Profiles are discovered and registered in a `ProfileCatalog` (analogous to `TemplateCatalog`) using the same directory scan and "first one wins" registration policy. The `env apply <profile-spec>` command resolves a profile by name or `name@version` from this catalog.

**Relationship to `.prototools` and `.protolock`**: During `env apply`, Boilerplate reads the profile's `tools` section, merges any `extends` chain, and writes the resolved tool versions to `.prototools` in proto's native format. Boilerplate also sets `settings.unstable-lockfile = true` in the generated `.prototools` to enable proto's native `.protolock` file, which records exact resolved versions and checksums for reproducibility. `.prototools` and `.protolock` are generated artifacts — Boilerplate owns their lifecycle during provisioning, but proto owns their schema and reads them at runtime.

**ProfileCatalog operations**: The `ProfileCatalog` follows the same interface pattern as `TemplateCatalog`:

| Method | Input | Output | Notes |
|--------|-------|--------|-------|
| `register(profile)` | EnvironmentProfile | void | First-wins deduplication by `name@version` |
| `resolve(name, version?)` | name + optional version | EnvironmentProfile or null | Null version returns highest by PEP 440 |
| `list_all()` | — | list[EnvironmentProfile] | All registered profiles |

---

## Error Hierarchy

All errors inherit from `BoilerplateError` (the base class). Each exception type maps to one or more `BP_*` error codes (see [07-operational-quality.md](07-operational-quality.md)). The exception hierarchy is the implementation mechanism; the error codes are the stable public contract.

| Error | Exit code | Raised When |
|-------|-----------|------------|
| `BoilerplateError` | — | Base; never raised directly |
| `DirectoryValidationError` | `2` | A required directory path is missing, not a directory, or otherwise invalid |
| `TemplateNotFoundError` | `1` | A requested template cannot be located in the catalog |
| `InvalidVersionError` | `3` | A version string is not PEP 440 compliant |
| `InvalidTemplateSpecifierError` | `3` | A specifier string fails name/version validation |
| `MetadataValidationError` | `3` | `boilerplate.yml` is malformed or missing required fields |
| `ProfileError` | `1` | `profile.toml` exists but is not valid TOML, or a reserved section is not a table (`BP_CONFIG_PROFILE_INVALID`) |
| `DestinationRequiredError` | `3` | A non-interactive render names no destination, and the current directory is never assumed (`BP_INPUT_DEST_REQUIRED`) |
| `DestinationNotEmptyError` | `3` | The render destination exists and is non-empty, and `--force` was not provided |
| `NonInteractiveRequiresForceError` | `3` | A multi-layer render in non-interactive mode requires `--force` |
| `MissingRequiredAnswersError` | `3` | Non-interactive render cannot proceed because required answers are missing (no default, and not hidden by its `when`) |
| `InteractiveModeRequiresTtyError` | `3` | Interactive render requested but stdin is not a TTY, so prompts can never be answered |
| `InvalidDataError` | `3` | `--data`/`--data-file` input cannot be parsed: a `--data` entry has no `=`, the file cannot be read, or its YAML is not a mapping |
| `InteractiveRenderFailedError` | `1` | Copier's prompt machinery failed because the environment cannot host interactive prompts |
| `UserCancelledError` | `130` | The user cancelled an interactive prompt (e.g. Ctrl+C); translated from Copier's `CopierAnswersInterrupt` before its `(AnswersMap, Question, Template)` payload can reach the generic exception handler |
| `DependencyError` | — | Intermediate base for dependency resolution errors; never raised directly |
| `DependencyNotFoundError` | `1` | (extends `DependencyError`) A template referenced in `extends` cannot be found in the catalog |
| `DependencyCycleError` | `1` | (extends `DependencyError`) The dependency graph contains a cycle |
| `VersionConflictError` | `1` | (extends `DependencyError`) The same template resolves to incompatible versions in the graph (`BP_RESOLVE_VERSION_CONFLICT`) |
| `LockReadFailedError` | `1` | `boilerplate.lock` cannot be read as a lock file: unparseable YAML, a truncated write or a body that does not match the schema (`BP_LOCK_READ_FAILED`) |
| `LockSchemaUnsupportedError` | `1` | The lock file's `schema_version` major exceeds the major the running tool supports, so the tool neither reads nor mutates it (`BP_LOCK_SCHEMA_UNSUPPORTED`) |
| `RecordedAnswerRejectedError` | `3` | A recorded answer fails the target view's question type, choices or validator inside a layer's update step, after the layer's migrations; translated from Copier's `ValueError` |
| `AnswersFileIncompleteError` | `3` | Before any layer runs, a question of a layer's scoped view at the recorded versions that is neither secret nor hidden ([04 §Safe Update](04-composition-engine.md#safe-update) defines hidden) is recorded in neither the layer's own answers file nor its declaring layer's file; the error lists the layer and the keys |
| `UpdateLayerDriftError` | `3` | Before any layer runs, a layer and one of its ancestors both disagree with `boilerplate.lock`, with no pending `conflict` record to resume |
| `UpdateTargetMismatchError` | `3` | An explicit `--target-version` differs from the targets a pending `conflict` record names |
| `UpdateUnknownLayerError` | `3` | `update` was given a target for a layer the project's lock does not list; nothing is staged (`BP_UPDATE_LAYER_UNKNOWN`) |
| `ActionRequiredError` | — | Base for a recoverable pause that needs user action; never raised directly, exits `4` through its subclasses |
| `UpdateTargetExcludedError` | `3` | An explicit `--target-version <layer>@<version>` names a version that the `extends` constraint of another lock layer excludes; nothing is staged (`BP_UPDATE_TARGET_EXCLUDED`) |
| `UpdateConflictPausedError` | `4` | (extends `ActionRequiredError`) A layer's update left merge conflicts and the walk stopped (`BP_UPDATE_CONFLICT_PAUSED`) |
| `UpdateDowngradeError` | `3` | Before any layer runs, a target is older than the version a layer's answers file records in `_commit`, or a recorded `_commit` yields no version (`BP_UPDATE_DOWNGRADE_REJECTED`) |
| `UpdateProjectNotReadyError` | `3` | The project is not a git repository root with at least one commit, or its working tree has uncommitted changes, untracked files included (`BP_UPDATE_PROJECT_NOT_READY`) |
| `UpdatePathObstructedError` | `3` | Before the copy back, a path the walk added already exists in the checkout as an ignored file or directory (`BP_UPDATE_PATH_OBSTRUCTED`) |
| `UpdateInterruptedError` | `3` | The restore marker shows an earlier run cut off while restoring its result into the working tree, and the rerun cannot finish it: another command, a moved HEAD, a working tree that differs from the run's result, a run a conflict had paused, or a marker file that does not parse (`BP_UPDATE_INTERRUPTED`) |
| `UpdateCopyBackFailedError` | `1` | Copying the staging worktree back failed partway; the copy back was undone ([06 §Undo](06-project-lifecycle.md#undo)), the staging worktree is kept, the restore marker and its ref are removed and no record is appended (`BP_UPDATE_COPY_BACK_FAILED`) |
| `ProjectNotManagedError` | `3` | `add` found no `boilerplate.lock` in the project (`BP_UPDATE_PROJECT_NOT_MANAGED`) |
| `LayerAlreadyAddedError` | `3` | `add` named a template the lock already lists (`BP_UPDATE_LAYER_ALREADY_ADDED`) |
| `AddAncestorsMissingError` | `3` | A template the new layer extends is not in the lock (`BP_UPDATE_ANCESTORS_MISSING`) |
| `AddAncestorVersionError` | `3` | An ancestor's recorded version fails the new layer's `extends` reference (`BP_UPDATE_ANCESTOR_VERSION_MISMATCH`) |
| `UpdateTaskFailedError` | `1` | A task failed after the update's files were copied back; the update keeps the files and writes the lock under `--non-interactive` |
| `UpdateSubmodulesUnsupportedError` | `3` | `update` or `add` finds a `.gitmodules` file in the project, so the staging worktree cannot be created safely (`BP_UPDATE_SUBMODULES_UNSUPPORTED`) |
| `UpdateCheckoutChangedError` | `3` | The user's checkout changed while an `update` or `add` worked in the staging worktree, so the worktree is discarded before the copy back (`BP_UPDATE_CHECKOUT_CHANGED`) |
| `ConcurrencyContentionError` | `1` | Another Boilerplate operation still holds the project's advisory lock when the wait times out (`BP_CONCURRENCY_CONTENTION`) |
| `MergeConflictError` | `1` | Two layers declare incompatible values for the same configuration key |

Unrecognized exceptions outside this hierarchy MUST exit with code `1` (`FAILURE`). Exit-code semantics (what each code means) are specified in [§Exit Codes](#exit-codes) below.

---

## Settings and Configuration Files

Runtime settings (the `Settings` object) and the `boilerplate-sources.yml` catalog-source configuration file are operator-authored configuration — a different artifact class than the domain schemas defined in this document. Their full specification (fields, env vars, defaults, validation rules, read protocols) lives in [09-settings-and-configuration.md](09-settings-and-configuration.md). The `revoked-templates.yml` revocation file is reserved for Phase 4 (revocation is deferred); it is not a live operator-authored file.

---

## Exit Codes

| Code | Name | Meaning |
|------|------|---------|
| `0` | `SUCCESS` | Command completed successfully |
| `1` | `FAILURE` | General runtime failure |
| `2` | `CONFIG_ERROR` | Configuration or settings could not be loaded |
| `3` | `VALIDATION_ERROR` | Input validation failed |
| `4` | `ACTION_REQUIRED` | The operation requires user intervention before it can complete (e.g., merge conflicts during `update` that the user resolves and commits before rerunning `boilerplate update`). Distinguishes recoverable workflow pauses from hard failures (exit 1). Commands: `update` (merge conflicts). `env apply` does not produce exit 4 — per §08 Part 4, all provisioning failures roll back fully to exit 1; a partial-install resume path is a candidate future enhancement, not part of the contract. |
| `130` | `USER_CANCELLED` | The user cancelled an interactive prompt (Ctrl+C). Matches the POSIX `128 + SIGINT` convention Typer's own `KeyboardInterrupt` handler already uses, so every Ctrl+C in the CLI — inside a prompt or not — exits with the same code. |

Command-line usage errors — an unknown option, a missing argument, a rejected flag value — are input validation and exit `3`, overriding Click's own default of `2`, which this taxonomy reserves for `CONFIG_ERROR`.

> **Documented validation example**: Passing `--verbose` and `--quiet` together is mutually exclusive and exits with code `3` (`VALIDATION_ERROR`).
