# Implementation Status

This page tracks how much of Boilerplate's [design specification](design/01-overview.md) is actually implemented in code today. It is maintained by hand and kept deliberately conservative: a feature is only marked **Implemented** when there is shipping code (and usually tests) behind it.

!!! info "Why this page exists"
    Boilerplate's design docs describe the full intended system. The code is a well-tested subset of that vision. This page is the honest map between the two so you can tell what works today versus what is still on the roadmap.

**Legend:** :material-check-circle:{ .status-shipped } Implemented · :material-progress-clock:{ .status-partial } Partial · :material-circle-outline:{ .status-design } Planned (design-only)

**Last updated:** 2026-08-05

## At a glance

The implemented core is **local template composition**: discover templates from local directories, resolve an `extends` graph, merge their configuration and question schemas, and render through Copier. That pipeline ships end to end and is covered by the test suite, but several of design 04's contracts are still open (graph limits, the `CopierWorker` abstraction), so the area is rated Partial below. Beyond the core, two customization mechanisms ship: an env/`.env`-driven `Settings` object (three of design 09's ten Settings fields, plus two code-only extras) and the per-user **profile** (`profile.toml`); the earlier typed Profile model, its resolution chain, and the `boilerplate config` command were retired in favor of the profile. Everything tied to *reproducibility and lifecycle* (lock files, project updates, three-way merge), *catalog federation* (remote/Git sources, trust tiers, search), and the *environment-provisioning subsystem* is currently design-only.

| Design area | Status |
| --- | --- |
| [01 — Overview / architecture](design/01-overview.md) | :material-progress-clock:{ .status-partial } Partial |
| [02 — Data models](design/02-data-models.md) | :material-progress-clock:{ .status-partial } Partial |
| [03 — Template system](design/03-template-system.md) | :material-progress-clock:{ .status-partial } Partial |
| [04 — Composition engine](design/04-composition-engine.md) | :material-progress-clock:{ .status-partial } Partial |
| [05 — CLI reference](design/05-cli-reference.md) | :material-progress-clock:{ .status-partial } Partial |
| [06 — Project lifecycle](design/06-project-lifecycle.md) | :material-progress-clock:{ .status-partial } Partial |
| [07 — Operational quality](design/07-operational-quality.md) | :material-progress-clock:{ .status-partial } Partial |
| [08 — Environment provisioning](design/08-environment-provisioning.md) | :material-circle-outline:{ .status-design } Planned |
| [09 — Settings & configuration](design/09-settings-and-configuration.md) | :material-progress-clock:{ .status-partial } Partial |
| [10 — Security](design/10-security.md) | :material-progress-clock:{ .status-partial } Partial |

## Detailed status

### 01 — Overview / architecture :material-progress-clock:{ .status-partial }

- :material-check-circle:{ .status-shipped } Service split: resolver / composer / render engine as independent, wired classes
- :material-progress-clock:{ .status-partial } Atomic / no-partial-output rendering — render is a sequential per-layer overlay with no transactional rollback, so a mid-render failure can leave partial output
- :material-progress-clock:{ .status-partial } Pluggable repository abstraction — the ABC exists, but only the directory repository is implemented

### 02 — Data models :material-progress-clock:{ .status-partial }

- :material-check-circle:{ .status-shipped } `TemplateMeta`, `TemplateInfo`, `TemplateSpecifier`, `SerializableVersion`, `TemplateCatalog`
- :material-circle-outline:{ .status-design } Lock / Project / MigrationRecord models — no code exists for any of these

### 03 — Template system :material-progress-clock:{ .status-partial }

- :material-check-circle:{ .status-shipped } Local template discovery across multiple directory roots (`catalog/`, `repository/directory_repository.py`)
- :material-check-circle:{ .status-shipped } `extends`-based layering and topological composition
- :material-check-circle:{ .status-shipped } Bundled Jinja extensions and the `project` / `streamlit` scaffold templates
- :material-circle-outline:{ .status-design } Catalog federation, remote/Git sources, classification, and trust/verification levels — catalog is local-only; a Git-backed repository remains unimplemented, with no stub in code — `build_template_catalog` (`cli/utils.py`) constructs only the directory repository

### 04 — Composition engine :material-progress-clock:{ .status-partial }

The most mature area. The resolution → graph → merge → render pipeline works end to end and is heavily tested; the gaps are specific design 04 contracts, not missing pipeline stages.

