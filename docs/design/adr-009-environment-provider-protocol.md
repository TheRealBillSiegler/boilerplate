# ADR-009: Environment provider protocol — proto is one provider, not the floor

**Status**: Accepted (target architecture; **not** current scope). The 0.x releases ship the thin pillar — `env apply` validates-and-warns and does not install ([08 §Behavior During `env apply`](08-environment-provisioning.md)), and the toolchain bootstrap is a **user-run** script (`install.ps1`). The provider protocol, proto orchestration, and gated provisioning below are target-state; the env-provisioning subsystem is 0% implemented today ([status.md](../status.md)) and proto integration is deferred.

**Date**: 2026-06-22 **Deciders**: Project team (Bill Siegler) **Amended**: 2026-07-02 — terminology "Environments pillar" → "Environment Provisioning" to match the [glossary](01-overview.md#glossary); no decision changed.

> **Supersession note (2026-07-16).** The typed Profile model and `config use`/`config show` surface referenced in this ADR were retired by [ADR-010](adr-010-profile.md); where this document says "the built Profile," read the plain-file `profile.toml` loader that replaced it.

> **Scope note.** This records a *target* decision. It does not change current behavior: nothing here is built yet, and the current environment story stays minimal (validate-and-warn + user-run bootstrap). The decision is captured now because the *shape* — proto as one provider behind an abstraction — is load-bearing for how the pillar eventually grows, and because it reconciles a live coherence gap (see Context). Per the project's "design docs are the target vision" stance, capturing the vision is in-scope even though the work is deferred.

## Context

Environment Provisioning is specified around **proto** as the toolchain installer ([08-environment-provisioning.md](08-environment-provisioning.md), [ADR-001](adr-001-build-vs-adopt.md)) — `ProtoWorker` is the only provisioning interface. Two pressures push against that single-tool shape:

1. **Proto-optional provisioning.** The real bootstrap today (`install.ps1`) provisions tools via `winget`, not proto. A user who wants a winget-based toolchain with **no proto at all** has no first-class way to express it; proto is currently a floor, not a choice.
2. **A "custom command" escape hatch with a promotion path.** The desire to run an ad-hoc provisioning step and *later* "roll it up into something managed."

Both collide with the project's non-negotiable **Reproducibility is mandatory** ([01-overview.md §Core Principles](01-overview.md)) and the fail-closed trust model: an arbitrary command is non-deterministic, non-pinnable arbitrary code. They also collide with a stated MUST: [08 §Behavior During `env apply`](08-environment-provisioning.md) — *"Boilerplate MUST NOT invoke package managers on the user's behalf"* (packages are advisory; the pillar validates-and-warns only).

A design exploration (prior art: mise backends, asdf plugins, devcontainer Features vs lifecycle hooks, Copier `_tasks`, proto/Nix; plus adversarial verification against this repo's own principles) converged on the model below. **Key reconciliation of that MUST:** the MUST governs the *orchestrated* `boilerplate env apply` flow. `install.ps1` invoking `winget` is **user-run bootstrap** — the *user* invokes the package manager, not Boilerplate — so the current release honors that MUST unchanged. Only the orchestrated provider protocol (Boilerplate invoking a gated installer) reverses it, and this ADR owns that reversal for target-state.

## Decision

**Generalize `ProtoWorker` into a Provider Protocol; proto becomes one *kind*, not the interface.** A profile MAY contain zero proto. The abstraction is a **closed set of declarative provider kinds** dispatched by a registry — explicitly **not** an open arbitrary-command runner (an open runner is the exact thing that voids reproducibility and the fail-closed trust model).

**Every provider kind implements three methods:**

- `provision(spec)` — **idempotent**; converges to the pinned target. Idempotency is a precondition because "re-run `env apply`" is the only recovery contract ([02 §EnvironmentProvisionRecord](02-data-models.md)). Absent → install; present and satisfies the pin → **adopt** (record provenance + observed version, no reinstall); present but violates the pin → **fail closed** (`BP_ENV_ADOPT_PIN_CONFLICT`).
- `verify(spec)` — integrity + an **exact-version** post-condition probe (presence-only `command -v` checks are insufficient). Shared typed return carrying an integrity-strength tier so `env status` renders all kinds uniformly.
- `resolved_state(spec)` — a deterministic pinned-state record.

**Initial kinds (closed enum):**

- **`proto`** — declarative versioned tools; keeps its WASM-sandbox trust posture and `.protolock`. Its `resolved_state` delegates to (hashes) `.protolock` — **no competing `env.lock`**, so "orchestrate, don't replace" holds ([02 §Environment Lock Strategy](02-data-models.md)).
- **`pinned-artifact`** — *the disciplined form of "custom command"*: a content-pinned fetch-verify-run (exact version + per-platform `https` URL + **mandatory** per-platform `sha256` + a version-assertion probe). Byte-reproducible. This is genuinely **first-party** (nothing external to orchestrate), which ADR-001's two-pillar-orchestration framing must admit alongside orchestrated providers. Free-form shell, unpinned fetch, `curl | sh`, and host-mutating `sudo` are **prohibited** in this kind.
- **`system-package`** — `winget` / `apt` / `brew`. This is *"make the existing advisory [`packages` / `PackageRequirement`](02-data-models.md) field (already carrying `source` + optional `version`) actually provision, gated,"* not a new concept. Optional `version`: absent → latest today; exact/range later (plural-shape, additive). Records the **resolved** version into the lock. **Best-effort tier** (see Reproducibility).
- **`package-index`** — folds the duplicated `uv.toml` fetch/verify/seed out of `install.ps1` / `setup-wsl-env.sh`. (Note overlap with the **already-built** `Profile` system — see Consequences.)

**Raw arbitrary shell is CUT from this decision.** Its *effect* cannot be locked (you can hash the command string, not its side effects). If ever added, it needs its own ADR **and** an explicit amendment to the "Reproducibility is mandatory" principle — not a smuggled `reproducible:false` carve-out.

**"Roll up into managed" = promote a *definition*, not a snapshot.** Scaffold-not-snapshot (operator supplies version + URL + per-platform sha256 + verify-probe; a past side-effect's content hash and upstream URL cannot be auto-recovered on a fresh host), **operator-performed**, **out-of-band** (never self-declared in the file that ships the step — self-promotion through composition is privilege escalation). Identity / lock-key stays stable across rungs (inline → catalog-named → registered); only the locator changes, so promotion is a registration, not a rewrite.

**Lock & reproducibility.** No separate `env.lock`; per-provider resolved state lands in the `provider_states` map of the `EnvironmentProvisionRecord` ([.boilerplate/environment.yml](01-overview.md)). Integrity tiers, surfaced honestly (never hidden behind a uniform interface):

| Tier | Providers | Guarantee |
|---|---|---|
| Checksum-locked | `proto` (.protolock), `pinned-artifact` (sha256) | same bytes across time |
| Version-pinned (best-effort) | `system-package` | same *declared version*; bytes are the package manager's word |

Recorded version is a **floor** honored on re-apply: declaration > recorded floor > latest. `env status` reports drift floor-vs-latest **without** silently re-pinning; a deliberate relock advances it. This promotes `provider_states` from a "state, not audit" projection to a **resolution input** — [02 §EnvironmentProvisionRecord](02-data-models.md) must be amended to say so. Unpinned-latest is allowed (the declaration says "latest"; `env apply` records the resolved version) — state plainly that this **extends** the principle's scope-note logic to the provider domain. **An *explicit* pin that cannot be satisfied fails closed** (`BP_ENV_*`, record not written) — silently installing something else would reduce determinism.

**Trust.** Control is **allowlist-as-ceiling + mandatory pins** (parallel to the existing `allowed_proto_plugins` ceiling, [08 §`allowed_proto_plugins` Enforcement](08-environment-provisioning.md)): allowlisted + pinned providers need no per-apply consent; ad-hoc / un-allowlisted inline entries prompt interactively and **refuse in CI** until promoted. The new gate **extends** the WASM-sandbox trust *exemption* at [08 §`allowed_proto_plugins` Enforcement](08-environment-provisioning.md) to non-WASM providers — `pinned-artifact` fetches an https URL and `system-package` shells out, so the sandbox rationale that justified the exemption evaporates the moment a profile uses a non-proto kind.

**Signing.** Local executable-bearing profiles → note + filesystem-permission expectation (the same ADR-005 posture as `boilerplate.lock`); signing stays deferred (a writable-FS attacker who can edit the profile can edit PATH/binaries directly, and local verification is only as strong as a trust root the attacker can't touch). Remote/third-party provenance → signing belongs in the **catalog trust model** ([03 §Trust](03-template-system.md), [10-security.md](10-security.md)), not here.

**Naming.** The OS-host axis is **`platform`** (`windows`/`wsl2`/`linux`/`macos`, the existing `packages` key) — **not** `substrate`, which is locked to the enforcement-mode meaning (`enforced`/`preconfigured`, PROD-001, [glossary](01-overview.md)).

## Options considered

- **Open arbitrary-command runner** — maximally flexible; rejected: voids reproducibility-mandatory and fail-closed trust. Convergent prior art (Copier `_tasks` default-deny, devcontainer Features-vs-hooks) draws the same managed-vs-escape-hatch line.
- **Closed declarative kind-set (chosen)** — every kind must implement `verify` with a real post-condition; a candidate that can't is, by construction, not a provider (the type-level test for escape-hatch abuse).
- **Separate Boilerplate `env.lock`** — rejected; duplicates `.protolock`, violates orchestrate-don't-replace. `provider_states` in the existing record instead.
- **Reuse the template trust gate as-is** — rejected; [08 §`allowed_proto_plugins` Enforcement](08-environment-provisioning.md) *exempts* profiles because proto runs in WASM. Non-proto providers have no sandbox, so the gate must be **extended**, not reused unchanged.
- **Capture as target (chosen) vs. keep the pillar thin in vision too** — a design review flagged Environment Provisioning as "a second product for users who don't exist yet." Capturing the protocol as *target* (while the shipped pillar stays thin) honors both that concern and "can't YAGNI a vision"; building it now was rejected as scope creep against the scripts-first decision.

## Consequences

- **Current behavior is unaffected.** Validate-and-warn + user-run `install.ps1` bootstrap; proto and this protocol are deferred. The MUST holds today; this ADR **supersedes** its *blanket* prohibition only in target-state — replacing "MUST NOT invoke" with "MUST NOT invoke **except** via an allowlisted, pinned, consented provider."
- **Amendments this forces when the pillar is built** (target docs, not current edits): generalize `ProtoWorker` → Provider Protocol in [01](01-overview.md) and [08](08-environment-provisioning.md); admit first-party providers (`pinned-artifact`) in [ADR-001](adr-001-build-vs-adopt.md)'s pure-orchestrator framing; amend [02 §EnvironmentProvisionRecord](02-data-models.md) (`provider_states` is a resolution input, recorded-version-as-floor) and resolve the `tools`-map vs `provider_states` duplication (derive `tools`); rewrite [08 §Behavior During `env apply`](08-environment-provisioning.md) for the gated-provision reversal.
- **Naming hazards to flag now:** the **built** `Profile` (org index/registry config — `settings/profile.py`, `config use/show`) vs the design-only `EnvironmentProfile` (`boilerplate-env.yml`) overload; "provider" also names catalog/template git-sources. The `package-index` kind overlaps the built `Profile` system — prefer *extending* that resolution chain over reinventing it.
- **Build decomposition (target):** Unit 1 = Provider Protocol + `provider_states` + `pinned-artifact` (the proto-*less* tracer-bullet that proves the abstraction) → Unit 2a = proto refactored in + `system-package` + `package-index` → Unit 2b = active/named configs. Strictly sequential; 2a/2b depend on Unit 1's registry + schema. Substrate/`platform` becoming required on `boilerplate-env.yml` is a breaking change → major bump, spec the migration.

## Relationship to other ADRs

- [ADR-001](adr-001-build-vs-adopt.md) — "orchestrate, don't replace"; this widens Environment Provisioning to admit **first-party** providers (`pinned-artifact`) beside orchestrated ones (proto).
- [ADR-003](adr-003-permissive-execution.md) — the executable-bearing-provider trust gate shares the task/extension consent surface; full gating lands with the trust model.
- [ADR-005](adr-005-integrity-model.md) — signing stays deferred; local profiles inherit the filesystem-permission integrity posture.
