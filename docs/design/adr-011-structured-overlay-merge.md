# ADR-011: Structured overlay-merge for downstream customization

**Status**: Proposed (**deferred; not in the open-source release**). Captured because the customization design work surfaced it as the real developer-experience capability for arbitrary structured-file customization; deferred — the 0.x releases ship without it — the three taps of [ADR-010](adr-010-profile.md) plus the post-generation script escape hatch stand as the release story.

**Deciders**: Project team (Bill Siegler)

> **Scope note.** This records a *target* decision and changes nothing in the release. It is written now so the gap and the chosen direction are on the record before someone reaches for the wrong tool (post-generation `tomlkit` surgery) as if it were the pattern.

## Context

[ADR-010](adr-010-profile.md) gives three customization taps: **values** (the profile), **structure** (layers via `extends`), and **behavior** (your own post-gen script). A real gap sits between them: a downstream that wants an *arbitrary structured edit* to a generated file — e.g. change `requires-python` mid-`pyproject.toml` **and** append a `[tool.acme.audit]` section — has only poor options today:

- **Profile** — only reaches *declared* questions; an arbitrary mid-file edit is not a declared slot.
- **Own the file** — the layer ships its own `pyproject.toml.jinja`, duplicating the base's whole file and drifting when the base changes. Brittle for "add one block."
- **Post-generation script** — edit the rendered file with `tomlkit` (Python stdlib can *read* TOML but cannot *write* it), guarded for idempotency. Clunky, hand-rolled per edit. Unacceptable as the *standing* answer for a developer-experience tool.

Copier renders each layer independently with **no merge primitive**, so "reach into the base's output and change it" always bottoms out in one of the above.

Key insight: for a structured file, **"edit in the middle" and "append a section" are the same operation** — the file is a tree, not lines. Both are "set these nodes," expressible declaratively.

## Decision (proposed)

**Extend the composition engine to deep-merge structured-content overlays.** A layer ships `<file>.overlay.{toml,yaml,json}`; after all layers render, the engine deep-merges each overlay into its target file on disk (then removes the overlay marker). Position-independent by construction — one fragment expresses both a mid-file edit and a new section:

```toml
# pyproject.overlay.toml — shipped by an org layer
[project]
requires-python = ">=3.12"     # overwrites that leaf, wherever it sits
[tool.acme.audit]             # adds a new table
endpoint = "https://audit.example/..."
```

Scoped to **structured formats only** (TOML/YAML/JSON). Free-text patching of unstructured files is explicitly **out** — that stays "own the file or script it." Fits the composition engine's mandate (it already merges questions and tasks across layers; this is the same idea applied to file bodies) and fills a gap Copier leaves, so it is build-not-reinvent per [ADR-001](adr-001-build-vs-adopt.md).

## Open questions to resolve before building

- **List / array-of-tables merge semantics** — append vs replace vs merge-by-key. This is where every merge system lives or dies (kustomize strategic-merge, Helm values). Proposed default: deep-merge, overlay wins on scalar conflict; offer JSON-Patch-style ops (RFC 6902: `replace /project/requires-python`, `add /tool/acme`) for surgical array targeting when deep-merge is ambiguous.
- **Comment/formatting preservation** — a re-serialize is best-effort; acceptable for a generated file (semantic correctness over textual layout).
- **Residual not covered** — *transforming an existing value as a function of its current content* (append to a string, conditional rewrite) cannot be a static overlay; that stays a post-generation script. Rare tail; does not merit machinery.

## Consequences

- Turns "edit the middle + append a section" from a hand-rolled `tomlkit` script into a three-line declarative fragment — the developer-experience bar this tool is held to.
- Adds a post-render merge pass and per-format mergers to the composition engine; the list-semantics decision above is the central design cost.
- No release impact: deferred. If a specific structured edit proves common across the catalog first, the cheaper interim move is to give the *base* template a typed list question for that slot ([ADR-010](adr-010-profile.md) Tier-1), not to rush this.

## Relationship to other ADRs

- [ADR-010](adr-010-profile.md) — the profile handles *values*; this handles *structured content* the template did not parameterize. Complementary taps.
- [ADR-001](adr-001-build-vs-adopt.md) — build-not-reinvent: Copier has no structured merge; this is first-party composition of file content.
