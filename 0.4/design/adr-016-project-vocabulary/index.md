# ADR-016: The project vocabulary as one ontology in CONTEXT.md

**Status**: Proposed

> **Scope note.** This ADR fixes how Boilerplate keeps its vocabulary: the names of its concepts, what each one means, how the concepts relate, and where each one lives in files and code. For what exists today, see [status.md](https://therealbillsiegler.github.io/boilerplate/0.4/status/index.md).

## Context

`CONTEXT.md` at the repository root is the domain glossary. The [design overview's glossary](https://therealbillsiegler.github.io/boilerplate/0.4/design/01-overview/#glossary) renders it, and `docs/agents/domain.md` tells the engineering skills to read it before they work in the code. Tenet 14 in `.claude/rules/docs.md` asks for one name per concept, and the glossary's *Avoid* lists name retired synonyms. The vocabulary still drifts in four ways.

- **Copies disagree.** The sweep found the glossary's dev loop entry, the Environment guide and the Quickstart each writing out a different sequence for the same everyday loop.
- **One word names unrelated concepts.**
  - "Profile" names `profile.toml`, a user's default answers, and `EnvironmentProfile` (`boilerplate-env.yml`), the tool versions a project pins. The glossary calls the two "unrelated despite the shared word".
  - "Layer" names a composition layer and, in the key `enforcement_layers` of PROD-001, an enforcement area.
  - "Stack" names the development tools in the brand line, templates building on one another on the home page, and an application's dependencies in the Streamlit template's dashboard.
  - "Workflow" names the general kind of a golden path in the glossary and the reference model, and a GitHub Actions workflow file in the CI guide (`docs/governance/ci.md`).
- **A concept and its file are split in two entries, merged in one, or missing a side.** The glossary separates `EnvironmentProvisionRecord` from `.boilerplate/environment.yml` and the Answers File from `.copier-answers.<layer>.yml`; it merges the lock with `boilerplate.lock` in one entry; it gives `boilerplate.yml` an entry with no template-metadata concept beside it; and it defines Profile by its file.
- **Relations are prose only.** A relation such as "the Toolchain is part of the Development Environment" exists as a sentence, so nothing shows the whole, and a relation to a renamed term goes unnoticed.

Boilerplate's data shapes already have a source of truth: hand-written Pydantic models, such as `BoilerplateLock` and `TemplateMeta` in `src/boilerplate/models/`, and AGENTS.md requires Pydantic at boundaries.

This repository's own history shows what written rules do and do not do ([Verification](#verification-2026-10-18)). A written rule is the specification every check here encodes: each automated check names the prose rule it enforces. A written rule with no check behind it did not reduce drift: the glossary's *Avoid* lists were followed by more uses of the names they retire. A checked rule held: the docstring-mood check has kept zero violations while the code grew. Whether written vocabulary also improves a coding agent's work is unmeasured; the published study of repository context files found no general gain in task success and a cost increase above 20%.

## Decision

**`CONTEXT.md` MUST be the project's one vocabulary document, organized as an ontology: concepts grouped in modules, each concept with one name, a namespaced identifier and a fixed set of labeled relation lines.** The document records each vocabulary decision once and is the specification later checks encode. Pydantic MUST stay the source of truth for data shapes.

1. **Modules.** The rendered part of `CONTEXT.md` has one section per module, in this order: `core` (concepts every module uses), `model` (the reference model), `composition`, `customization`, `provisioning` and `trust`. A concept moves to `core` only when a second module uses it.

1. **Entries.** Each entry opens with its `<a id="term-…">` anchor, its term in bold and its identifier, `module:Name`, then one or two sentences of definition, then these lines in this order, each left out when it does not apply:

   | Label                       | Holds                                                                     | Example                                            |
   | --------------------------- | ------------------------------------------------------------------------- | -------------------------------------------------- |
   | **Kind of**                 | The concept this one is a kind of                                         | `model:Workflow`, for the golden path              |
   | **Part of**                 | The concept this one is a part of                                         | `model:DevelopmentEnvironment`, for the toolchain  |
   | **Related**                 | Other concepts it works with                                              | `core:Template`, `composition:ScopedView`          |
   | **Not to be confused with** | A concept with a similar name and a different meaning, and the difference | `provisioning:EnvironmentProfile`, for Profile     |
   | **Stored in**               | The files that store the concept                                          | `profile.toml`                                     |
   | **Defined in**              | The source files that define or enforce it                                | `src/boilerplate/settings/profile.py`              |
   | **See**                     | The design section that owns its mechanics                                | design 04 §Scoped view                             |
   | **Avoid**                   | Retired names, as phrases                                                 | `org profile`, `config profile`                    |
   | **Carve-out**               | An allowed use of an avoided phrase                                       | "template skeleton" names `init-template`'s output |
   | **Matches**                 | An equivalent term in another vocabulary, its source, and exact or close  | paved road (Netflix, exact)                        |

1. **One concept, one name, one entry.** A term MUST be unique across all modules, compared without case, and MUST NOT appear in another entry's **Avoid** line. Two concepts that share a word each get their own term and entry, and each one's **Not to be confused with** line MUST name the other.

1. **A file is not a concept.** A file appears on the **Stored in** line of the concept it stores. A file gets its own entry only when its format is a concept in its own right.

1. **Data shapes stay in code.** An entry's **Defined in** line points at the Pydantic model or module that defines it; the entry does not restate the model's fields.

1. **Relations across modules.** The section "Rules across modules" holds only statements that span modules and that no labeled line states, such as the customization ladder Profile < Layer < Task.

1. **Drift is found by a sweep.** A read-only sweep compares the docs, the README and user-facing strings against `CONTEXT.md` and lists every synonym, conflicting copy and undefined term; the fixes land as ordinary pull requests. The sweep of 2026-10-18 found 161 findings, the baseline each later sweep's count is compared with.

1. **Automation follows evidence.** When a sweep finds drift of a kind an earlier sweep already fixed, the vocabulary moves to the form in [When the vocabulary is automated](#when-the-vocabulary-is-automated).

### Maintaining the vocabulary

- **Add a concept:** add an entry in its module with every label that applies, and link the pages that introduce the term to its anchor.
- **Rename a concept:** change the term and its anchor, keep the old anchor beside the new one so inbound links still resolve, move the old name into **Avoid**, and fix the prose the next sweep reports.
- **Split a word that means two things:** give each meaning its own term in its own module and point each one's **Not to be confused with** at the other.
- **Change behavior:** update the entry's definition and its **Defined in** line in the same pull request as the code.
- **Record a mistake:** when a contributor or an agent confuses two concepts, add or sharpen the **Not to be confused with** line on both.

### When the vocabulary is automated

The labeled lines of decision 2 are built to convert mechanically into this form, which is designed and not adopted:

- One concept file per concept, Markdown with YAML frontmatter, whose fields are the labels of decision 2.
- `CONTEXT.md` generated from the concept files, with a test that fails when the two differ.
- A pytest module that validates the frontmatter with a Pydantic model and fails on a duplicate id or term, a relation to a missing id, a cycle in **Kind of** or **Part of**, and a **Defined in** path, or a **Stored in** path under `src/` or `docs/`, that does not exist. A **Stored in** line may also name a file that lives in a generated project or the user's data directory, such as `profile.toml`, and the check skips those.
- Each domain model declaring its concept's identifier in `model_config["json_schema_extra"]["x-concept"]`, with a test that every declared identifier has an entry.
- A Vale vocabulary generated from the **Avoid** lines for the prose check, so the retired names have one source and an established tool applies them, with severities: error for a name that collides with another concept's term, warning for a softer preference.

## Options considered

- **One ontology in `CONTEXT.md`, found by sweeps (chosen).** One document is the only copy of each definition, the engineering skills keep reading the file they already read, the site keeps rendering it, and the labels give structure without new tooling.
- **One concept file per concept now** — deferred to automation. Without a generator, the concept files and `CONTEXT.md` hold two copies of every term and summary with nothing to keep them equal.
- **A SKOS concept scheme in Turtle as the source** — rejected as the source and kept as a possible export. SKOS fits the content: it models concepts as individuals rather than classes, and its hidden label matches **Avoid**. As the source it puts definitions in string literals that people and skills edit by hand and needs rdflib, pySHACL and a generator to produce the Markdown everyone reads, and SHACL Core cannot check **Kind of** for cycles without SHACL-SPARQL.
- **TBX (ISO 30042) as the source** — rejected as the source and kept as a possible export. TBX is the published standard closest to this entry model, a concept entry holding terms with preferred, admitted and deprecated status, and it is XML built for translation and exchange between termbases.
- **LinkML as the source** — rejected. LinkML describes data shapes, and many of Boilerplate's concepts (golden path, toolchain, curation) are not data shapes. Generating the domain models from LinkML makes two sources of the same shapes during the migration, and the models' hand-written validators would move into generator templates. Revisit if a data schema has to serve other languages as an equal, if RDF interoperability becomes a product feature, or if people who do not write Python need to own the model.
- **OWL** — rejected. OWL is open-world and makes no unique-name assumption, so a missing required value is not an error, and nothing in Boilerplate needs inference.
- **`CONTEXT.md` as it was** — rejected. Its *Avoid* lists retired names that prose then used more often, and relations it states only in sentences show no whole.

## Consequences

- The old Relationships list becomes "Rules across modules"; its other statements move onto labeled lines.
- Entries that name only a file fold into the concept they store, and their anchors stay beside the absorbing entry.
- `docs/agents/domain.md` tells the engineering skills that entries follow these labels. The skills themselves are the maintainer's plugins, outside this repository, and change there.
- Drift between sweeps is expected: nothing fails a build when prose uses a retired name.

## Open questions

1. **Placements.** Some concepts fit two modules, such as Guardrails in `model` or `trust`, and slot in `model` or as a term of the tool landscape. The maintainer confirms each placement the restructuring proposes.
1. **An admitted tier.** Terminology standards allow a tolerated synonym between the preferred term and a deprecated one. Whether **Avoid** needs that middle tier, for an abbreviation for example, is open.
1. **The enforcement area.** The **substrate** entry says "area" where PROD-001 says "layer". Whether "area" needs its own term, and what to do about the `enforcement_layers` key in PROD-001, which still carries the word, is open.

## Verification (2026-10-18)

I checked each external claim against its primary source on 2026-10-18. The repository facts in Context come from the files they name.

- **SKOS models concepts as individuals.** "the 'concepts' of a thesaurus or classification scheme are modeled as individuals in the SKOS data model … never as class or property axioms" ([SKOS Reference §1.1](https://www.w3.org/TR/skos-reference/)). skos:hiddenLabel is "A lexical label for a resource that should be hidden when generating visual displays of the resource, but should still be accessible to free text search operations" ([SKOS core RDF](https://www.w3.org/2004/02/skos/core.rdf)).
- **SHACL Core has no cycle check.** `sh:hasValue` compares value nodes with a fixed RDF term and not with the focus node, and SHACL-SPARQL adds SELECT-based constraints ([SHACL §4.8.2, §5](https://www.w3.org/TR/shacl/)). I infer the absence of a cycle constraint from the specification; no sentence in it states one.
- **OWL makes no unique-name assumption.** "OWL does not make the assumption that different names are names for different individuals" ([OWL 2 Primer](https://www.w3.org/TR/owl2-primer/)).
- **LinkML is closed-world and writes pattern validators only by itself.** "OWL is open-world, whereas LinkML is closed-world" ([LinkML OWL generator](https://linkml.io/linkml/generators/owl.html)); "Currently the only kind of slot-level validators that are created are for those slots that have a pattern property" ([LinkML Pydantic generator](https://linkml.io/linkml/generators/pydantic.html)).
- **Terminology standards separate preferred, admitted and deprecated terms.** ANSI/NISO Z39.19 links a non-preferred synonym to its preferred term (USE/UF) and separates whole-part from genus-species hierarchy (BT/NT); ISO 12620 lists preferred, admitted and deprecated term status. I read both through published summaries, not the standards' texts.
- **Vale reads vocabularies independently of its styles.** Vale feeds a vocabulary's rejected terms into `Vale.Avoid` ([Vale vocabularies](https://docs.vale.sh/keys/vocabularies)), and GitLab fails its docs CI on error-level Vale rules ([GitLab docs testing](https://docs.gitlab.com/development/documentation/testing/vale/)).
- **Context files have no measured general benefit.** Gloaguen et al. report that context files "do not generally improve task success rates" and raise inference cost by more than 20% ([arXiv 2602.11988](https://arxiv.org/abs/2602.11988)). The study tested overviews and tooling instructions, not glossaries.
- **This repository's history.** I measured rules at dated snapshots of the archive repository (2026-05-11 to 2026-09-04) and of `develop` (from 2026-09-04), and reran at least one number per rule.
  - Of 556 commits authored while the commit-message rules existed only in prose, 22 had a subject over 72 characters; of 667 authored once `scripts/commit_lint.py` existed, none did. A model new to the repository wrote most of the later commits, so the check is not the only cause.
  - The docstring-mood rule changed twice in prose, and neither change moved existing code; the count fell to zero when a sweep rewrote the code and the D401 check turned on, and it stayed at zero as public functions grew from 102 to 270.
  - After the *Avoid* lists were written, "template variable" rose from 14 to 16 uses in the docs and "overlay" for a layer from 0 to 8.
  - The limits: one project, no control group, gates record only what landed, and maintainer corrections made in conversation leave no trace in git.
