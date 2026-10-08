# ADR-007: Safe-update model — conflict is a pause, structural change is migration-driven

**Status**: Accepted **Date**: 2026-06-20 **Deciders**: Project team

## Context

`boilerplate update` performs a per-layer `copier update`; Copier performs the only merge (INT-003, [04 §Safe Update](04-composition-engine.md)). Three questions bear on the update model: (1) what happens on a merge conflict, (2) what happens when the template's `extends` chain changed since lock time (the [ADR-001](adr-001-build-vs-adopt.md) HIGH-severity gap), and (3) whether `update` must walk one version at a time within a layer when a template version can carry a migration. On (1), [06 §Step 5](06-project-lifecycle.md#step-5-failure-and-conflict) specifies that a conflict brings back the finished layers with Copier's markers and exits 4 (`ACTION_REQUIRED`), after which the user resolves, commits and reruns `boilerplate update`, and [02](02-data-models.md) records the pause as the `conflict` MigrationRecord state. The `MergeConflictError → exit 1` row in the [02](02-data-models.md) Error-Hierarchy table is a *different* condition — the composition-time config-merge error (two layers declaring incompatible values for one key, per [04](04-composition-engine.md)) — unrelated to the update file-conflict. This ADR states the model on (1) and decides (2) and (3).

## Decision

**A conflict is a designed pause, not a failure.** On a layer reporting conflicts, `update` stops the walk, copies the layers finished so far into the working tree as uncommitted changes with Copier's conflict markers, records a `conflict` MigrationRecord, writes no lock, and exits **4 (`ACTION_REQUIRED`)**. The user resolves the markers, commits as with plain Copier, and reruns `boilerplate update`; a layer already at its target is skipped, so the answers files record the progress, and the rerun writes the new lock and a `success` record. `git stash --include-untracked` sets the partial update aside. **Every other error removes the staging worktree** ([06 §Staging worktree](06-project-lifecycle.md#staging-worktree)), which leaves the working tree unchanged with no lock and no migration record, and exits by the error's class (1 for an unexpected failure). INT-003's "atomic, no partial state" guarantee applies to *failures*; a pause is intentional.

**A changed `extends` chain is handled by author migrations, not provenance inference.**

