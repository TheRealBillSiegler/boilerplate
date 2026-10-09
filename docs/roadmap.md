# Build-out roadmap

The [design specification suite](design/README.md) describes the target contract, [Implementation status](status.md) tracks what exists today, and this page sequences the path between them — phases ordered by dependency, not by design-document numbering, with effort labels that are scope-based (small / medium / large by blast radius and files touched), never clock time.

!!! info "How to read this page"
    Each phase lists what ships, why it sits where it does, and which design documents govern it. The [CI pipeline reference](governance/ci.md) describes the repository's own CI, and phase completion is recorded by releases — one minor version per completed phase — in the changelog. When a sequencing decision here no longer reflects reality, update this page in the same PR.

## Sequencing principle

**Primitives-first, just-in-time.** The design suite's slice numbering is not the build order. Operational primitives — atomic staged write, the lock file, checksums — are prerequisites of the lifecycle slices, so they ship first; bulk hardening that nothing yet depends on defers.

The design documents are well-factored, but two seams cross document boundaries and must be re-cut into the work:

1. **Artifact fetching** ([design 06](design/06-project-lifecycle.md) Part 3) is lifecycle-document content but federation-track work. It belongs to Phase 4, and Phase 3 declares an interface dependency on it.
2. **Per-operation invariants** in [design 07](design/07-operational-quality.md) ship *inside* the phase that introduces the operation needing them — they are **not** deferred hardening. The advisory lock attaches to every mutating operation. The intent journal attaches to **in-place** mutation, where a crash can strand partial state that the staging pattern cannot undo: it ships with Phase 3's update commit window, not with `new`, whose crash recovery is simply deleting the stale staging directory.

### Phase summary

| Phase | Theme | Depends on | Effort |
| --- | --- | --- | --- |
| 0 | Release gate: CI, error codes, YAML hardening, determinism, content audit | — | Small–medium per item |
| 1 | Provenance and atomicity for `new` (lock file, atomic render) | 0 | Large |
| 2 | Read-side lock tooling (`lock verify`, local-only) | 1 | Medium |
| 3 | `update` + `add` + `adopt` + `eject` — the longest pole | 1 (interface dep on 4 for remote) | Large |
| 4 | Catalog federation and remote sources | 1; parallel with 3 | Large |
| 5 | Environment provisioning | 0 (topology contract), 1 (primitives); parallel with 3 and 4 | Large |
| 6 | Observability track (cross-cutting) | Any time after 0 | Medium |

## Phase 0 — Release gate

Most of this is cheap now and is good launch hygiene. The CLI ships via the bootstrap installer (`scripts/install.ps1` on Windows), which installs uv and boilerplate from git and uses no PyPI name, so cutting the first public tag without a PyPI publish freezes nothing. The **distribution name** becomes genuinely irreversible only *once published to PyPI* (re-publishing under a different name orphans every prior PyPI install and silently mis-routes `pip install boilerplate` to the unrelated package — see [adr-008](design/adr-008-distribution-name.md)). The legal / no-leak items (LICENSE, NOTICE, a clean history) gate public *exposure* regardless of version. Everything else here (error-code rename, CI) is reversible during `0.x` per SemVer, so doing it now is good hygiene rather than a hard pre-tag deadline.

The gate's criteria:

