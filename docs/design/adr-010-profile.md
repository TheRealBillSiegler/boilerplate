# ADR-010: Profiles as plain default-answer files (retiring the typed Profile model)

**Status**: Accepted (implemented). Ships in the open-source release. Supersedes the built-`Profile` references in [ADR-009](adr-009-environment-provider-protocol.md) and the Profile/resolution/`config` sections of [09-settings-and-configuration.md](09-settings-and-configuration.md) and [05-cli-reference.md](05-cli-reference.md).

**Date**: 2026-07-01 **Deciders**: Project team (Bill Siegler)

## Context

The earlier design shipped a typed **Profile** customization model: `Profile`/`PackageIndex`/`Container` pydantic models (`settings/profile.py` — note: this filename is later reused for an unrelated module; see Consequences), a four-layer resolution chain (`settings/resolver.py`), a `boilerplate config` command group, a `_boilerplate` Copier context hook (`integrations/copier_context.py`), and a pre-profile migration hint. It existed to inject an organization's private package index and container registry into shipped templates, and it was coupled to a private-feed install path (an org wrapper script + the `-Profile` machinery in `install.ps1`).

Going public, that shape is wrong on three counts:

1. **Private-feed coupling.** The installer and the whole Profile stack assumed an authenticated org feed. The public product resolves from PyPI/GHCR by default.
2. **Heavyweight for what it does.** Profile was, functionally, two values (`package_index.simple_url`, `container.registry`) plus a resolution chain and a CLI surface — a deep apparatus around a shallow need.
3. **Mislabel.** "Pluggable org profile" exposed a typed model as an interface and invited more maintenance than it earned; the values are just template answers.

## Decision

