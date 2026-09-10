# ADR-016: Generated architecture docs — deterministic facts, optional prose, one check on every pull request

**Status**: Proposed **Date**: 2026-09-10 **Deciders**: Project team

## Context

The docs site has no current-state view of the library. The Contributing page's architecture section points at the design specifications, which describe the target and by rule state no implementation status. The API reference renders each class and function from its docstring and shows nothing above module grain: which packages exist, which import which, or how a command moves through them.

A hand-drawn architecture figure describes one commit. Nothing ties the figure to the source lines it depicts, so a refactor leaves the figure wrong with no signal. Generated wikis such as DeepWiki show the alternative shape: an index of the code, pages written against that index with citations back to files, and a re-index that reruns the same procedure. A third-party wiki reads code and design docs together and cannot tell designed behavior from shipped behavior, cannot index a private repository, and re-indexes on its own schedule.

Three project constraints bound the design. Deterministic gates run free on every pull request and metered agents run on demand only. Required status checks are configured against the `gate` job alone, per the [CI pipeline](../governance/ci.md#the-gate) page. A contributor without access to a Claude subscription MUST be able to get a pull request green.

## Decision

Boilerplate's docs gain a generated section, `docs/architecture/`, produced by `scripts/architecture.py` from the source tree in two layers. The facts layer is deterministic and enforced on every pull request from the first day. The prose layer uses an LLM, runs on demand, and is reported but not enforced until one setting flips.

### Inputs

- The generator MUST read only `src/boilerplate/` (bundled templates included), `scripts/`, and `pyproject.toml`.
- The generator MUST NOT read `docs/design/`. Every generated page describes shipped behavior by construction, and the design specifications remain the only description of target state.
- Generated pages MUST NOT embed commit hashes or dates. Stamps hold content hashes only.

### Facts layer

The facts layer derives a facts file and three pages using the standard library alone.

| Output | Content | Derived from |
| --- | --- | --- |
| `docs/architecture/facts.json` | Packages, modules with their docstring summary lines, package-to-package import edges, exception classes with their bases, exit-code values, the error-to-exit mapping read from the except clauses of the error boundary decorator, and a SHA-256 over the canonical JSON | `ast` over `src/boilerplate/`, `pyproject.toml` |
| `index.md` | What the section is, the fixed sentence "Generated from the source at every refresh; the [design specifications](../design/README.md) describe the target", the refresh commands, and the list of pages present | the pages present |
| `packages.md` | Package inventory with module summaries, and a Mermaid flowchart of import edges between packages with any cycle named | `facts.json` |
| `errors.md` | A Mermaid class diagram of the exception hierarchy and a table mapping each error type to its exit code | `facts.json` |

- Two runs over the same source MUST produce byte-identical output: sorted keys, sorted edges, no timestamps.
- The generator MUST rewrite the nav entries for the section between the markers `# architecture:begin` and `# architecture:end` in `mkdocs.yml` from the pages present, so the strict build never references an absent page.

### Prose layer

The prose layer writes narrative pages and sequence diagrams from a prompt pack committed at `scripts/architecture/prompts/`, one prompt per page.

| Page | Content | Cites |
| --- | --- | --- |
| `overview.md` | What the library does end to end, the main components, one context diagram | `facts.json`, `src/boilerplate/` |
| `composition.md` | Resolve, merge, render, with a sequence diagram for `new` | `composition/`, `cli/commands/new.py` |
| `cli.md` | Command dispatch, the error boundary, the interactivity gate, and one sequence diagram each for `compose`, `graph`, `validate`, and `templates list` | `cli/` |
| `catalog-and-settings.md` | Template discovery and the search path, profile loading, settings | `repository/`, `catalog/`, `settings/` |

- Each prompt receives the facts file and reads the cited source itself. The writer runs headless through the Claude CLI with an explicit model and returns JSON: sections, Mermaid diagrams with captions, and citations of the form `{path, start_line, end_line, quote}`.
- The validator MUST reject a page when any citation names a path outside the allowed inputs, a line range outside the file, or a quote absent from those lines, and when any diagram fails a structural lint: unbalanced quotes, a reserved identifier such as `end` or `graph` as a node id, or a `style`, `click`, or HTML directive.
- A refuter pass at the balanced tier MUST read each claim against its cited lines and return accept or reject per claim. One rejected claim fails the page.
- A page that fails validation or refutation MUST NOT be written. The command exits non-zero and lists every rejected citation and claim.
- Each rendered page opens with an admonition stating that the page is generated and naming the refresh command, and closes with an HTML-comment stamp holding the facts hash and, for every cited file, its path and SHA-256.

### The check

`uv run python scripts/architecture.py check` runs on every pull request and in the local gate. It MUST NOT invoke an LLM and MUST NOT need network access.

- The check regenerates the facts layer into a temporary directory and compares it byte-for-byte with the committed files, including the nav block. Any difference fails the check.
- For each prose page the check parses the stamp, hashes every cited file as it stands in the working tree, and marks the page stale when any hash differs or the facts hash differs.
- The check prints each stale page with the changed files beneath it and the two commands that clear it.
- Whether a stale prose page fails the check is set by `prose_enforcement` in the `[tool.architecture]` table of `pyproject.toml`: `warn` exits zero after the report, `fail` exits non-zero. The initial value is `warn`.
- The check is one step in `scripts/check.py` and one job in the CI workflow that the `gate` job needs. It MUST NOT be configured as its own required status check.

### Refresh and attest

| Command | Effect |
| --- | --- |
| `refresh` | Regenerates the facts layer, then regenerates every stale prose page. Named pages limit the prose step to those pages; `--all` regenerates every prose page. |
| `refresh --facts` | Regenerates the facts layer only. |
| `attest PAGE...` | Rewrites the named pages' stamps to the current hashes and leaves the prose untouched. The diff shows a stamp-only change, which records that a person read the source change and judged the prose still accurate. |

- The facts step of `refresh` needs no external tool. The prose step fails fast with the install hint when the Claude CLI is absent, after the facts step has completed.
- The writer and refuter models are explicit in `[tool.architecture]` and overridable with `--model`.

### Procedure

The same commands run on the first day and on every later day.

| Day | Commands |
| --- | --- |
| First | `refresh --facts`, commit. When the prose layer is wanted: `refresh --all`, review the diff, commit. |
| Any later day | `check` names what is stale. `refresh` or `attest` clears it. |
| Each release | `refresh --all`, review the diff, commit. This step joins `RELEASING.md`. |

### Placement

- The section sits under Contribute in the nav as Architecture, with the index first, the facts pages next, and the prose pages after them when present.
- The Contributing page's architecture section links to the generated section for shipped structure and to the design specifications for target state.
- Hand-drawn figures remain only where the claim is about the reader's task on a reader page. Figures about how the library is built are generated.

### Testing

- Tests live under `tests/scripts/architecture/`, mirroring the script package.
- The walker and the renderer run against a fixture package with known imports, exceptions, and docstrings; syrupy snapshots pin the generated Markdown and the facts file.
- A determinism test runs the facts layer twice and asserts identical bytes.
- Validator tests cover a path outside the inputs, a line range past the end of a file, a missing quote, and each lint failure.
- Stamp, staleness, attest, and exit-code tests run with the Claude CLI call replaced by a stub returning canned JSON.
- The LLM writer and refuter are not under test.

## Options considered

- **Facts layer only** — rejected: no narrative, no sequence per command, no context view. A skeleton, and the request was a wiki.
- **LLM wiki only, or a third-party generated wiki** — rejected as the sole mechanism: tokens on every refresh, no run on a private repository, target state presented as shipped, and re-indexing outside the project's control. A third-party wiki remains a complement once the repository is public.
- **Build-time generation through `mkdocs-gen-files` and `mkdocs-literate-nav`** — rejected for now: two dependencies, and generated pages vanish from the diff. The marker block in `mkdocs.yml` is one function.
- **Prose enforcement at `fail` from the first day** — deferred: a contributor without the Claude CLI could not clear a stale page except by attest, and the prose layer has no track record yet. The setting flips when the maintainer judges the pages worth enforcing.
- **Mermaid parse validation inside the validator** — deferred: a real parse needs Node or a browser in the loop. The structural lint and the strict docs build stand in until then.

## Consequences

- Everything under `docs/architecture/` and the nav block between the markers is generated. A hand edit fails the check.
- Facts pages cannot rot. Prose pages can rot while enforcement is `warn`, and the check names them on every pull request.
- Attest is an honor system. The diff makes an attest visible as its own kind of change, and the release-time full refresh catches what an attest let through.
- The docs gain a current-state architecture section and the design specifications stay the sole owner of target state, per the single-owner rule in the [design README](README.md).
- The generator MAY later ship as template substrate, so a generated project gets the same section. That is future scope and nothing here depends on it.

## Relationship to other ADRs

- [ADR-001](adr-001-build-vs-adopt.md): the standard library walks the source and the Claude CLI writes the prose; nothing is reimplemented.
- [ADR-004](adr-004-exit-code-taxonomy.md): `errors.md` renders the taxonomy's error-to-exit mapping from the code that implements it.

## Verification

I read the rulesets, the CI workflow jobs, the local gate script, and the Contributing page against the repository on the date above. The description of DeepWiki rests on its public Copier page read the same day. No prototype of the walker, the validator, or the check has run.
