# Design Specifications

The canonical target architecture spec for Boilerplate. See [`01-overview.md`](01-overview.md) for the principles, glossary, and architecture overview.

This corpus describes the target only — no implementation status appears here. For what exists in code today, see [Implementation status](../status.md).

**Single-owner rule.** Every normative fact has exactly one owning document; other documents cross-reference it, never restate it.

The ancillary documents in this directory:

- [`adr-001-build-vs-adopt.md`](adr-001-build-vs-adopt.md) — build-vs-adopt: orchestrate Copier/proto rather than reimplement them.
- [`adr-002-copier-internals-shim.md`](adr-002-copier-internals-shim.md) — depend on Copier's private `Template`/`Worker` through one audited shim.
- [`adr-003-permissive-execution.md`](adr-003-permissive-execution.md) — renders with template tasks/extensions enabled (current posture, ahead of the trust model).
- [`adr-004-exit-code-taxonomy.md`](adr-004-exit-code-taxonomy.md) — six-value exit-code taxonomy with `BP*` codes for detail.
- [`adr-005-integrity-model.md`](adr-005-integrity-model.md) — integrity today: filesystem-permission-based for the lock file; cryptographic signing and a revocation list deferred.
- [`adr-006-template-distribution.md`](adr-006-template-distribution.md) — git-backed template distribution: monorepo authoring → release-time extraction into published per-template repos, whose URLs and tags the answers files and lock record (the wheel bundle is a deferred offline seed cache).
- [`adr-007-update-model.md`](adr-007-update-model.md) — safe update: conflict is a pause (exit 4 + `--continue`/`--abort`); structural change is migration-driven; updatability is per-layer.
- [`adr-008-distribution-name.md`](adr-008-distribution-name.md) — distribution name: PyPI `boilerplate` is taken by a same-niche tool; publish the dist as `boilerplate-cli`, keep `boilerplate` as the command/repo/brand (Pending — may become `boilerplate` if the name is acquired).
- [`adr-009-environment-provider-protocol.md`](adr-009-environment-provider-protocol.md) — target: generalize Environment Provisioning into a provider protocol (proto is one kind, optional); the shipped pillar stays thin (validate-and-warn + user-run bootstrap).
- [`adr-010-profile.md`](adr-010-profile.md) — profiles are plain default-answer files (`profile.toml` riding Copier's overridable `user_defaults=` channel); the typed Profile model is retired.
- [`adr-011-structured-overlay-merge.md`](adr-011-structured-overlay-merge.md) — proposed and deferred: deep-merge structured overlay fragments (`<file>.overlay.toml`) for downstream file customization; the 0.x releases ship without it.
- [`adr-012-positioning.md`](adr-012-positioning.md) — docs framing relative to Copier: foundation framing (pixi/hatch pattern), the public-signal evidence behind it, and its pre-launch, proxy-only epistemic status.
- [`adr-013-interactivity-contract.md`](adr-013-interactivity-contract.md) — stdin-TTY-gated prompting, fail-closed with named substitute flags, two-layer enforcement, no CI-env-var input-mode switching.
- [`adr-014-deferred-task-execution.md`](adr-014-deferred-task-execution.md) — `_tasks` accumulate across layers and run once on the final layer against the completed project, in Copier's native task shapes.
- [`adr-015-idiomatic-artifacts.md`](adr-015-idiomatic-artifacts.md) — idiomatic artifacts, orchestrated engine: a composed project is Copier on disk (per-layer answers files); compose and `boilerplate update` both run each layer through the merged schema, and a hand-run vanilla `copier update` per layer is the escape hatch.
- [`dev-environment-landscape.md`](dev-environment-landscape.md) — the reference taxonomy of development-environment **slots**, and the inner-loop slots Boilerplate fills with one opinionated pick each.
- [Intentions register](../intentions/README.md) — the tracked outcomes (INT-XXX) that design decisions and roadmap items cite by ID. The product definition those documents cite as PROD-001 (`enforcement_layers`, `shipped_gating_scaffolding`, `candidate_scope`) has no rendered page; it is the YAML source `docs/products/PROD-001.yaml`, linked from the register's "Source of truth" section.

## Conventions

- Every passage is either a **normative requirement** — it constrains observable behavior or a persisted artifact, stated as a testable MUST — or an **implementation note** explicitly marked non-normative ("a conforming implementation MAY…").
- Rationale prose survives only where it guards a correctness trap (e.g. PEP 440 pre-release ordering). Justification of arbitrary-but-fine choices was deliberately removed: a missing "why" is intentional — argumentation belongs in an ADR, not the spec body.
- Scope boundaries are negative requirements ("Reserved for Phase 4" = MUST NOT do now). They are load-bearing, not stubs.
- **An ADR states the current decision.** When the decision changes, the ADR is rewritten in place under the same number, and its history lives in git. An ADR carries no superseded markers, no amendment sections and no record of earlier positions.
- Rules were once labeled with `INV_*` identifiers; the labels were stripped (verified unreferenced in code, tests, and the PRD) and every rule survives in place as a plain MUST. Do not reintroduce an invariant-naming scheme; historical `INV_*` citations refer to rules that still exist. The §03 create-path lock rule and §06 update-path lock rule are deliberately separate requirements, not duplicates to merge.

This directory is served as part of the boilerplate documentation site (mkdocs) and is also the authoritative source for the implementer-facing spec — see [`01-overview.md`](01-overview.md).
