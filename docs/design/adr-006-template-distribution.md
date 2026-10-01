# ADR-006: Git-backed template distribution — monorepo authoring, published per-template repos

**Status**: Accepted (target architecture; not yet implemented) **Date**: 2026-06-20 **Deciders**: Project team **Rewritten**: 2026-07-28 — the decision below supersedes the original wheel-bundled form; see [Superseded positions](#superseded-positions).

> **Scope note.** This ADR records a *target* decision. The distribution mechanism it describes is not yet built; for current state see [status.md](../status.md). It **commits** `first_party_template_distribution` (previously a PROD-001 `candidate_scope` item) — the `update` spine depends on it.

## Context

`boilerplate update` orchestrates `copier update`, which performs the three-way merge. Copier's update is **git-only**: it computes the merge base by diffing the template's old git ref against the new ref. First-party templates currently ship as *subdirectories of the package* (`src/boilerplate/templates/`), with no per-template git history and no version tags — and a `pip install`-ed wheel carries no `.git` at all. So as templates are distributed today, `copier update` cannot run for an installed user.

[ADR-015](adr-015-idiomatic-artifacts.md) sharpens what a distribution channel has to satisfy: the per-layer answers file is the **distribution contract**. Whatever Copier records there as `_src_path` and `_commit` must stay resolvable by vanilla Copier, on any machine, indefinitely — that is what keeps every git-backed layer independently updatable with no Boilerplate installed. *[Superseded 2026-09-30 in its "no Boilerplate installed" clause by the [ADR-015 Amendment (2026-09-30)](adr-015-idiomatic-artifacts.md#amendment-2026-09-30-the-update-walk-runs-through-the-merged-schema-a-layer-declares-only-what-it-owns-or-overrides): the escape hatch is a hand-run vanilla `copier update -a .copier-answers.<layer>.yml` per layer with the other layers' answers passed as data.]* A channel that cannot be named in an answers file and re-resolved later is not a channel.

## Decision

Templates are **authored in a monorepo** (templates as subdirectories — good authoring DX, atomic cross-template changes). At **release time** each template is **deterministically extracted** (`git subtree split`) into its own git repository carrying full history and `vX.Y.Z` tags. Those repositories are **published, and they are the canonical first-party distribution channel.**

- **What gets recorded.** `new` and `compose` render first-party layers from the published repository, so the answers file records the published URL as `_src_path` and a real tag as `_commit`, and the lock records the same. Nothing a user's project points at is machine-local.
- **Versioning.** Per-template tags (`vX.Y.Z`). The Template Specifier `name@version` maps to "the `name` repo at tag `vX.Y.Z`", and Copier's `--vcs-ref` is an honest passthrough. One repository per template gives each template its own version stream natively, with no mapping layer.
- **A repository is a release train.** Templates share a version stream only when they genuinely release together — one repository carries exactly one PEP 440 tag series, and Copier resolves "latest" from it.
- **The wheel bundle is deferred.** Shipping bundles inside the wheel and cloning them to a per-user cache remains available as an *offline seed cache*, built only on demonstrated demand. A cache path **MUST NEVER** be recorded as `_src_path`: Copier records the source it actually used, and masking a local path behind a canonical URL would mean rewriting Copier's answers file, which [ADR-015](adr-015-idiomatic-artifacts.md) forbids. Until such a cache exists, the offline and air-gapped story is org-local clones or mirrors of the published repositories — pure Copier mechanics, portable inside the org, with rehoming a one-line `_src_path` edit.
- **Third-party parity.** A single-template repository is Copier's mainstream idiom, so third-party authors get first-party treatment by doing the ordinary thing. Monorepo authoring plus extraction is tooling we may share later, never a convention anyone must adopt to be a first-class template.
- **Reproducibility invariant.** The extraction is deterministic over un-rewritten history: same source commit → same extracted SHA across builds, so a lock's and an answers file's recorded `commit` keeps resolving against the published repositories. Published repository history is therefore **append-only** — never force-pushed, never re-created — because users' answers files and locks record commit SHAs from it, and a re-extraction that produced different SHAs would orphan every recorded commit.

**URL durability is a cutover coupling.** Published repository names are recorded permanently in user projects, so their naming rides the public-cutover naming decision and must be settled before the first release that records them.

**Sequencing.** The build-pipeline responsibility is deterministic extraction plus publishing; the per-user cache leaves the critical path entirely. One consequence is *open*, not settled: because a project is only updatable if its answers files name a resolvable git source, un-stubbing the git source became a prerequisite of the updatable-project outcome rather than a catalog-federation nicety. The [roadmap](../roadmap.md) owns that sequencing question.

## Options considered

- **Shared bundle or monorepo served directly to Copier** (one repository, templates as subdirectories via `_subdirectory:`, simplest build) — rejected on two independent grounds. Copier reads `_subdirectory` from the repository's *root* config, so serving several templates from one repository requires a root `copier.yml` with a dynamic `_subdirectory` and every template's questions `when:`-gated in that one file; per-template question schemas stop being self-contained artifacts. And one repository carries exactly one PEP 440 tag series, so independently versioned templates either release in lockstep — exporting spurious version bumps to downstream `extends` constraints — or become invisible to Copier's version resolution.
- **Published per-template repositories (chosen)** — clean Copier semantics (one template, one repository, plain tags, no `_subdirectory:`), forkable artifacts, per-template version streams, at the cost of build-time extraction and a determinism discipline: don't rewrite history, pin the split tool.
- **Authoring in separate repositories from the start, federated by submodules** — dominates on artifact realness but makes a coupled cross-template change three commits, adds contributor friction at debut, and turns a pinned set back into lockstep by another name. Deferred as an organization convention, not the first-party mechanism.
- **Extraction into bundles shipped inside the wheel** (the original decision here) — rejected once the answers file became the distribution contract; see [Superseded positions](#superseded-positions).

## Consequences

- A new build-pipeline responsibility: deterministic per-template extraction plus publishing, with tags kept in sync with each template's `boilerplate.yml` version — the release-pipeline half of that is INT-010 (see the [intentions register](../intentions/README.md)). Publishing the extracted repositories falls outside INT-010 as currently scoped: its `not_included` excludes template publishing and registry hosting, so no intention owns the canonical channel today. Either INT-010 widens or a new intention takes it; that ownership question is open, and this ADR does not settle it.
- First-party templates become ordinary remote `git` sources, which meets [ADR-003](adr-003-permissive-execution.md)'s own stated trigger for tightening: its permissive render posture is acceptable only while sources are **local** and deliberately chosen, and its rationale — that an unsafe render executes code the user already has on disk — does not hold for a template fetched over the network. Whether that trip-wire re-scopes (to third-party or otherwise untrusted provenance) or fires as written (consent gating lands with the git source) is an open question ADR-003 owns and must resolve before the git source ships. This ADR does not decide it.
- A default install needs network access on first use: first-party layers render from the published repositories, so scaffolding no longer works from the wheel alone. That interacts with the designed `--offline` semantics ([design 05](05-cli-reference.md)) — an offline run depends on an org-local clone or mirror already being present — and it is what the deferred seed cache would address.
- `update` dogfoods against the published repositories, or against local clones during development — Copier treats the two identically.
- Air-gapped *environment provisioning* is a separate, harder problem (proto/tools) owned by Environment Provisioning ([design 08](08-environment-provisioning.md)), not here.

## Relationship to other ADRs

- [ADR-001](adr-001-build-vs-adopt.md) — "orchestrate Copier"; this is how first-party templates become git-orchestratable.
- [ADR-003](adr-003-permissive-execution.md) — making first-party templates remote git sources meets ADR-003's own trigger for tightening the permissive render posture; whether that trip-wire re-scopes to untrusted provenance or fires as written is ADR-003's open question, to be resolved before the git source ships.
- [ADR-007](adr-007-update-model.md) — consumes the per-template git history this ADR ships.
- [ADR-015](adr-015-idiomatic-artifacts.md) — supplies the answers-file-as-contract invariant this decision is derived from.

## Superseded positions

The original decision (2026-06-20) reached the same authoring and extraction model but stopped one step short: it treated the extracted repositories as an intermediate artifact to be packaged, not published. What changed, and why:

- **The wheel-shipped bundle was the canonical consumable form.** Falsified by [ADR-015](adr-015-idiomatic-artifacts.md): the per-layer answers file is the distribution contract, and a per-user cache path recorded as `_src_path` does not resolve on any other machine. The bundle survives only as a deferred seed cache that must never be the recorded source.
- **"No per-template repos are pushed to remotes"; scaffolding and update work offline from the wheel.** Reversed — the repositories are published, and offline use is served by org-local clones or mirrors of them.
- **Bundle packaging plus a per-user cache subsystem were a hard prerequisite** said to block lock provenance and `update`. Both are off the critical path; the prerequisite is publishing.
- **Live remote git was deferred to Phase 4** as a different-provenance alternative to the bundle, with a project choosing monorepo-vs-bundle at `new` time. Remote git *is* the first-party path now, and the two no longer compete.
- **Remote sources were said to remain stubbed** in the relationship to [ADR-001](adr-001-build-vs-adopt.md). Reversed — the remote git source is the first-party path, so un-stubbing it is a prerequisite of first-party distribution rather than a later source kind.
- **The lock / verify / adopt path was said to be unaffected**, with the git dependency isolated to `update`. Reversed — a project is updatable only if what `new` and `compose` recorded is a resolvable git source, so the recorded source, and therefore the create path that writes it, carries the dependency too.
- **Non-git layers were said to still update**, with Copier's three-way merge degrading to two-way comparison and a warning. Falsified empirically ([ADR-015 §Verification](adr-015-idiomatic-artifacts.md#verification-2026-07-28)): Copier has no two-way fallback — such a layer refuses to update, and the walk skips it.