- *Added* layer → a fresh `copier copy` that writes only paths not already present, so a descendant's file keeps its precedence as at compose, + new answers file, folded into the lock; the update reports the colliding paths it left.
- *Removed* layer → Boilerplate drops it from the managed set; **file cleanup is the job of a Copier `_migrations` script in the template that removed the dependency** (the removed layer's own migrations never run, because it is no longer in the chain). Copier runs migrations across the version range in a single pass — Boilerplate does not loop (see [§Version jumps](#version-jumps-stay-single-pass-migrations-are-jump-safe-by-authoring-contract)).
- *No migration provided* → **safe-orphan + WARN**: leave the files in place (now unmanaged), name them, and give guidance. Boilerplate **never infers file provenance and never auto-deletes.**
- Dry-run preview cannot predict migration file effects (they are arbitrary scripts — Copier's `--pretend` has the same limit); the plan shows version/layer deltas and *which* migrations will run.

**Update behavior is per-layer**, keyed on git-backing (see [ADR-006](adr-006-template-distribution.md)): published-repo and local-git layers update three-way. A plain local-directory layer (`commit: null`, marking a non-git source) does not update: Copier has no two-way fallback, so a layer with no recoverable old ref refuses to update, and `boilerplate update` skips it with a warning ([ADR-015](adr-015-idiomatic-artifacts.md) point 5; [§06](06-project-lifecycle.md#step-4-three-way-merge)).

**`commit: null` costs a ref to check out, not recoverable information — but it does not heal itself.** The lock records the layer's *version* even when `commit` is null, and Copier reconstructs the three-way merge base by *re-rendering* the old version rather than storing one, so nothing needed for a later merge is lost. What a null commit does withhold is the ref Copier checks out to do that re-render, and Copier resolves that ref from `_commit`/`_src_path` in its own answers file — which [ADR-015](adr-015-idiomatic-artifacts.md) forbids Boilerplate from rewriting. A first-party layer created before [ADR-006](adr-006-template-distribution.md)'s published repositories exist therefore stays **copy-only** until its `_src_path` is rehomed to the published repository by hand: the documented one-line edit of [ADR-015](adr-015-idiomatic-artifacts.md) point 5. After that edit the recorded version resolves to a tag, Copier reconstructs the base by re-render, and the three-way merge proceeds normally. Copy-only is permanent **only** for *genuinely* non-git sources (a user's plain local directory, which never gains a tag). Recording the real `commit` at creation stays strictly stronger (an immutable pin vs. a mutable tag) and remains the target.

**Git-backed distribution ([ADR-006](adr-006-template-distribution.md)) is not a prerequisite of lock creation.** Because a `commit: null` lock withholds only a ref and no recoverable information (above), `new` / `lock` / `verify` / `adopt` do not wait on the published distribution; what they cannot promise for a layer created before it is a clean three-way `update`, which needs the one-line `_src_path` rehome first. The rehome is a user-run edit, so the distribution work gates the clean-three-way quality of update-apply and does not block lock creation. Where it lands in the sequence is the roadmap's call.

### Version jumps stay single-pass; migrations are jump-safe by authoring contract

`update` crosses a layer's version range in a single pass and does not walk one version at a time, even when the crossed versions carry migrations. The evidence is in [§Verification](#verification-2026-07-28), which established:

- **Copier's migration model is fix-up, not replay.** A migration's `version:` key is a *gate* (`target ≥ version > source`), not a checkpoint. In a v1→v3 jump every crossed migration runs exactly once, in list order, all against the same tree — the pre-update tree for `before`-stage entries, the fully rendered target tree for `after`-stage ones (the default stage). **No intermediate tree is ever materialized.** A migration that assumes it sees the tree as of the version it names is therefore wrong under any jump.
- **The migration list comes only from the target version's `copier.yml`.** Nothing is read from intermediate tags. Two consequences bind template authors: every historical migration entry MUST be carried forward in every later release, or jumpers silently skip it; and a stepped walk executes each intermediate tag's *own copy* of a migration, so stepping and jumping can run **different code** for the same nominal migration — stepping is not a safer subset of jumping, it is a different execution.

**Why stepping is not adopted anyway** (reasoning from the above, not separately measured): each step is another three-way merge against the same layer, so each is another chance to pause on the same overridden files, and — because migrations are arbitrary commands with no layer awareness (below) — another chance for a base-layer migration to touch overlay-owned files. Stepping also requires Boilerplate to enumerate and walk intermediate tags: a loop Copier does not provide (verified absent from its update path in 9.15.0), which [ADR-001](adr-001-build-vs-adopt.md) says we do not build for ourselves.

**The authoring contract that makes single-pass safe** (first-party templates MUST; documented for third parties):

1. **Jump-safe:** a migration inspects actual state before acting and is idempotent — never "the tree is at version N-1, so move X to Y" but "if X exists, move it to Y." It must be correct when run against the target tree with any supported older version as the source.
2. **Carried forward:** historical migration entries stay in `_migrations` in every later release, in ascending version order — Copier executes the list in declaration order rather than sorting by version (read from Copier's source; ordering was not exercised empirically).
3. **Layer-scoped by discipline:** a migration touches only files its own template owns. Copier has no ownership model — a base-layer migration can overwrite an overlay-owned file silently, and a later update of the owning layer will not detect, conflict on, or repair it.
4. **Conflict-aware:** an `after`-stage migration MUST tolerate conflict markers in files it reads. Migrations run even when the merge left unresolved conflicts — Copier reports exit 0 and writes the new `_commit` regardless — and a migration that exits non-zero fails the whole update. Destructive or parsing work belongs behind a state check, not in a bare `after` migration.

**Orchestration consequences.** `boilerplate update` MUST detect the conflict pause itself — via git unmerged paths or a marker scan, never Copier's exit code — and MUST halt the layer walk at the first paused layer rather than running later layers over an unresolved tree. `--skip-tasks` does **not** skip migrations (documented Copier behavior), so there is no built-in defer; the pause envelope is Boilerplate's. An update that actually crosses a declared migration requires Copier's `--trust` (a template whose migrations all fall outside the crossed range does not), which `boilerplate update` supplies for first-party templates under [ADR-003](adr-003-permissive-execution.md) and must gate for untrusted sources — note that the first release introducing a migration is where an otherwise-working non-interactive pipeline starts failing (Copier exits 4 and applies nothing at all) unless trust is passed.

**A paused update resumes from its `conflict` record, not from version comparison.** The `conflict` MigrationRecord names each layer's target version and the layers the paused walk finished ([02 §MigrationRecord](02-data-models.md#migrationrecord)). When it is the last record, `update` skips the finished layers, walks the remaining layers to the recorded targets and refuses an explicit `--target-version` that differs from them ([04 §Safe Update](04-composition-engine.md#safe-update)). A layer whose own version did not move still ran under its ancestors' new versions in the paused walk, so only the record tells a finished layer from an unfinished one.

**Deferred, not rejected:** an opt-in `--via <version>` stepped walk, if a first-party migration is ever found that cannot be made jump-safe. That is a template-authoring failure with a tooling escape hatch, not the default model; building it before such a case exists would add a version-walking loop with no demonstrated need.

## Options considered

- **Rollback-on-conflict** — simpler (drops the conflict-pause path), but it throws away the merge attempt and hands the user nothing to resolve; it fights Copier's native model. Rejected.
- **A Boilerplate-owned backup directory with `update --continue` and `update --abort`** — rejected: the staging worktree leaves the checkout untouched until the walk ends, `git stash --include-untracked` sets a paused update aside and a rerun of `update` finishes it, so a second state machine adds nothing Copier and git lack ([ADR-001](adr-001-build-vs-adopt.md)).
- **Pause-with-markers (chosen)** — Copier-native, preserves work, costs the continuation slice.
- Removed layers: **auto-delete uniquely-owned files** (needs a per-layer file manifest in the lock; carries deletion risk) vs **migrations + safe-orphan (chosen)** — author-declared, no data-loss risk.

## Consequences

- The update CLI is `update`, rerun after a conflict (git/Copier idiom), with `--skip-answered` (Copier's name); `--dry-run` (preferred over Copier's `--pretend` where git and Copier idioms clash); `--prereleases` (Copier's name). Operationally-scoped flags may be set per-layer via an allowlisted params object; answers stay merged (the singular-template experience).
- Migrations are arbitrary code — fine for first-party templates (ADR-003), gated behind the trust model before untrusted templates run them.
- Authoring guidance (removed-layer cleanup migration, breaking-change migration) is owned by INT-009; `init-template` may scaffold a commented `_migrations` stub.

## Verification (2026-07-28)

Copier 9.15.0 on Windows, git 2.55. Fixtures: a single-template repo tagged v1/v2/v3, each tag changing a probe file whose content names its version, with version-gated `_migrations` entries whose commands append a JSON record of the migration id, stage, `VERSION_FROM`/`VERSION_TO`/`VERSION_CURRENT`, and the probe file's content as read at execution time — so the log proves which tree each migration saw. Two-layer variants added an overlay template overwriting a base-rendered file. An independent adversarial run repeated the two load-bearing claims with differently shaped fixtures and a marker distinguishing each tag's copy of a migration.

| Claim | Result |
|---|---|
| Jump v1→v3 runs every crossed migration exactly once | Confirmed — both fired, ascending, one update |
| Intermediate migrations see the target tree, not an intermediate one | Confirmed — `after`-stage probes read the v3 tree; `before`-stage probes read the pre-update tree; no v2 tree ever existed |
| The migration list is read only from the target version's config | Confirmed — a migration present only in v3's config still fired for a v1→v3 jump, and a stepped walk ran each tag's own copy |
| A step-wise walk runs each migration once against a true intermediate tree | Confirmed — and re-running an already-current update is a no-op |
| Migrations run despite unresolved merge conflicts | Confirmed — the `after`-stage migration read a file containing conflict markers; exit 0; the answers file advanced to the new tag |
| A migration can silently overwrite another layer's file | Confirmed — a base-layer migration replaced overlay-owned content, and the overlay's own later update neither detected nor repaired it |

Read from Copier's source rather than exercised: `_migrations` executes in declaration order rather than sorted by version; `--skip-tasks` does not gate migrations (also stated in Copier's own configuration docs); trust is demanded only when a version-gated migration falls inside the crossed range. Measured incidentally: an update crossing a migration without `--trust` exits 4 and applies nothing at all.

## Relationship to other ADRs

- [ADR-006](adr-006-template-distribution.md) — supplies the per-template git history that update diffs against.
- [ADR-015](adr-015-idiomatic-artifacts.md) — the per-layer walk this ADR's update model executes; its verification records the companion per-layer run, while the migration evidence is recorded in [§Verification](#verification-2026-07-28) above.
- [ADR-003](adr-003-permissive-execution.md) — migrations share the task/extension trust surface.
- [02-data-models.md](02-data-models.md) and [06-project-lifecycle.md](06-project-lifecycle.md) — own the conflict model this ADR states: the update `conflict` state exits 4.
