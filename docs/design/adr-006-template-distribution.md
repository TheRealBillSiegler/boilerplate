# ADR-006: Git-backed template distribution — monorepo authoring, published per-template repos

**Status**: Accepted **Deciders**: Project team

> **Scope note.** This ADR **commits** the PROD-001 item `first_party_template_distribution` — the `update` spine depends on it. For what exists in code today, see [status.md](../status.md).

## Context

`boilerplate update` orchestrates `copier update`, which performs the three-way merge. Copier's update is **git-only**: it computes the merge base by diffing the template's old git ref against the new ref. Templates authored as subdirectories of the package have no per-template git history and no version tags, and a `pip install`-ed wheel carries no `.git` at all, so a layer rendered from the wheel cannot be updated by `copier update`.

[ADR-015](adr-015-idiomatic-artifacts.md) sharpens what a distribution channel has to satisfy: the per-layer answers file is the **distribution contract**. Whatever Copier records there as `_src_path` and `_commit` must stay resolvable by vanilla Copier, on any machine, indefinitely — that is what keeps every git-backed layer updatable, by `boilerplate update` and by the escape hatch, a hand-run vanilla `copier update -a .copier-answers.<layer>.yml` per layer with its ancestors' answers passed as data ([ADR-015](adr-015-idiomatic-artifacts.md#decision)). A channel that cannot be named in an answers file and re-resolved later is not a channel.

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
- **Extraction into bundles shipped inside the wheel** — rejected: the per-layer answers file is the distribution contract, and a per-user cache path recorded as `_src_path` does not resolve on any other machine. The bundle survives only as the deferred seed cache above, which is never the recorded source.

## Consequences

- A new build-pipeline responsibility: deterministic per-template extraction plus publishing, with tags kept in sync with each template's `boilerplate.yml` version — the release-pipeline half of that is INT-010 (see the [intentions register](../intentions/README.md)). Publishing the extracted repositories falls outside INT-010 as currently scoped: its `not_included` excludes template publishing and registry hosting, so no intention owns the canonical channel today. Either INT-010 widens or a new intention takes it; that ownership question is open, and this ADR does not settle it.
- First-party templates become ordinary remote `git` sources, which meets [ADR-003](adr-003-permissive-execution.md)'s own stated trigger for tightening: its permissive render posture is acceptable only while sources are **local** and deliberately chosen, and its rationale — that an unsafe render executes code the user already has on disk — does not hold for a template fetched over the network. Whether that trip-wire re-scopes (to third-party or otherwise untrusted provenance) or fires as written (consent gating lands with the git source) is an open question ADR-003 owns and must resolve before the git source ships. This ADR does not decide it.
- A default install needs network access on first use: first-party layers render from the published repositories, so scaffolding no longer works from the wheel alone. That interacts with the designed `--offline` semantics ([design 05](05-cli-reference.md)) — an offline run depends on an org-local clone or mirror already being present — and it is what the deferred seed cache would address.
- The create path carries the git dependency as well as `update`: a project is updatable only if what `new` and `compose` recorded is a resolvable git source.
- `update` dogfoods against the published repositories, or against local clones during development — Copier treats the two identically.
- Air-gapped *environment provisioning* is a separate, harder problem (proto/tools) owned by Environment Provisioning ([design 08](08-environment-provisioning.md)), not here.

## Relationship to other ADRs

- [ADR-001](adr-001-build-vs-adopt.md) — "orchestrate Copier"; this is how first-party templates become git-orchestratable.
- [ADR-003](adr-003-permissive-execution.md) — making first-party templates remote git sources meets ADR-003's own trigger for tightening the permissive render posture; whether that trip-wire re-scopes to untrusted provenance or fires as written is ADR-003's open question, to be resolved before the git source ships.
- [ADR-007](adr-007-update-model.md) — consumes the per-template git history this ADR ships.
- [ADR-015](adr-015-idiomatic-artifacts.md) — supplies the answers-file-as-contract invariant this decision is derived from.
