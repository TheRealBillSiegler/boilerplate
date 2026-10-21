# ADR-014: Deferred task execution — accumulate per layer, run once on the final layer

**Status**: Accepted

## Context

Copier's contract runs `_tasks` after generating a project, in the destination directory. Under composition, "the project" is the composed whole: layers render sequentially into one destination, and a layer's tasks (dependency installation, `git init`) generally assume the finished project, not that layer's partial contribution. Copier's own multi-template guidance — sequential independent applications — runs each template's tasks at its own apply time, against a project the later templates have not written yet. The closest prior art fails in the other direction: cookie-composer executes each layer's cookiecutter hooks inside a throwaway temp render, so environment side effects never reach the real project, and its documented mitigation is disabling hooks per layer.

## Decision

- **Merge**: `_tasks` accumulates across layers by ordered concatenation — topological order across layers (dependencies first, target last), declaration order within a layer, no deduplication. Tasks are effects; repetition and order are meaningful, so the append-only strategy is deliberate even though files use last-layer-wins.
- **Execution**: every non-final layer renders with `skip_tasks=True` (a public Copier flag); the final layer executes the full accumulated list exactly once, after all layers' files exist. Conditions are evaluated by the final layer's worker against the merged answers.
- **Update**: the update walk renders with `skip_tasks=True` in every render Copier makes during a layer's update (the old copy, the in-place render and the new copy), and the accumulated list runs exactly once against the finished project after the last layer's update, through the same `Worker` subclass under Copier's `update` operation, so a task's `when:` sees `_copier_operation == "update"` ([design 04 §Safe Update](https://therealbillsiegler.github.io/boilerplate/0.4/design/04-composition-engine/#safe-update)). Copier would otherwise run each updated layer's own `_tasks` three times per update, twice in temporary directories, and never the merged list.
- **Shapes**: task entries keep Copier's native forms end-to-end — plain string (shell execution), argv list (no shell), mapping with `command` and optional `when`/`working_directory` — so Copier, not Boilerplate, interprets execution semantics. Entries that match none of these shapes are dropped with a warning.

## Options considered

- **Per-layer execution (Copier-native timing)** — rejected: runs a base layer's tasks against an incomplete project (e.g. dependency installation against a `pyproject.toml` a later layer still overrides); the sequential-application precedent inherits exactly this flaw.
- **Deferred single execution (chosen)** — matches the pattern Yeoman institutionalized in its `composeWith` run loop (all composed generators' writing phases complete before any install/end phase runs) and preserves the object of Copier's contract: the completed project.

## Consequences

- A child layer cannot remove or reorder an inherited task; the idiomatic gate is a `when:` condition on the task, which shape pass-through preserves.
- Task provenance (which layer contributed an entry) is not yet carried through the merge. The trust-tier consent and audit design ([03 §Task Execution Safety](https://therealbillsiegler.github.io/boilerplate/0.4/design/03-template-system/#task-execution-safety), [Security model](https://therealbillsiegler.github.io/boilerplate/0.4/design/10-security/index.md)) requires per-layer attribution and selective execution; that needs a provenance-carrying merge and is deferred work this ADR explicitly does not cover.
- Mid-list failure leaves rendered files with partially applied post-processing — Copier's own no-rollback property, inherited unchanged. Task authors SHOULD keep tasks idempotent.
- `{{ _copier_conf.src_path }}` and `_copier_operation` inside task templates resolve against the final layer's worker, not the declaring layer's.

## Relationship to other ADRs

- [ADR-003](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-003-permissive-execution/index.md) governs the permissive `unsafe` trust posture the deferred execution runs under.
- [ADR-002](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-002-copier-internals-shim/index.md) localizes the `Template`/`Worker` coupling this mechanism drives; `skip_tasks` itself is public Copier API.
- [ADR-015](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-015-idiomatic-artifacts/index.md) — the update walk whose renders skip tasks; its [Verification (2026-10-06)](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-015-idiomatic-artifacts/#verification-2026-10-06) records where Copier runs a layer's tasks during an update.