- :material-check-circle:{ .status-shipped } Resolution, graph ordering, and composition (`composition/resolution/`, `composition/graph/`, `composition/composer.py`) — ordering is deterministic: siblings follow `extends` declaration order, with lexicographic order only across independent roots (design 04 Stage 2)
- :material-check-circle:{ .status-shipped } Config & question-schema merging — deep-merge of questions, dicts, and tasks, with dedicated strategies for `_jinja_extensions` (union) and `_min_copier_version` (highest wins) (`composition/merging/`). Note: this is *configuration-layer* merging, not file-level three-way merge.
- :material-check-circle:{ .status-shipped } Composition serialization to YAML/JSON (`composition/serialization/`)
- :material-check-circle:{ .status-shipped } Cycle detection and merge-conflict errors (`composition/graph/exceptions.py`, `composition/merging/exceptions.py`)
- :material-check-circle:{ .status-shipped } Version-conflict detection — an `extends` diamond that pins the same template name at two different versions is rejected during resolution, raising `VersionConflictError` with error code `BP_RESOLVE_VERSION_CONFLICT` (design 04 Stage 1) (`composition/resolution/resolver.py`, `composition/graph/exceptions.py`)
- :material-circle-outline:{ .status-design } Graph size/depth limits — `BP_GRAPH_*` covers cycles only
- :material-circle-outline:{ .status-design } `CopierWorker` abstraction — Copier's `Worker` is invoked directly; the isolation interface design 04 specifies does not exist
- :material-check-circle:{ .status-shipped } Per-layer answers files — each bundled template declares `_answers_file: .copier-answers.<layer>.yml` and ships the answers-file stub; Copier writes one per layer natively during that layer's render, and no canonical `.copier-answers.yml` is written (design 04's per-layer `_answers_file:` contract, the foundation for per-layer update)

