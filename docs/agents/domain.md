# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, if it exists — the project's domain glossary.
- **`docs/design/`** — this repo's ADRs live here, named `adr-NNN-*.md` (e.g. `adr-001-build-vs-adopt.md`). Read the ADRs that touch the area you're about to work in.

If any of these don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. They are created lazily when terms or decisions actually get resolved.

> **`docs/design/` is target-state vision, not a contract.** Alongside the ADRs, `docs/design/` holds design docs (`01-overview.md` … `10-security.md`) that describe the *intended* application — a PRD-style target, not a re-implementation spec. Code may lag them. Don't treat a gap between code and these docs as a defect, and don't audit them for release scope.
>
> The converse also holds: every doc **outside** `docs/design/`, `docs/intentions/`, and `docs/products/` describes the *current* state of the shipped tree. Unbuilt features appear there only when explicitly marked as planned (as in `docs/status.md` and the README's Planned section).

## File structure

Single-context repo:

```text
/
├── CONTEXT.md            ← domain glossary
├── docs/design/
│   ├── adr-001-build-vs-adopt.md
│   ├── adr-002-copier-internals-shim.md
│   └── …                 ← plus target-state design docs 01-overview … 10-security
└── src/
```

## Use the glossary's vocabulary

When your output names a domain concept (an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it).

`CONTEXT.md` groups concepts in modules (`core`, `model`, `composition`, `customization`, `provisioning`, `trust`). Each entry has an identifier, `module:Name`, and the same labeled lines: **Kind of**, **Part of**, **Related**, **Not to be confused with**, **Stored in**, **Defined in**, **See**, **Avoid**, **Carve-out**, **Matches**. Check **Not to be confused with** before you use a term, add a new term in that shape, and keep the old anchor when you rename one. [ADR-016](../design/adr-016-project-vocabulary.md) records the format.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-001 (build vs adopt) — but worth reopening because…_
