---
paths:
  - "docs/**/*"
  - "mkdocs.yml"
---

# Docs golden-path tenets

At every zoom level — site map, section order, page, paragraph — the reader is on one designed route: they know where they are, what's next, and where depth lives when they want it. Every docs edit either strengthens that path or erodes it. Hold every docs diff against these tenets, and name the tenet number when reviewing or justifying an edit.

## The site — information architecture

1. **Sections are stages of one journey** — arrive → evaluate → act → master → contribute. A page joins the stage at which the reader needs it; the need at hand decides, never the topic and never a fixed reader label.
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
14. **One name per thing.** Boilerplate is the product, `boilerplate` is the command; a concept keeps one name site-wide — layer, slot, profile, template. Synonym-cycling for variety reads as new concepts and breaks the path. Use the term `CONTEXT.md` defines, and link its entry where a page introduces it; [ADR-016](../../docs/design/adr-016-project-vocabulary.md) (proposed) sets how the vocabulary is kept.

## The ground — the path must be true

15. **Candor is load-bearing.** Shipped behavior stated as fact; designed behavior labeled as design; every claim verified against the code it describes, in the same sitting it is written; each fact owned by one page and linked from everywhere else. The three state-bearing pages keep their roles: docs/design/ describes the target (no status), docs/status.md maps what exists, docs/roadmap.md records sequencing. The origin narrative in why.md is fixed prose; do not extend or rephrase it.
16. **Durable and diff-friendly.** No issue/PR numbers or commit SHAs in prose (they die at renumbering); one logical line per paragraph or bullet — no hard wraps; dates only where they scope a verified snapshot (status.md) or trip a staleness wire (roadmap.md).

## The whole — parts in relation

17. **Show how the parts connect.** Boilerplate's picks are chosen to work together, so a page that presents a part names what it connects to — the configuration it shares, the part that reads it, the step that depends on it — and an override names what it gives up. Show each connection through its concrete object (one `[tool.ruff]` table that both the editor and `uv run ruff` read) and link the page that owns it (tenet 15), never through a word for it: "synergy", "holistic", "seamless" and "compounding" are named virtues, banned under tenet 11.

## The diagram — one question at a glance

18. **A diagram answers one question at a glance.** Use one only where tenet 9 calls for one, and pick the type that matches the content's shape: a sequence diagram for handoffs between actors over time, a flowchart for steps and branches, a state diagram for a lifecycle. The sentence that introduces it states the question and its boundary. Keep the participants few (the bar has four) and name them in words the reader already uses, label every arrow with a short active verb phrase, and draw repetition and concurrency with the type's own constructs (`loop`, `par`, one back-edge) instead of copied arrows. A placeholder gets one concrete example, decoration that repeats information is off (on a sequence diagram, `mirrorActors: false` draws each participant once), and `accTitle` and `accDescr` say in words what the diagram shows. Judge the diagram as it renders on the docs site and on GitHub, not its source: Mermaid can reorder flowchart nodes that the source orders. The bar is the release diagram, which answers what happens from the first merge after a release to `main` moving to the new tag:

    ```mermaid
    %%{init: {"sequence": {"mirrorActors": false}}}%%
    sequenceDiagram
        accTitle: Release sequence
        accDescr: Pull requests merge into develop and gather in the release PR. The maintainer approves the release PR's CI and merges it, which tags and publishes the release. Then three jobs run at the same time: the docs deploy, the offline docs zip is attached, and main fast-forwards to the tag.
        actor M as Maintainer
        participant D as develop
        participant W as Release workflow
        participant G as GitHub
        loop for each PR, as many as needed
            M-)D: merge a PR
            D-)W: push
            W-)G: add it to the release PR
        end
        M-)G: approve the release PR's CI
        M-)D: merge the release PR
        D-)W: push
        W-)G: tag vX.Y.Z (e.g. v0.4.0), publish the release
        par at the same time
            W-)G: deploy vX.Y.Z's docs as version X.Y
        and
            W-)G: attach the offline docs zip
        and
            W-)G: fast-forward main to vX.Y.Z
        end
    ```
