# ADR-009: Environment provider protocol — proto is one provider, not the floor

**Status**: Accepted

**Date**: 2026-06-22 **Deciders**: Project team (Bill Siegler)

> **Scope note.** The *shape* recorded here — proto as one provider behind an abstraction — is load-bearing for how the pillar grows, and it reconciles a coherence gap (see Context).

## Context

Environment Provisioning is specified around **proto** as the toolchain installer ([08-environment-provisioning.md](08-environment-provisioning.md), [ADR-001](adr-001-build-vs-adopt.md)) — `ProtoWorker` is the only provisioning interface. Two pressures push against that single-tool shape:

1. **Proto-optional provisioning.** The bootstrap script (`install.ps1`) provisions tools via `winget`, not proto. A user who wants a winget-based toolchain with **no proto at all** has no first-class way to express it; with `ProtoWorker` as the only interface, proto is a floor, not a choice.
2. **A "custom command" escape hatch with a promotion path.** The desire to run an ad-hoc provisioning step and *later* "roll it up into something managed."

Both collide with the project's non-negotiable **Reproducibility is mandatory** ([01-overview.md §Core Principles](01-overview.md)) and the fail-closed trust model: an arbitrary command is non-deterministic, non-pinnable arbitrary code.

A design exploration (prior art: mise backends, asdf plugins, devcontainer Features vs lifecycle hooks, Copier `_tasks`, proto/Nix; plus adversarial verification against this repo's own principles) converged on the model below. `install.ps1` invoking `winget` is **user-run bootstrap** — the *user* invokes the package manager, not Boilerplate. The orchestrated provider protocol (Boilerplate invoking a gated installer) is the only path by which Boilerplate installs a package, and the Trust paragraph below gates it.

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
- **`package-index`** — folds the duplicated `uv.toml` fetch/verify/seed out of `install.ps1` / `setup-wsl-env.sh`. (Note overlap with the plain-file `profile.toml` loader of [ADR-010](adr-010-profile.md) — see Consequences.)

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
- **Capture as target (chosen) vs. keep the pillar thin in vision too** — a design review flagged Environment Provisioning as "a second product for users who don't exist yet." Capturing the protocol as *target* honors both that concern and "can't YAGNI a vision"; building it now was rejected as scope creep against the scripts-first decision.

## Consequences

- **Installation is gated.** Boilerplate installs a package only through an allowlisted, pinned provider, or through one the user consents to at the prompt, per the Trust paragraph above. The user-run `install.ps1` bootstrap invokes the package manager itself, so it sits outside this rule.
- **Design-doc changes this decision forces:** generalize `ProtoWorker` → Provider Protocol in [01](01-overview.md) and [08](08-environment-provisioning.md); admit first-party providers (`pinned-artifact`) in [ADR-001](adr-001-build-vs-adopt.md)'s pure-orchestrator framing; amend [02 §EnvironmentProvisionRecord](02-data-models.md) (`provider_states` is a resolution input, recorded-version-as-floor) and resolve the `tools`-map vs `provider_states` duplication (derive `tools`).
- **Naming hazards:** the plain-file `profile.toml` loader ([ADR-010](adr-010-profile.md), `settings/profile.py`) vs the `EnvironmentProfile` (`boilerplate-env.yml`) overload; "provider" also names catalog/template git-sources. The `package-index` kind overlaps the `profile.toml` loader — prefer *extending* that loader over reinventing it.
- **Build decomposition (target):** Unit 1 = Provider Protocol + `provider_states` + `pinned-artifact` (the proto-*less* tracer-bullet that proves the abstraction) → Unit 2a = proto refactored in + `system-package` + `package-index` → Unit 2b = active/named configs. Strictly sequential; 2a/2b depend on Unit 1's registry + schema. Substrate/`platform` becoming required on `boilerplate-env.yml` is a breaking change → major bump, spec the migration.

## Relationship to other ADRs

- [ADR-001](adr-001-build-vs-adopt.md) — "orchestrate, don't replace"; this widens Environment Provisioning to admit **first-party** providers (`pinned-artifact`) beside orchestrated ones (proto).
- [ADR-003](adr-003-permissive-execution.md) — the executable-bearing-provider trust gate shares the task/extension consent surface; full gating lands with the trust model.
- [ADR-005](adr-005-integrity-model.md) — signing stays deferred; local profiles inherit the filesystem-permission integrity posture.