The merged `_jinja_extensions` union (see [What gets merged](reference/merging.md#what-gets-merged)) lets a question default or task use a sibling layer's filter instead of crashing.

### 05 — CLI reference :material-progress-clock:{ .status-partial }

See the [command table](#cli-specified-vs-implemented) below for the specified-vs-implemented command areas.

- :material-check-circle:{ .status-shipped } Global options (`--verbose/--quiet/--color/--ci/--version`) and Typer's own did-you-mean on a mistyped command
- :material-check-circle:{ .status-shipped } The banner above the top-level help — the braille logo beside the name, the name alone where the logo can't show, and its opt-outs (`cli/display/banner.py`, `cli/display/terminal_probe.py`)
- :material-circle-outline:{ .status-design } Design 05's confirmation contracts (plan-then-prompt for mutating commands) — no code; sequencing in the [backlog](roadmap.md#backlog)

### 06 — Project lifecycle :material-progress-clock:{ .status-partial }

- :material-progress-clock:{ .status-partial } Project creation (`new`) — resolves, composes, and renders with `--dry-run`, `--force`, `--non-interactive`, `--no-tasks`, `--data`/`--data-file`, `--format json` (the shipped flag names and prompting semantics diverge from design 05's Answer Presets contract). **It does not write a lock file.**
- :material-circle-outline:{ .status-design } Lock-file generation (`boilerplate.lock`) — no code reads or writes a lock file
- :material-circle-outline:{ .status-design } Project update (`update` command), three-way merge, migration records, and rollback — none implemented

### 07 — Operational quality :material-progress-clock:{ .status-partial }

- :material-check-circle:{ .status-shipped } Logging via stdlib `logging` — Rich console on TTY; non-TTY / `--ci` stderr gets one strict-JSON object per event with `phase`, `operation`, `request_id`, `success`, and `error_code` on failure, plus `BOILERPLATE_REQUEST_ID` passthrough (`logging_config.py`). Redaction and `duration_ms` terminal events are not implemented.
- :material-progress-clock:{ .status-partial } Error attribution — a uniform CLI error boundary, exception hierarchy, phase-tagged `BP_{PHASE}_{DESCRIPTOR}` codes, and per-exception remediation hints exist (`cli/utils.py`, `common/exceptions.py`); the `severity` / `retryable` fields are declared but hardcoded (`"error"` / `False`) on every exception and read by nothing yet, and attribution labels and the `--verbose` diagnostic block are not emitted
- :material-check-circle:{ .status-shipped } Exit codes — the design's canonical six-value set defined (`constants.py`), with `ACTION_REQUIRED=4` routed in the CLI error boundary (no shipped operation produces exit 4 yet; its first producer is the update conflict pause) and `USER_CANCELLED=130` shipped: Ctrl+C at a prompt exits 130 as clean cancellation
- :material-circle-outline:{ .status-design } Metrics, performance budgets, retry policy, automation gates, and the per-operation invariants (advisory locks, intent journal, atomic staged writes)

### 08 — Environment provisioning :material-circle-outline:{ .status-design }

Design-only. There is no proto/toolchain code, no `.prototools`/`.protolock` generation, and no `env` command group. (The profile covers package index and container registry values — not toolchain versions or provisioning.)

### 09 — Settings & configuration :material-progress-clock:{ .status-partial }

Two mechanisms ship, both tested: an env-driven `Settings` object and the per-user **profile** (`profile.toml`). The rest of design 09's surface (the full `Settings` field set, catalog source config, revocation file) is not yet built. The typed `Profile` model, its resolution chain, and the `boilerplate config` command group were **retired** in the template-customization redesign; named default sets and a repurposed `config` command are designed but deferred.

- :material-check-circle:{ .status-shipped } `Settings` object loaded at every CLI startup — `BOILERPLATE_`-prefixed env vars and `.env`; ships five fields: three of design 09's ten (`default_templates_dir` and `extra_template_dirs` drive template-directory resolution, `debug` drives logging) plus `log_dir` and `file_logging_enabled`, which sit outside design 09's field set and are not consumed yet (`settings/settings.py`)
- :material-check-circle:{ .status-shipped } Profile loader: `[defaults]` + `[templates.<name>]` merged from `profile.toml` (`settings/profile.py`)
- :material-check-circle:{ .status-shipped } Platform-aware config-root resolution for `profile.toml` (`settings/paths.py`)
- :material-circle-outline:{ .status-design } The seven remaining design-09 `Settings` fields (four operation timeouts, `allowed_extension_packages`, `request_id`, `accessible`) and catalog source config (`boilerplate-sources.yml`) — design-only (the revocation file is reserved for Phase 4, not a pending surface)
- :material-circle-outline:{ .status-design } Named default sets + a repurposed `config` command to switch between them — designed, deferred
- **Retired** — the strict `Profile` model, the CLI/env/profile/defaults resolution chain, `config show/use/validate`, and the pre-profile migration hint (replaced by `profile.toml`)

### 10 — Security :material-progress-clock:{ .status-partial }

- :material-progress-clock:{ .status-partial } YAML safety — boilerplate-owned files load through the shared hardened loader (`common/yaml_loading.py`): safe-load semantics plus duplicate mapping keys as errors and capped alias expansion, per design 03's YAML parsing rules; `copier.yml` parsing is delegated to Copier's own loader; `validate` warns on custom YAML tags in `boilerplate.yml`
- :material-progress-clock:{ .status-partial } Execution posture — template tasks and Jinja extensions run under Copier's `unsafe` grant, scoped per layer to what that layer's Worker invocation loads (for extensions that is the composition-wide merged union — see design area 04 above), per the accepted permissive posture in [ADR-003](design/adr-003-permissive-execution.md); trust-gated execution is deferred until remote sources ship
- :material-circle-outline:{ .status-design } Checksums, signatures, trust verification, and Jinja2 sandbox enforcement — no code exists

## CLI: specified vs implemented

| Command | Status | Notes |
| --- | --- | --- |
| `new` | :material-progress-clock:{ .status-partial } Partial | Renders projects (incl. answers supplied with `--data`/`--data-file`); does not write a lock file (`cli/commands/new.py`) |
| `list` | :material-check-circle:{ .status-shipped } | `cli/commands/templates.py` |
| `compose` | :material-check-circle:{ .status-shipped } | `cli/commands/compose.py` |
| `graph` | :material-check-circle:{ .status-shipped } | `cli/commands/graph.py` |
| `validate` | :material-check-circle:{ .status-shipped } | Template-dir well-formedness (`cli/commands/validate.py`) |
| `config` | :material-circle-outline:{ .status-design } | Retired with the Profile system; a repurposed `config` for the profile is designed, deferred |
| `update` | :material-circle-outline:{ .status-design } | No update lifecycle |
| `status` | :material-circle-outline:{ .status-design } | Not implemented |
| `adopt` | :material-circle-outline:{ .status-design } | Not implemented |
| `eject` | :material-circle-outline:{ .status-design } | Not implemented |
| `doctor` | :material-circle-outline:{ .status-design } | Not implemented |
| `test` | :material-circle-outline:{ .status-design } | Not implemented |
| `init-template` | :material-circle-outline:{ .status-design } | Not implemented |
| `search` | :material-circle-outline:{ .status-design } | Discovery is `list` only — no search/filter/trust |
| `env` (apply/status/diff/rollback/…) | :material-circle-outline:{ .status-design } | No `env` command group |
| `lock` (migrate/verify) | :material-circle-outline:{ .status-design } | No lock subsystem |
| `cache warm` | :material-circle-outline:{ .status-design } | No cache layer |
| shell completions | :material-progress-clock:{ .status-partial } Partial | Typer's built-in completion only |

## Known gaps (design-only)

These are specified in the design docs but have **zero implementation** today — listed here so expectations are clear:

1. **Lock files (`boilerplate.lock`)** — nothing writes or reads a lock file yet.
2. **Project update lifecycle** — no `update` command, version diffing, or apply.
3. **Three-way merge / conflict resolution** — only configuration-schema merging exists. The target semantics (conflict-pause, safe-orphan, never-auto-delete) are specified in [ADR-007](design/adr-007-update-model.md).
4. **Migration records & rollback.**
5. **Environment provisioning** — the entire proto toolchain subsystem and `env *` commands.
6. **Catalog federation & discovery** — remote/Git sources, `search`, trust tiers, classification.
7. **Security verification pipeline** — checksums, signatures, trust verification, Jinja sandbox.
8. **Operational quality remainder** — metrics, performance budgets, retry policy, automation gates, advisory locks, and the intent journal (the phase-tagged error codes and six-value exit taxonomy are shipped; see design area 07 above).
9. **Lifecycle/quality commands** — `status`, `adopt`, `eject`, `doctor`, `test`, `init-template`, `cache warm`.

## Where next

- [Roadmap](roadmap.md) — the sequencing these states feed.
- [Design specifications](design/README.md) — the target being built toward.
- [Commands](cli.md) — the shipped command surface in detail.

---

*This page reflects the state of the `develop` line at the date above. Please update it in the same PR whenever a feature moves between states.*