1. **CI** — the full test suite runs from the repo root across the OS × Python matrix, with the `src/` doctests collected by an explicit step rather than silently omitted.
2. **Error codes** — every shipped code follows `BP_{PHASE}_{DESCRIPTOR}` and is registered in [design 07](design/07-operational-quality.md)'s Error Code Registry, so codes match the target scheme before anyone scripts against them.
3. **Hardened YAML loading** — all boilerplate-owned parse sites load through a shared helper with duplicate-key errors and capped alias expansion per [design 03](design/03-template-system.md), while `copier.yml` parsing is delegated to Copier's own loader.
4. **Topology determinism** — sibling order follows `extends` declaration order per [design 04](design/04-composition-engine.md) Stage 2, with lexicographic order only across independent roots, held by fixed-order regression tests.
5. **INT-007 content audit** — the license stance lives in `RELEASING.md`: all direct dependencies permissive, and one vendored docs asset (the Mermaid bundle) redistributed unmodified with upstream's LICENSE beside it (`docs/assets/mermaid.LICENSE`) and its embedded license banners intact. Re-verify `NOTICE` against what the tree actually vendors whenever vendored content changes — it is an acceptance criterion, not a settled fact. The history criterion is satisfied by publishing from a fresh repository — see the INT-007 acceptance criteria.
6. **ADR-003 decision recorded** (small) — going public under the documented permissive-execution posture is sanctioned by [ADR-003](design/adr-003-permissive-execution.md) while template sources are local and deliberately chosen. The hard deadline for trust-gated execution is **Phase 4 entry** — before remote/Git/community sources ship. Optionally, land a minimal tier-less consent gate early via Copier's native trust setting.

## Phase 1 — Provenance and atomicity for `new` (the spine)

Every later lifecycle feature stands on these two units. They are sequential, not parallel — both restructure the `new` render pipeline.

- **1b — Atomic staged-write render** (large): stage → verify → commit, with temp-then-rename semantics and the Windows non-atomic fallback. Crash recovery for `new` is deletion of the stale staging directory (timestamped staging names plus an age check) — the destination is untouched by construction, so no intent journal is needed here; the journal ships with Phase 3, whose in-place commit window is what it actually protects. Standalone value: a crash mid-render can no longer leave partial output.
- **1a — Lock emission on `new`** (large): the `BoilerplateLock` model plus checksums, written by `new`, with a **provenance-complete schema from day one** — per-layer name / version / source / commit / checksum and a trust-tier field, per [design 02](design/02-data-models.md) — so Phase 4 does not have to reshape it. Provenance-complete means exactly this verified core plus `schema_version` and `copier_version`. The `source_bundle` / `subdirectory` fields, and the `bundle_uri` and `bundle_checksum` fields, are **reserved/optional and deferred with the `wheel_bundle` seed cache** ([ADR-006](design/adr-006-template-distribution.md)) — recorded by external catalog or enterprise-infra tooling for air-gap restoration; they carry no logic today, are never consulted by `lock verify`, and must not be required by any shipped command. The cut fields `answers_hash` and `answers_preset_path` are not written to the lock file at all — no command reads them, and including them would calcify unconsumed surface in user-owned files. Attribution fields (`invoked_by`, `hostname`, `flags_used`) are fully cut from the schema. Each first-party template already declares `_answers_file:` and ships its answers-file stub (`{{ _copier_conf.answers_file }}.jinja`), per [ADR-015](design/adr-015-idiomatic-artifacts.md); this phase adds `copier_answers_file_hashes` recorded in the lock against those per-layer files, so locks are born update-ready; otherwise every project created during Phases 1–2 mints a legacy lock that Phase 3 must migrate. Also ships the `.boilerplate/migrations.yml` `created` record and the advisory-lock primitive for mutating operations. Standalone value: every new project carries verifiable provenance.

**Order: 1b, then 1a.** Landing the lock-write first would mean relocating it when 1b restructures the render pipeline.

## Phase 2 — Read-side lock tooling

`lock verify` only, explicitly scoped **local-only**: checksum recompute and answers-file hash compare against the lock written in Phase 1 (medium). `status` is deferred to Phase 3 — it must report drift, which requires the fetch layer (Phase 4) or at minimum the update machinery to have meaningful output; shipping it in Phase 2 would imply guarantees it cannot yet check. Source-reachability checks arrive with Phase 4's fetch layer; environment-state reporting arrives with Phase 5.

## Phase 3 — `update` + `add` + `adopt` (longest pole)

Ship **local-source update first**; remote-source update has a declared interface dependency on Phase 4's fetch layer (large overall).

Prerequisites inside the composition engine, in order:

