# ADR-012: Positioning relative to Copier

**Status**: Accepted

> **Scope note.** This is a documentation-framing decision, not an architecture one. It governs how public-facing docs (README first screen, docs home, the [Why Boilerplate?](../why.md) page) frame Boilerplate's relationship to Copier, and records the evidence that framing rests on. It does not change any behavioral contract.
>
> **Epistemic status.** Boilerplate has no public users yet. Nothing below is first-party data; it is public-signal research on adjacent ecosystems (issue trackers, adoption counts of proxy tools), and every conclusion drawn from it is an inference from proxies. Replace these inferences with first-party signals (issues, installs, feedback) as soon as any exist.

## Context

Boilerplate was extracted from an internal platform team's tooling and generalized for public release. Its public-facing story can be told two ways, and before this decision the repository told neither deliberately:

1. **The narrow pitch** — a composition engine for Copier templates (`extends`, merged questions, deterministic precedence). Concrete and verifiable, but it invites the immediate objection "Copier already documents applying multiple templates."
2. **The broad pitch** — an opinionated Python development system (curated toolchain, layered templates, planned lock/update lifecycle). Differentiated, but its value only fully demonstrates as the catalog and lifecycle features land.

Primary-source research (2026-07) resolved how to weigh these:

**Interest is documented, and upstream leaves it to the community.** Template composition/inheritance is Copier's longest-running unresolved feature request — 15+ distinct threads from 13+ authors, 2018–2025. The canonical thread, [copier-org/copier#934](https://github.com/copier-org/copier/issues/934) ("Updatable templates for template hierarchies and reuse", open since January 2023), sits in Copier's *Community contribution* milestone, whose own description is design-approved but not something the core team will build. Individual maintainer quotes need their context kept: yajo's "a different thing than copier" (2023) addressed a proposed fork/squash-merge update mode, and "with Copier, 1 template = 1 repo" a meta-template repo layout — neither is a blanket rejection of hierarchies, and yajo's first #934 response was a constructive meta-template prototype. The durable signal is the milestone itself. Copier's documented alternative, [applying multiple templates to one subproject](https://copier.readthedocs.io/en/stable/configuring/#applying-multiple-templates-to-the-same-subproject) with one answers file each, officially works only when templates touch **disjoint file sets**; merging shared files such as `pyproject.toml` across templates is the acknowledged unsolved gap ([discussion #1485](https://github.com/orgs/copier-org/discussions/1485), [issue #1738](https://github.com/copier-org/copier/issues/1738)).

**In the closest proxies, composition alone attracted few users; updatability attracted many.** The nearest prior art: [cookie-composer](https://github.com/callowayproject/cookie-composer) (declared multi-template layering for cookiecutter) drew ~21 stars and ~150 downloads/month over four years (as of 2026-07), while [cruft](https://github.com/cruft/cruft) — update-tracking only, same base ecosystem — has ~1,600 stars, and the highest-engagement thread in the space is cookiecutter's update request ([cookiecutter#784](https://github.com/cookiecutter/cookiecutter/issues/784), 43 reactions). This gap is suggestive, not conclusive — the tools differ in timing, marketing, and audience. Consistent with it: #934's own title asks for *updatable* hierarchies, and the users who articulate composition pain are platform teams whose stated motive is maintenance scaling, not initial scaffolding.

**Positioning norms among comparable tools are consistent.** Across uv, ruff, pnpm, pixi, biome, polars, and hatch: every tool that answers "why not X?" does so on the first screen or behind a first-screen link; none buries it; none uses an in-README feature table. The *form* splits by relationship — replacement tools (uv, ruff) lead with benchmarks and parity claims; tools built **on** an incumbent's ecosystem (pixi on conda; hatch on packaging standards) frame the incumbent as foundation, never attack, link outward to its docs, and defer extended comparison to a prose docs page.

**Honest caveats.** Per-thread engagement on composition asks is modest (single-digit reactions); Stack Overflow traffic on the topic is near zero; the one purpose-built predecessor flopped. The addressable market is thin and concentrated in platform teams. Separately, two competitive risks exist: upstream movement on #934 (a maintainer has sketched a "fork-like approach"), and uv absorbing scaffolding scope from below.

## Decision

Position Boilerplate as **the composition layer for Copier — foundation framing, not replacement framing** (the pixi/hatch pattern):

- **Name Copier in the first paragraph as the foundation.** State the gap in one sentence: Copier applies multiple *independent* templates by hand; Boilerplate lets template authors *declare* composition, giving consumers one command, one merged question set, and deterministic precedence when layers overlap.
- **Cite the documented gap, respectfully.** The README and the [Why Boilerplate?](../why.md) page may link Copier's own multi-template documentation and #934 — engaging prior art head-on, in the incumbent-as-foundation tone. No benchmarks, no feature-table combat.
- **Scope the compatibility claim to what ships.** Current-state docs say: templates remain standard Copier templates; composition metadata lives in a separate `boilerplate.yml`; `copier.yml` is never modified; a template becomes a layer by adding that one file. The stronger claim — vanilla Copier templates consumable with no added metadata — is not current behavior (the catalog requires `boilerplate.yml`) and MUST NOT appear in current-state docs unless that changes.
- **Split the two pitches by surface.** The README (arriving Copier-ecosystem audience) leads with the narrow, verifiable composition pitch; the docs home keeps the broad opinionated-system pitch and brand voice. Extended "why not plain Copier?" prose lives on the [Why Boilerplate?](../why.md) docs page, not in the README.

## Options considered

- **Foundation framing, first-screen gap statement (chosen)** — matches the norm for built-on-incumbent tools, preempts the predictable "just use `-a`" objection with the upstream's own words, and costs one paragraph.
- **Replacement framing (uv/ruff pattern)** — rejected: Boilerplate has no speed or drop-in-parity story against Copier, and it *depends* on Copier; attack framing would be both false and self-undermining.
- **Not naming Copier at all** — rejected: six of seven comparable tools name the incumbent, and Boilerplate's entire early audience consists of Copier users who will raise the comparison themselves if the docs don't.
- **Leading everywhere with the broad system pitch** — rejected for the README (the concrete gap is what the arriving audience can verify today), retained for the docs home where the fuller story has room.

## Consequences

- The proxy evidence (cruft vs. cookie-composer; #934's title) suggests the lock/update workstream (roadmap Phase 3, [adr-007](adr-007-update-model.md)) may matter more for adoption than composition alone. Weigh this when prioritizing; treat it as a hypothesis to test against first-party signals, not a settled fact.
- At public debut, the most directly reachable audience that has already expressed interest is the [copier-org/copier#934](https://github.com/copier-org/copier/issues/934) thread; a respectful pointer there is low-cost outreach. Caveat: the *Community contribution* milestone invites contributions **into Copier**, not external tools — the comment may present Boilerplate as one experiment toward the ask, never as "the" invited answer.
- Watch items: activity on #934 (upstream building or blessing an approach would change the gap statement), and uv's scaffolding scope. If either materializes, revisit this ADR.
- The mis-install hazard from [adr-008](adr-008-distribution-name.md) (bare `pip install boilerplate` installs an unrelated same-niche package) remains a positioning liability at every surface that names the package; install docs continue to lead with the git-URL path.
