# Implementation Status

This page tracks how much of Boilerplate's [design specification](https://therealbillsiegler.github.io/boilerplate/0.4/design/01-overview/index.md) is actually implemented in code today. It is maintained by hand: a feature is marked **Implemented** only when code backs it, and usually tests too.

The design docs describe the full target system; this page lists which parts are Implemented, Partial or Planned.

**Legend:** Implemented · Partial · Planned (design-only)

## At a glance

The implemented core is **local template composition**: discover templates from local directories, resolve an `extends` graph, merge their configuration and question schemas, and render through Copier. That pipeline ships end to end and is covered by the test suite, but several of design 04's contracts are still open (graph limits, the `run_worker` contract), so the area is rated Partial below. Beyond the core, two customization mechanisms ship: an env/`.env`-driven `Settings` object (three of design 09's ten Settings fields, plus two code-only extras) and the per-user **profile** (`profile.toml`); the earlier typed Profile model, its resolution chain, and the `boilerplate config` command were retired in favor of the profile. Reproducibility and lifecycle are partial: `new` writes `boilerplate.lock`, and the per-layer update and add engines (three-way merge, migration records) are implemented but driven only by tests, with no command wired to them. *Catalog federation* (remote/Git sources, trust tiers, search) and the *environment-provisioning subsystem* are design-only.