**Retire the typed Profile model; keep "profile" as the plain-file concept.** A per-user `profile.toml` at the config root supplies **default answers to template questions**, merged into Copier as *overridable pre-fills* (`load_profile(template)` → `ExecutionContext.profile` → Copier's `user_defaults=` channel — **not** the forced `data=` channel). Templates declare ordinary Copier questions (`project.package_index_url`, `streamlit.container_registry`) instead of reading `_boilerplate.*`.

Grammar: two reserved tables — `[defaults]` (any template) and `[templates.<name>]` (one template, overrides `[defaults]`). Keys are open (template question names, validated by nothing). Missing file → `{}`; malformed → `ProfileError`. Values are validated by templates, not the loader: a profile value's validation belongs in the declaring template's own Copier question (`copier.yml`), never in `load_profile`.

**The interface contract (how it stays coherent as the catalog grows):**

- `[defaults] X` is **best-effort**: it fills question `X` only in templates that declare it, and silently no-ops elsewhere. This is by design, not a gap.
- **Consistency comes from a canonical shared-question vocabulary owned by base templates and propagated by `extends`.** Declare a cross-cutting question once in a base (e.g. `package_index_url` on `project`); every descendant inherits the exact name/type; `[defaults]` then reaches the whole subtree. Verified: a `[defaults]` value reaches `streamlit` because it inherits the question from `project` (inherited questions reach every render through the merged schema — [ADR-015](adr-015-idiomatic-artifacts.md)).
- **No per-template mandatory variable set.** Forcing every template to declare a fixed set is overexposure and couples unrelated templates. Authors declare only the few first-class variation points they intend.
- **No `[templates.<base>]` cascade.** The loader keys on the *invoked* template name; use `[defaults]` for family-wide values, `[templates.<name>]` for one-template overrides. Cascading would couple the settings loader to composition resolution.
- **Scope boundary.** A profile covers *declared questions only* — the customizations a template chose to make first-class. Structure the template didn't ship is a **layer** (`extends`); anything unanticipated is **your own script** after generation. A profile is one of three taps, deliberately the least powerful; it is **not** "the customization interface." (See [ADR-011](adr-011-structured-overlay-merge.md) for the structured-content gap this leaves.)

**Two answer channels, kept distinct** (`ExecutionContext`):

- `profile` → Copier `user_defaults=` — pre-fills the prompt, **overridable** interactively, taken as-is under `--non-interactive`. This is what a *default* means.
- `context_data` → Copier `data=` — a **forced** answer (prompt skipped); also carries answers threaded between composition layers. Merging profile values into this channel makes them non-overridable — the exact regression the final review caught.

**Org configuration is split out of the product.** An organization layers its private config *after* the canonical public installer via an org-owned script that writes two plain files: `uv.toml` (machine package resolution + keyring/artifacts-keyring) and `%APPDATA%\boilerplate\profile.toml` (generation defaults). An organization keeps its real setup in its own repository; the public repo documents the generic pattern (fictional `acme`) in [customization.md](../customization.md).

## Options considered

- **Keep Profile, de-couple the feed** — rejected: retains the typed-model weight, the `config` surface, and the resolver chain for two values that are just answers.
- **Profile via the forced `data=` channel** — rejected: makes defaults non-overridable (skips the interactive prompt); contradicts "pre-fill, overridable."
- **Mandatory per-template variables** — rejected: overexposure; impossible to anticipate every downstream need anyway.
- **Env-var / CLI override layers on the loader** — rejected: per-invocation overrides already exist (the interactive prompt over the pre-fills, and Copier's forced `data=` channel for scripted runs), so new layers would duplicate channels. The loader stays a plain function, never a source-pluggable resolver; an environment layer returns only if a concrete second configuration source appears.
- **Profile (chosen)** — a thin merge over Copier's native `user_defaults`; orchestrate-don't-reimplement ([ADR-001](adr-001-build-vs-adopt.md)).

## Consequences

- Deleted: the typed model's `settings/profile.py`, `settings/resolver.py`, `integrations/copier_context.py`, `cli/commands/config.py`, `cli/migration_hint.py`, and their tests. `boilerplate.settings` now exports `Settings`, `ProfileError`, `load_profile` — from a new, unrelated `settings/profile.py` module (the plain default-answers loader; the filename is reused, the code is not). **Breaking**: `boilerplate config` and the `profiles/`+`settings.toml` files are gone.
- [ADR-009](adr-009-environment-provider-protocol.md)'s `package-index` provider kind should extend the profile, not the retired Profile model; its "built Profile" naming hazard is resolved by this retirement.
- The retired resolver's fail-loud guard ("never silently fall back to the public index") protected one state — a *declared* profile that fails to load — which no longer exists: a missing `profile.toml` legitimately yields `{}`. The publish-safety concern relocated to where publishing happens: a generated project's publish step should fail closed when no explicit target is configured. Boilerplate core stamps values and holds no publish opinion. No first-party template ships a publish workflow yet, so nothing enforces this today — a gap to close when one does, not an oversight.
- **Deferred, not built** (each with its own trigger):
    - *Named default sets*: one file per set plus an active pointer, switched by a repurposed `config` command; every render announces the active set — the loud toggle is part of the design, not polish (a silently stale org/personal switch is the failure mode). Build when a user actually juggles contexts.
    - *Warn-on-unknown-key lint + per-template key discoverability* — the best-effort model's safety net. Build when the catalog is large enough for key collisions and typos to bite.
    - *Profile-declared user tasks*: a `tasks = [...]` list appended to the composition engine's existing `_tasks` accumulation, run last after all template tasks. Interim answer: your own script after `boilerplate new`. Build when someone demonstrably re-runs the same script after every generation.
    - *Shareable-set trust*: profiles are trusted only because they are user-local files. If sets ever become distributable, fetching needs SHA-pinned verification — the trust boundary changes the moment the file crosses a machine boundary. Until then, distribution is the org script's business.

## Relationship to other ADRs

- [ADR-001](adr-001-build-vs-adopt.md) — orchestrate, don't reimplement: the profile is a merge over Copier's own channel, adding only the `profile.toml` grammar.
- [ADR-009](adr-009-environment-provider-protocol.md) — superseded re: the built Profile.
- [ADR-011](adr-011-structured-overlay-merge.md) — the structured-content customization gap that the profile (values only) does not close.
