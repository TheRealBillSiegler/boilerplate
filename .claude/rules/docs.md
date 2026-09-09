---
paths:
  - "docs/**/*"
  - "mkdocs.yml"
---

# Docs golden-path tenets

At every zoom level — site map, section order, page, paragraph — the reader is on one designed route: they know where they are, what's next, and where depth lives when they want it. Every docs edit either strengthens that path or erodes it. Hold every docs diff against these tenets, and name the tenet number when reviewing or justifying an edit.

## The site — information architecture

1. **Sections are audiences on a journey** — arrive → evaluate → act → master → contribute. A page joins the section whose reader needs it; topic never overrides audience.
2. **Nav order is the curriculum.** The prev/next chain (in `mkdocs.yml` nav) is a designed route; a page may assume everything before it in its section and nothing after it.
3. **Every section orients at the door** — an index page saying what's here, who it's for, and where to start.

## The page — one question, progressively disclosed

4. **A page owns one question and answers it completely.** The answer starts on the first screen; depth unfolds below or behind links — never before the answer, and never omitted. A page that must be long to be complete is answering more than one question and should split.
5. **One mode per page.** Tutorial (linear lesson), guide (task), reference (lookup), or explanation (concept) — mixing modes mid-page is how layouts bleed together. Same-mode pages share the same shape; predictability lets the reader stop reading the layout and start reading the content.
6. **Waypoint, not destination.** Orient at the top, deliver the value, hand off at the bottom ("Where next") — no dead ends anywhere on the site.
7. **Teach by showing.** Lead with the working example and explain after; every example runs verbatim (test it); introduce one new concept at a time.

## The paragraph — texture and rhythm

8. **No brick walls, no monotony.** Alternate density — prose, code, table, whitespace are the rhythm section, and so are icons, buttons, cards, and tasteful emoji: engagement is a goal, not a suspect. A screen that looks the same from top to bottom gets restructured, not trimmed.
9. **Features are signals, not decoration.** A table for enumerable facts, a diagram for what prose can't say linearly, an admonition for a genuine aside. A visual accent earns its place by aiding scanning or marking a real category, and the accent language stays consistent site-wide — prefer Material icon shortcodes (`:material-*:`) over raw Unicode emoji, which render differently on every platform. If the reader loses nothing when it's prose, it's prose. An admonition in every section means none of them signal.
10. **Headings carry the story.** Scanning headings alone should tell what the page says; write them to match what a reader would search, not what sounds clever.

## The voice — how Boilerplate sounds

11. **Sound like the engineer who set up your environment, not the brochure.** Second person, active, present tense, every sentence about the tool or the reader's work, and no more words than the point needs: lead with the outcome, state the intention behind a pick, and hand anything enumerable, sequential, or structural to a list, table, or diagram (tenets 8 and 9). The exemplar is the ethos list in `docs/why.md`: each opinion names its concrete object and its override. Banned outside the brand register (tenet 13): marketing filler, "it's not X, it's Y" reversals, triadic adjective stacks, a named virtue standing in for the thing that shows it, and meta-commentary about the docs themselves — the tell is an agentless passive whose hidden agent is the author ("is stated as fact" describes the writing, not the tool).
12. **Opinionated in prose as in defaults.** State the pick with conviction and name the override in the same breath — a pick and an escape hatch, never a shrug. "It depends" is legal only when the next clause states the dependency.
13. **Brand carries itself; wit is rationed.** The brand register — "An ethos made executable", "Less yak. More stack.", "Start fast. Stay consistent. Reproduce anywhere." — travels freely as brand marks with no explanation required, and the home page is the slogan's anchor. Outside the register: at most one aphorism per page and none on reference pages (tenet 5); humor is dry, brief, and never at the reader's expense.
14. **One name per thing.** Boilerplate is the product, `boilerplate` is the command; a concept keeps one name site-wide — layer, slot, profile, template. Synonym-cycling for variety reads as new concepts and breaks the path.

## The ground — the path must be true

15. **Candor is load-bearing.** Shipped behavior stated as fact; designed behavior labeled as design; every claim verified against the code it describes, in the same sitting it is written; each fact owned by one page and linked from everywhere else. The three state-bearing pages keep their roles: docs/design/ describes the target (no status), docs/status.md maps what exists, docs/roadmap.md records sequencing. The origin narrative in why.md is fixed prose; do not extend or rephrase it.
16. **Durable and diff-friendly.** No issue/PR numbers or commit SHAs in prose (they die at renumbering); one logical line per paragraph or bullet — no hard wraps; dates only where they scope a verified snapshot (status.md) or trip a staleness wire (roadmap.md).
