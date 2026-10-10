# ADR-010: Profiles are plain default-answer files

**Status**: Accepted

## Context

An organization generating projects from shared templates needs to point those projects at its own private package index and container registry. Both are template answers: a value the template asks for, which the organization wants pre-filled on every run.

Default answers are the right shape for this need, for three reasons:

1. **Public by default.** The public product resolves packages from PyPI and GHCR. A default answer overrides that resolution for one user without any template or installer assuming an authenticated organization feed.
2. **Two values, not an apparatus.** The need is two values (`package_index.simple_url`, `container.registry`). A typed model, a layered resolution chain, and a CLI command group are a deep apparatus around a shallow need.
3. **Answers, not an interface.** Exposing a typed model as an interface invites more maintenance than the values earn, and "pluggable org profile" suggests an extension point the product does not offer.

## Decision

**A profile is a plain file of default answers to template questions.** A per-user `profile.toml` at the config root supplies **default answers to template questions**, merged into Copier as *overridable pre-fills* (`load_profile(template)` → `ExecutionContext.profile` → Copier's `user_defaults=` channel, not the forced `data=` channel). Templates declare ordinary Copier questions (`project.package_index_url`, `streamlit.container_registry`) and read them as ordinary answers.

Grammar: two reserved tables, `[defaults]` (any template) and `[templates.<name>]` (one template, overrides `[defaults]`). Keys are open: they are template question names, validated by nothing. A missing file yields `{}`; a malformed file raises `ProfileError`. Templates validate values, not the loader: a profile value's validation belongs in the declaring template's own Copier question (`copier.yml`), never in `load_profile`.

**The interface contract (how it stays coherent as the catalog grows):**

- `[defaults] X` is **best-effort**: it fills question `X` only in templates that declare it, and silently no-ops elsewhere. This is by design, not a gap.
- **Consistency comes from a canonical shared-question vocabulary owned by base templates and propagated by `extends`.** Declare a cross-cutting question once in a base (e.g. `package_index_url` on `project`); every descendant inherits the exact name/type; `[defaults]` then reaches the whole subtree. Verified: a `[defaults]` value reaches `streamlit` because it inherits the question from `project` (inherited questions reach every render of a descendant through its scoped view — [ADR-015](adr-015-idiomatic-artifacts.md)).
- **No per-template mandatory variable set.** Forcing every template to declare a fixed set is overexposure and couples unrelated templates. Authors declare only the few first-class variation points they intend.
- **No `[templates.<base>]` cascade.** The loader keys on the *invoked* template name; use `[defaults]` for family-wide values, `[templates.<name>]` for one-template overrides. Cascading would couple the settings loader to composition resolution.
- **Scope boundary.** A profile covers *declared questions only* — the customizations a template chose to make first-class. Structure the template didn't ship is a **layer** (`extends`); anything unanticipated is **your own script** after generation. A profile is one of three taps, deliberately the least powerful; it is **not** "the customization interface." (See [ADR-011](adr-011-structured-overlay-merge.md) for the structured-content gap this leaves.)

**Two answer channels, kept distinct** (`ExecutionContext`):

- `profile` → Copier `user_defaults=` — pre-fills the prompt, **overridable** interactively, taken as-is under `--non-interactive`. This is what a *default* means.
- `context_data` → Copier `data=` — a **forced** answer (prompt skipped); also holds answers threaded between composition layers. Merging profile values into this channel would make them non-overridable.

**Org configuration lives outside the product.** An organization layers its private config *after* the canonical public installer via an org-owned script that writes two plain files: `uv.toml` (machine package resolution + keyring/artifacts-keyring) and `%APPDATA%\boilerplate\profile.toml` (generation defaults). An organization keeps its real setup in its own repository; the public repo documents the generic pattern (fictional `acme`) in [customization.md](../customization.md).

## Options considered

- **Typed Profile model with a resolver chain and a `config` command group** — rejected: adds typed-model weight, a CLI surface, and a resolution chain for two values that are just answers.
- **Profile via the forced `data=` channel** — rejected: makes defaults non-overridable (skips the interactive prompt); contradicts "pre-fill, overridable."
- **Mandatory per-template variables** — rejected: overexposure; impossible to anticipate every downstream need anyway.
- **Env-var / CLI override layers on the loader** — rejected: per-invocation overrides already exist (the interactive prompt over the pre-fills, and Copier's forced `data=` channel for scripted runs), so new layers would duplicate channels. The loader stays a plain function, never a source-pluggable resolver; an environment layer returns only if a concrete second configuration source appears.
- **Profile as default answers (chosen)** — a thin merge over Copier's native `user_defaults`; orchestrate-don't-reimplement ([ADR-001](adr-001-build-vs-adopt.md)).

## Consequences

- `boilerplate.settings` exports `Settings`, `ProfileError`, and `load_profile`; the loader lives in `settings/profile.py`.
- [ADR-009](adr-009-environment-provider-protocol.md)'s `package-index` provider kind extends the plain-file profile.
- A missing `profile.toml` legitimately yields `{}`, so the loader has no *declared profile that fails to load* state to guard against silently falling back to the public index. The publish-safety concern belongs where publishing happens: a generated project's publish step should fail closed when no explicit target is configured. Boilerplate core stamps values and holds no publish opinion.
- **Deferred** (each with its own trigger):
    - *Named default sets*: one file per set plus an active pointer, switched by a `config` command; every render announces the active set — the loud toggle is part of the design, not polish (a silently stale org/personal switch is the failure mode). Build when a user actually juggles contexts.
    - *Warn-on-unknown-key lint + per-template key discoverability* — the best-effort model's safety net. Build when the catalog is large enough for key collisions and typos to bite.
    - *Profile-declared user tasks*: a `tasks = [...]` list appended to the composition engine's existing `_tasks` accumulation, run last after all template tasks. Interim answer: your own script after `boilerplate new`. Build when someone demonstrably re-runs the same script after every generation.
    - *Shareable-set trust*: profiles are trusted only because they are user-local files. If sets ever become distributable, fetching needs SHA-pinned verification — the trust boundary changes the moment the file crosses a machine boundary. Until then, distribution is the org script's business.

## Relationship to other ADRs

- [ADR-001](adr-001-build-vs-adopt.md) — orchestrate, don't reimplement: the profile is a merge over Copier's own channel, adding only the `profile.toml` grammar.
- [ADR-009](adr-009-environment-provider-protocol.md) — its `package-index` provider kind extends the plain-file profile.
- [ADR-011](adr-011-structured-overlay-merge.md) — the structured-content customization gap that the profile (values only) does not close.