1. The rest of the `CopierWorker` abstraction ([design 04](design/04-composition-engine.md), Copier Worker Interface): the `Worker` subclass ships, so what remains is the `run_worker` / `WorkerResult` contract and the startup `BP_COPIER_COMPAT_FAILED` check.
2. Per-layer answers-file consumption (the per-layer answers files projects already carry).
3. Version-conflict detection and graph size/depth limits.

Then the three-way merge envelope — `UpdatePlan`, the staging worktree, and the restore marker that keeps an interrupted copy back in git (`new`'s staging pattern needs neither, so Phase 1 defers it) — then `add`, which stages and copies back through the same worktree and restore marker to add a layer to a managed project, and finally `adopt`, which reuses the same machinery to bring an existing project under lock management. The conflict-pause / safe-orphan / never-auto-delete semantics governing this envelope are specified in [ADR-007](design/adr-007-update-model.md).

`status` ships here rather than in Phase 2: reporting drift requires the update machinery to have a meaningful reference point, and source-reachability checks require Phase 4's fetch layer. A Phase 2 `status` would silently omit the most useful signals.

`eject` also ships here: a guarded delete (requires the advisory mutex) that removes `boilerplate.lock` and the `.boilerplate/` directory, releasing a project from lock management — the inverse of `adopt`, reusing the same mutex and idempotency contract.

## Phase 4 — Catalog federation and remote sources

Runs in parallel with Phase 3 after Phase 1, under the [parallelism contract](#parallelism-contract) below (large).

- `boilerplate-sources.yml` plus the `CatalogSource` / trust model ([design 09](design/09-settings-and-configuration.md), [design 03](design/03-template-system.md)).
- Git source — build a Git-backed `TemplateRepository` — then archive sources and the local catalog cache. The wheel-bundle source stays deferred per [ADR-006](design/adr-006-template-distribution.md); build it only on demonstrated demand for an offline seed cache.
- TOFU pinning, the git credential helper, and the revoked-templates read protocol (Reserved for Phase 4 / remote sources) ([design 10](design/10-security.md)).
- **Owns artifact fetching** ([design 06](design/06-project-lifecycle.md) Part 3): the fetch layer lives here exclusively.
- **Carries the ADR-003 expiry:** full trust-tier consent gating must land at Phase 4 entry, together with the superseding ADR that [ADR-003](design/adr-003-permissive-execution.md)'s expiry clause requires.

!!! question "Open sequencing question — the git source became a first-party dependency"
    The same amendment moves the git source out of "Phase 4 nicety" and into the update spine's prerequisites: a project is only updatable if its answers files record a resolvable git source, so `new` must render first-party layers from a published repo (or a local clone) rather than the wheel's plain directories. Implementing the Git-backed `TemplateRepository` therefore gates the *updatable-project* outcome, not just catalog federation. Resolve before Phase 3 begins: either move the git source into Phase 1/early Phase 3, or accept that projects created before it lands are copy-only and rehome via a one-line `_src_path` edit.

## Phase 5 — Environment provisioning

Runs in parallel with Phases 3 and 4 (large). The build order within the phase, per [design 08](design/08-environment-provisioning.md):

profile models → `ProfileCatalog` and scanner → `extends` resolution → `.prototools` generation → `ProtoWorker` → `env apply` and `env status` (the `env` command group thin core).

Gated on the pinned topology-ordering contract from Phase 0: the profile `extends` resolution mirrors the composition topology, so the ordering semantics must be frozen before this phase consumes them.

## Phase 6 — Observability track

The genuinely cross-cutting work (medium): a single JSON-to-stderr structured log stream (no file rotation or aggregation), redaction plus a non-serializing secret type, subprocess-output capture at DEBUG, correlation IDs, the retry policy, and performance budgets per [design 07](design/07-operational-quality.md).

!!! warning "What is *not* in this phase"
    Advisory locks and intent journals are **not** here — locks ship inside Phases 1–5 attached to each mutating operation, and the journal, which identifies a staging folder for stale cleanup, ships with Phase 3's staged update, whose interrupted copy back the restore marker covers, per design 07 and the sequencing principle above. Placing them in a trailing hardening phase would mean retrofitting every command shipped before it.

## Backlog

Unsequenced planned scope — an item leaves the backlog once a phase adopts it into the sequencing above.

- **Merge strategy annotations** — per-field merge behavior (`append`, `unique`, `deep-merge`) instead of today's fixed strategy set.
- **Conflict reporting** — `compose --conflicts` flags file-level composition conflicts instead of silent overwrites.
- **Version specifiers in `extends`** — PEP 440 constraints (e.g. `parent@>=1.2`) pin a layer to a compatible parent version range instead of today's exact-version-only match.
- **File overlay preview** — `graph --files` shows which files each layer would touch before rendering.
- **Author lint** — fails the build when a layer's delta unnecessarily repeats a base default.
- **Generated-project CI scaffolding** — templates ship CI configuration for the generated project itself, not just the three quality-check commands you wire into your own CI provider.
- **A deploy-time and runtime guardrail layer** — checks that run after generation, not only at scaffold time.
- **Design 05's confirmation contracts** — plan-then-prompt for mutating commands: `update`, `add`, `env apply`, and `eject` show their plan before acting.
- **A backward-compatibility test suite** — pins the public surfaces (CLI, template contract, lock schema) and fails CI on an accidental break.

## Release workstream

Independent of the feature phases, sequenced against the go-public decision:

- **Day-one distribution:** the bootstrap installer — `scripts/install.ps1` on Windows installs uv + boilerplate from git, needs no PyPI name.
- **Cross-platform bootstrap:** a macOS/Linux equivalent of `install.ps1` (e.g. `install.sh`), so the bootstrap-first install is canonical on every platform.
- **Publish pipeline (fallback / parallel, non-gating):** a GitHub Actions release pipeline — PyPI via OIDC trusted publisher, tag-driven — per INT-010 in the [intentions register](intentions/README.md); deferred until the PyPI distribution name (`boilerplate-cli`, adr-008) is final.
- **Template publishing:** deterministic per-template extraction (`git subtree split`) from the authoring monorepo, publishing the resulting repositories with tags kept in sync with each template's `boilerplate.yml` version — the canonical first-party distribution channel per [ADR-006](design/adr-006-template-distribution.md). The wheel-bundled seed cache is an optional, deferred item, built only on demonstrated demand.
- **Version checkpoints:** wired to the release checklist in `RELEASING.md`. Proposal: `0.3.0` = Phase 0 complete, cut at go-public; one minor version per completed phase after that.
- **Dormant `ci/` content:** the Azure Pipelines templates under `ci/` are first-party template substrate per PROD-001 — shipped product material, not this repository's own CI. Standing decision: relocate them into template material when the catalog work lands; never delete them, and exclude them from the repo's own CI concerns.

## Parallelism contract

Tracks 3, 4, and 5 may proceed in parallel after Phase 1 **only** under three conditions:

1. The lock schema ships **provenance-complete in Phase 1a** (source, commit, checksum, trust-tier field), so Phase 4 extends values rather than reshaping the model Phase 3 is consuming.
2. The fetch/Git layer belongs **exclusively to Phase 4**, and Phase 3 declares an explicit interface dependency on it for remote-source update, shipping local-source update first.
3. The shared merge points — command registration in `cli/cli.py`, `common/exceptions.py`, and `constants.py` — are treated as **append-only**. They are coordination points, not evidence of independence.

If any condition fails, the affected tracks serialize.

## Tracking

- One **milestone** per phase.
- One **epic** per phase — a parent issue with native sub-issues — linking the phase's governing design documents.
- **`area:*` labels** per component, doubling as a spec-coverage map.
- Optionally a **GitHub Projects v2 board** with Status / Area / Size / Priority fields and Board / Table / Roadmap views.

All tracker scaffolding is created once the repository is public (see INT-007 in the [intentions register](intentions/README.md)).

## Where next

- [Implementation status](status.md) — what exists today, the ground truth under this sequencing.
- [Contributing](governance/contributing.md) — how to pick up work aligned with the current phase.