| Design area                                                                                                                         | Status  |
| ----------------------------------------------------------------------------------------------------------------------------------- | ------- |
| [01 — Overview / architecture](https://therealbillsiegler.github.io/boilerplate/0.4/design/01-overview/index.md)                    | Partial |
| [02 — Data models](https://therealbillsiegler.github.io/boilerplate/0.4/design/02-data-models/index.md)                             | Partial |
| [03 — Template system](https://therealbillsiegler.github.io/boilerplate/0.4/design/03-template-system/index.md)                     | Partial |
| [04 — Composition engine](https://therealbillsiegler.github.io/boilerplate/0.4/design/04-composition-engine/index.md)               | Partial |
| [05 — CLI reference](https://therealbillsiegler.github.io/boilerplate/0.4/design/05-cli-reference/index.md)                         | Partial |
| [06 — Project lifecycle](https://therealbillsiegler.github.io/boilerplate/0.4/design/06-project-lifecycle/index.md)                 | Partial |
| [07 — Operational quality](https://therealbillsiegler.github.io/boilerplate/0.4/design/07-operational-quality/index.md)             | Partial |
| [08 — Environment provisioning](https://therealbillsiegler.github.io/boilerplate/0.4/design/08-environment-provisioning/index.md)   | Planned |
| [09 — Settings & configuration](https://therealbillsiegler.github.io/boilerplate/0.4/design/09-settings-and-configuration/index.md) | Partial |
| [10 — Security](https://therealbillsiegler.github.io/boilerplate/0.4/design/10-security/index.md)                                   | Partial |

## Detailed status

### 01 — Overview / architecture Partial

- **Implemented:** Service split: resolver / composer / render engine as independent, wired classes
- **Partial:** Atomic / no-partial-output rendering — render is a sequential per-layer overlay with no transactional rollback, so a mid-render failure can leave partial output
- **Partial:** Pluggable repository abstraction — the ABC exists, but only the directory repository is implemented

### 02 — Data models Partial

- **Implemented:** `TemplateMeta`, `TemplateInfo`, `TemplateSpecifier`, `SerializableVersion`, `TemplateCatalog`
- **Partial:** `BoilerplateLock`, `LockLayer` and `MigrationRecord` (`models/`) — implemented; `new` writes the lock, and the update and add engines append migration records, driven only by tests

### 03 — Template system Partial

- **Implemented:** Local template discovery across multiple directory roots (`catalog/`, `repository/directory_repository.py`)
- **Implemented:** `extends`-based layering and topological composition
- **Implemented:** Bundled Jinja extensions and the `project` / `streamlit` scaffold templates
- **Planned:** Catalog federation, remote/Git sources, classification, and trust/verification levels — catalog is local-only; a Git-backed repository remains unimplemented, with no stub in code — `build_template_catalog` (`cli/utils.py`) constructs only the directory repository

### 04 — Composition engine Partial

The most mature area. The resolution → graph → merge → render pipeline works end to end and is heavily tested; the gaps are specific design 04 contracts, not missing pipeline stages.

- **Implemented:** Resolution, graph ordering, and composition (`composition/resolution/`, `composition/graph/`, `composition/composer.py`) — ordering is deterministic: siblings follow `extends` declaration order, with lexicographic order only across independent roots (design 04 Stage 2)
- **Implemented:** Config & question-schema merging — deep-merge of questions, dicts, and tasks, with dedicated strategies for `_jinja_extensions` (union) and `_min_copier_version` (highest wins) (`composition/merging/`). Note: this is *configuration-layer* merging, not file-level three-way merge.
- **Implemented:** Composition serialization to YAML/JSON (`composition/serialization/`)
- **Implemented:** Cycle detection and merge-conflict errors (`composition/graph/exceptions.py`, `composition/merging/exceptions.py`)
- **Implemented:** Version-conflict detection — an `extends` diamond that pins the same template name at two different versions is rejected during resolution, raising `VersionConflictError` with error code `BP_RESOLVE_VERSION_CONFLICT` (design 04 Stage 1) (`composition/resolution/resolver.py`, `composition/graph/exceptions.py`)
- **Planned:** Graph size/depth limits — `BP_GRAPH_*` covers cycles only
- **Partial:** `CopierWorker` abstraction — the `Worker` subclass ships as `ScopedWorker`, and composition renders and updates through it (`composition/rendering/scoped_worker.py`); the `run_worker` / `WorkerResult` contract and the startup `BP_COPIER_COMPAT_FAILED` check are not built
- **Implemented:** Per-layer answers files — each bundled template declares `_answers_file: .copier-answers.<layer>.yml` and ships the answers-file stub; Copier writes one per layer natively during that layer's render, and no canonical `.copier-answers.yml` is written (design 04's per-layer `_answers_file:` contract, the foundation for per-layer update)
- **Implemented:** Scoped rendering — `boilerplate new` asks the merged questionnaire once, then renders each layer under its scoped view (the questions and extensions of that layer and its ancestors), so each answers file records only its own scope; ancestors' file-path extensions load for the descendants that use them (`composition/rendering/engine.py`, `composition/views/`)

The questionnaire pass sees the merged `_jinja_extensions` union (see [What gets merged](https://therealbillsiegler.github.io/boilerplate/0.4/reference/merging/#what-gets-merged)), so a question default can use any layer's filter instead of crashing; the merged tasks run once, on the last layer.

### 05 — CLI reference Partial

See the [command table](#cli-specified-vs-implemented) below for the specified-vs-implemented command areas.

- **Implemented:** Global options (`--verbose/--quiet/--color/--ci/--version`) and Typer's own did-you-mean on a mistyped command
- **Implemented:** The banner above the top-level help — the braille logo beside the name, the name alone where the logo can't show, and its opt-outs (`cli/display/banner.py`, `cli/display/terminal_probe.py`)
- **Planned:** Design 05's confirmation contracts (plan-then-prompt for mutating commands) — no code; sequencing in the [backlog](https://therealbillsiegler.github.io/boilerplate/0.4/roadmap/#backlog)

### 06 — Project lifecycle Partial

- **Partial:** Project creation (`new`) — resolves, composes, and renders with `--dry-run`, `--force`, `--non-interactive`, `--no-tasks`, `--data`/`--data-file`, `--format json` (the flag names match design 05's Answer Presets contract except the missing `-d` short flag; `new` rejects `_`-prefixed keys in `--data-file` where the design warns and skips them, and `update` and `add` take no `--data` or `--data-file` yet). It ends by writing `boilerplate.lock` (`composition/rendering/creation_lock.py`).
- **Partial:** Lock-file generation (`boilerplate.lock`) — `new` writes it after a successful render: each layer's name, version, source, commit (null for a bundled folder), checksum, and a hash of each answers file. No command reads it yet
- **Partial:** Project update and layer add — the per-layer update and add engines are implemented (`composition/updating/`, `composition/adding/`) and driven only by tests; the `update` and `add` commands are planned

### 07 — Operational quality Partial

- **Implemented:** Logging via stdlib `logging` — Rich console on TTY; non-TTY / `--ci` stderr gets one strict-JSON object per event with `phase`, `operation`, `request_id`, `success`, and `error_code` on failure, plus `BOILERPLATE_REQUEST_ID` passthrough (`logging_config.py`). Redaction and `duration_ms` terminal events are not implemented.
- **Partial:** Error attribution — a uniform CLI error boundary, exception hierarchy, phase-tagged `BP_{PHASE}_{DESCRIPTOR}` codes, and per-exception remediation hints exist (`cli/utils.py`, `common/exceptions.py`); the `severity` / `retryable` fields are declared but hardcoded (`"error"` / `False`) on every exception and read by nothing yet, and attribution labels and the `--verbose` diagnostic block are not emitted
- **Implemented:** Exit codes — the design's canonical six-value set defined (`constants.py`), with `ACTION_REQUIRED=4` routed in the CLI error boundary (no shipped operation produces exit 4 yet; its first producer is the update conflict pause) and `USER_CANCELLED=130` shipped: Ctrl+C at a prompt exits 130 as clean cancellation
- **Partial:** Advisory locks and the intent journal — implemented (`common/file_lock.py`, `composition/staging/`) and used by the update and add engines, driven only by tests
- **Planned:** Metrics, performance budgets, retry policy, automation gates, and atomic staged writes for `new`

### 08 — Environment provisioning Planned

Design-only. There is no proto/toolchain code, no `.prototools`/`.protolock` generation, and no `env` command group. (The profile covers package index and container registry values — not toolchain versions or provisioning.)

### 09 — Settings & configuration Partial

Two mechanisms ship, both tested: an env-driven `Settings` object and the per-user **profile** (`profile.toml`). The rest of design 09's surface (the full `Settings` field set, catalog source config, revocation file) is not yet built. The typed `Profile` model, its resolution chain, and the `boilerplate config` command group were **retired** in the template-customization redesign; named default sets and a repurposed `config` command are designed but deferred.

- **Implemented:** `Settings` object loaded at every CLI startup — `BOILERPLATE_`-prefixed env vars and `.env`; ships five fields: three of design 09's ten (`default_templates_dir` and `extra_template_dirs` drive template-directory resolution, `debug` drives logging) plus `log_dir` and `file_logging_enabled`, which sit outside design 09's field set and are not consumed yet (`settings/settings.py`)
- **Implemented:** Profile loader: `[defaults]` + `[templates.<name>]` merged from `profile.toml` (`settings/profile.py`)
- **Implemented:** Platform-aware config-root resolution for `profile.toml` (`settings/paths.py`)
- **Planned:** The seven remaining design-09 `Settings` fields (four operation timeouts, `allowed_extension_packages`, `request_id`, `accessible`) and catalog source config (`boilerplate-sources.yml`) — design-only (the revocation file is reserved for Phase 4, not a pending surface)
- **Planned:** Named default sets + a repurposed `config` command to switch between them — designed, deferred
- **Retired** — the strict `Profile` model, the CLI/env/profile/defaults resolution chain, `config show/use/validate`, and the pre-profile migration hint (replaced by `profile.toml`)

### 10 — Security Partial

- **Partial:** YAML safety — boilerplate-owned files load through the shared hardened loader (`common/yaml_loading.py`): safe-load semantics plus duplicate mapping keys as errors and capped alias expansion, per design 03's YAML parsing rules; `copier.yml` parsing is delegated to Copier's own loader; `validate` warns on custom YAML tags in `boilerplate.yml`
- **Partial:** Execution posture — template tasks and Jinja extensions run under Copier's `unsafe` grant, scoped per layer to what that layer's Worker invocation loads (for extensions that is the layer's scoped view, its own and its ancestors' union, and the composition-wide union for the questionnaire pass — see design area 04 above), per the accepted permissive posture in [ADR-003](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-003-permissive-execution/index.md); trust-gated execution is deferred until remote sources ship
- **Planned:** Checksums, signatures, trust verification, and Jinja2 sandbox enforcement — no code exists

## CLI: specified vs implemented

| Command                              | Status      | Notes                                                                                                                       |
| ------------------------------------ | ----------- | --------------------------------------------------------------------------------------------------------------------------- |
| `new`                                | Partial     | Renders projects (incl. answers supplied with `--data`/`--data-file`) and writes `boilerplate.lock` (`cli/commands/new.py`) |
| `list`                               | Implemented | `cli/commands/templates.py`                                                                                                 |
| `compose`                            | Implemented | `cli/commands/compose.py`                                                                                                   |
| `graph`                              | Implemented | `cli/commands/graph.py`                                                                                                     |
| `validate`                           | Implemented | Template-dir well-formedness (`cli/commands/validate.py`)                                                                   |
| `config`                             | Planned     | Retired with the Profile system; a repurposed `config` for the profile is designed, deferred                                |
| `update`                             | Planned     | Planned; the per-layer update engine is implemented and driven only by tests                                                |
| `add`                                | Planned     | Planned; the add engine is implemented and driven only by tests                                                             |
| `status`                             | Planned     | Not implemented                                                                                                             |
| `adopt`                              | Planned     | Not implemented                                                                                                             |
| `eject`                              | Planned     | Not implemented                                                                                                             |
| `doctor`                             | Planned     | Not implemented                                                                                                             |
| `test`                               | Planned     | Not implemented                                                                                                             |
| `init-template`                      | Planned     | Not implemented                                                                                                             |
| `search`                             | Planned     | Discovery is `list` only — no search/filter/trust                                                                           |
| `env` (apply/status/diff/rollback/…) | Planned     | No `env` command group                                                                                                      |
| `lock` (migrate/verify)              | Planned     | No `lock` command; `new` writes the lock and nothing reads it                                                               |
| `cache warm`                         | Planned     | No cache layer                                                                                                              |
| shell completions                    | Partial     | Typer's built-in completion only                                                                                            |

## Known gaps

These are specified in the design docs but no shipped command exercises them — listed here so expectations are clear. Items 2 to 4 have engines implemented and driven only by tests, so they are partial; their commands are not yet wired. The rest are design-only:

1. **Using the lock (`boilerplate.lock`)** — `new` writes it, but no command reads it: there is no `lock verify`, `status` or `update`.
1. **Project update lifecycle** — the per-layer update engine is implemented and driven only by tests; the `update` command is not yet wired, so no shipped command diffs versions or applies an update.
1. **Three-way merge / conflict resolution** — the update engine merges through Copier and pauses on a conflict, driven only by tests; the only merge a shipped command performs is configuration-schema merging. The target semantics (conflict-pause, safe-orphan, never-auto-delete) are specified in [ADR-007](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-007-update-model/index.md).
1. **Migration records & rollback** — the update and add engines append migration records, driven only by tests; no shipped command writes them or exposes a rollback.
1. **Environment provisioning** — the entire proto toolchain subsystem and `env *` commands.
1. **Catalog federation & discovery** — remote/Git sources, `search`, trust tiers, classification.
1. **Security verification pipeline** — checksums, signatures, trust verification, Jinja sandbox.
1. **Operational quality remainder** — metrics, performance budgets, retry policy, and automation gates (advisory locks and the intent journal are partial, above; the phase-tagged error codes and six-value exit taxonomy are shipped; see design area 07 above).
1. **Lifecycle/quality commands** — `status`, `adopt`, `eject`, `doctor`, `test`, `init-template`, `cache warm`.

## Where next

- [Roadmap](https://therealbillsiegler.github.io/boilerplate/0.4/roadmap/index.md) — the sequencing these states feed.
- [Design specifications](https://therealbillsiegler.github.io/boilerplate/0.4/design/index.md) — the target being built toward.
- [Commands](https://therealbillsiegler.github.io/boilerplate/0.4/cli/index.md) — the shipped command surface in detail.

______________________________________________________________________

*This page reflects the state of the `develop` line. Please update it in the same PR whenever a feature moves between states.*
