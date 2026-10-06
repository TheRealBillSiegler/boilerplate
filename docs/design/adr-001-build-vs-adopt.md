# ADR-001: Build vs. Adopt Analysis

**Status**: Accepted **Date**: 2026-03-19 (decision) · corrected 2026-06-09 **Deciders**: Project team **Amended**: 2026-07-02 — terminology "Environments pillar" / "Environments/proto pillar" → "Environment Provisioning" to match the [glossary](01-overview.md#glossary); no decision changed.

> **Scope note.** This ADR records the build-vs-adopt *decisions* and the supply-chain assessment. Some decisions describe **target** architecture not yet implemented — Environment Provisioning, lock files, and the trust model. For what is actually built today, see [Implementation status](../status.md). The Copier integration *mechanism* is recorded separately in [ADR-002](adr-002-copier-internals-shim.md).

## Context

Before implementing remaining Boilerplate features, we critically evaluated each responsibility against the modern tool landscape to determine what should be built first-party vs. delegated to existing state-of-the-art solutions. This ADR records the architectural decisions, supply chain assessments, and design doc gaps identified during the review.

## Guiding Principles

1. Prefer modern, proven third-party solutions. Build only what doesn't exist.
2. Enterprise-grade: evaluate supply chain risk of every dependency.
3. No shim-based tools in the stack. Every dependency must provide native Windows execution.
4. "Orchestrate, don't replace" — applied consistently across all pillars.

## Decision: Two-Pillar Orchestration Architecture

Boilerplate is an orchestration layer with two pillars:

| Pillar | Orchestrated Tool | Boilerplate Adds |
| ------ | ----------------- | ---------------- |
| **Templates** | Copier (rendering, answers, three-way merge) | Composition (`extends` DAG), lock files, catalog, trust model |
| **Environment Provisioning** | proto (tool installation, 800+ tools, cross-platform) | Profile composition (`extends`), `.boilerplate/environment.yml` (profile provenance), enterprise trust. Tool-level locking delegated to proto's `.protolock`. |

> **Implemented:** the **Templates** pillar (composition + local catalog + Copier render). **Planned (design-only):** **Environment Provisioning**, lock files, and the trust model — see [status.md](../status.md).

### Template Composition is the Core Differentiator

Composition gives "the experience of a singular template, built from many variants." This is Boilerplate's reason to exist. No other tool provides declarative template composition on top of Copier. Copier's own template inheritance ([Issue #934](https://github.com/copier-org/copier/issues/934)) has been open since Jan 2023 with no implementation.

### Environment Provisioning Orchestrates proto (planned)

[proto (moonrepo)](https://moonrepo.dev/proto) handles the hard part of environment management: installing 800+ tools across platforms via WASM plugins. The plan is for Boilerplate to use proto's native `.prototools` schema and add what proto lacks: profile composition, `.boilerplate/environment.yml` (profile provenance), and enterprise trust/validation, with tool-level version locking delegated to proto's `.protolock`, and proto invoked via subprocess behind a `ProtoWorker` interface. This pillar is **not yet implemented**.

### Implementation Language: Python

Python is the right choice because Boilerplate builds directly on Copier (a Python library) — Rust would force subprocess invocation, losing type safety, shared error handling, and direct use of Copier's `Template`/`Worker` objects. Performance is not a concern: operations are I/O-bound (YAML, files, git), not CPU-bound.

**Copier integration mechanism.** Boilerplate depends on Copier's *internal* `Template`/`Worker` classes (not its public API): it subclasses `Template` to present the merged question schema and hands that schema to Copier, at compose and at update, through a `Worker` subclass that holds the merged view in its fields. This coupling is deliberate and contained behind a single audited import shim — see [ADR-002](adr-002-copier-internals-shim.md) for the mechanism, rationale, and version pin. (An earlier design proposed a file-based merged-template approach to avoid the internal dependency; it was evaluated and not adopted.)

## Supply Chain Decisions

*Last assessed: 2026-03-20. These ratings should be re-assessed periodically (at least quarterly or when a dependency releases a major version).*

| Dependency | Risk | Decision | Last Assessed |
| ---------- | ---- | -------- | ------------- |
| Copier | MEDIUM | Accept — internal `Template`/`Worker` used via the audited shim in [ADR-002](adr-002-copier-internals-shim.md). Mature project, active development, BSD-3 license. See [copier-org/copier](https://github.com/copier-org/copier); check [scorecard.dev](https://scorecard.dev) for current OpenSSF score. | 2026-03-20 |
| proto | MEDIUM | Accept (planned) — to be abstracted via a `ProtoWorker` interface. Younger project from [moonrepo](https://github.com/moonrepo/proto), active development, MIT license. Note: the `unstable-lockfile` feature flag signals `.protolock` is not yet stabilized — monitor for breaking changes. | 2026-03-20 |
| uv | LOW | Python toolchain foundation (no shims). Check [scorecard.dev](https://scorecard.dev) for current OpenSSF score. | 2026-03-20 |
| Typer | MEDIUM-LOW | Accept — wraps Click (Pallets); fallback straightforward. | 2026-03-20 |
| packaging | LOW | Accept — PyPA, no alternative for PEP 440. Declared as a direct dependency. | 2026-06-09 |
| logging (stdlib) | NONE | Chosen — logging via the stdlib `logging` module (Rich console on TTY, plain formatter otherwise). `structlog` was evaluated but **not adopted**; there is no third-party logging dependency. | 2026-06-09 |
| graphlib | NONE | Python stdlib | 2026-03-20 |
| deepmerge | HIGH | **Rejected** — inactive maintenance; merge strategies built inline (`composition/merging/`). | 2026-03-20 |
| mise | HIGH | **Rejected** — shim-based on Windows (violates the no-shims principle). | 2026-03-20 |
| oras-py | HIGH | **Deferred** (remote distribution) — immature Python SDK. | 2026-03-20 |

Zero shim-based dependencies in the final stack.

### proto Plugin Trust (planned)

proto's value is its 800+ tool plugins, but each plugin is third-party WASM code. When Environment Provisioning is built, Boilerplate SHOULD mitigate this by:

1. Maintaining an allowlist of vetted plugins in the environment profile schema.
2. Evaluating plugin signature verification when proto supports it.
3. Documenting the trust boundary: Boilerplate trusts proto; proto trusts its plugin authors; the user trusts the profile author's plugin selections.

This is an accepted residual risk for the (planned) environment subsystem, documented so it is not forgotten.

## Design Doc Gaps Identified

| Severity | Count | Key Issues |
| -------- | ----- | ---------- |
| Critical | 1 | Windows path handling unspecified |
| High | 3 | Copier API stability, `build_merged_template` filesystem tension, update with changed `extends` chain |
| Medium | 6 | Concurrency, submodule failure, copier-only template UX, keyword relevance, private repo auth, log format |
| Low | 5 | `--set-json` flag table (--set-json was subsequently cut), `--format` spec, undocumented alias, retry params, perf targets |

These gaps were tracked into the design docs at the time of the review.

## Consequences

- Environment management will orchestrate proto rather than building first-party tool resolvers (planned).
- Merge strategies are built inline rather than depending on `deepmerge`.
- Remote (OCI) template distribution is deferred; local filesystem sources are used today (Git sources are stubbed, not yet supported).
- A first-party trust model is planned — required by Phase 4 entry, per [ADR-003](adr-003-permissive-execution.md) — but not yet implemented; OCI signatures deferred until remote distribution lands.

## Sources

- [Copier Template Inheritance — Issue #934](https://github.com/copier-org/copier/issues/934)
- [proto (moonrepo)](https://moonrepo.dev/proto)
- [uv (Astral)](https://docs.astral.sh/uv/)
- [Copier Comparisons](https://copier.readthedocs.io/en/stable/comparisons/)
- [deepmerge health (Snyk)](https://snyk.io/advisor/python/deepmerge)
- [ORAS — OCI Registry As Storage (CNCF)](https://www.cncf.io/projects/oras/)
- [OpenSSF Scorecard](https://scorecard.dev/)
