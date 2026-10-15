---
paths:
  - "README.md"
---

# README template and guide

`README.md` follows the template below and the guide after it. The README is the front door, written for someone who has never heard of the project; every fact beyond the front door lives on the page that owns it, and the README links there.

## Template

```markdown
<!--
README template. Curly-braced text is a placeholder; replace it, and delete these comments.
The README is the front door, written for someone who has never heard of the project. It owns what the project is, who it is for, why it matters, how to get it, how to start, and where to go next; every other fact lives on the page that owns it, and the README links there.
Each section answers the question the section before it raised. Budget: about 45 non-blank lines.
-->

# {Mark, if the project has one} {Project name}

{Live badges only, such as build status and license.}

**{Role line: what {Project name} is, in one sentence of nouns a newcomer already knows. The same sentence on every surface that says what it is.}** {Who it is for and what they do with it, marking optional uses as optional. If the role line uses a coined term, this sentence earns it with a plain example.} {What it builds on, glossed in a few words, and whether the reader needs to know it.}

{Mission: why {Project name} exists and what it does for you, in one or two sentences.}

{Curation, only if the project carries a set of choices: what it picks, how the picks were chosen, and the files that configure them, in one to three sentences. This is the one sentence that names the picks.}

**{Tagline, only if the project has a brand line}**

{Demo, only if the first run can be shown: one recording, with alt text that says what the recording is for.}

*{Caption: what the recording shows, in one line.}*

## Install

{For each supported install: who it is for or what it needs already installed, then the command. The commands name the branch that holds the latest release, never a version number; only other branches and versioned docs pin one. Say what the reader doesn't need first. If a command runs a downloaded script, say what it installs and what it asks of the machine, and link the script at the ref the command fetches.}

{The wrong install to avoid, phrased as an action, if a name collision makes one likely. One line linking the install guide for everything else.}

## {First-result heading, such as "Start a project"}

{One command block that takes the reader from installed to a first result.}

{What each argument means, what the command made, and how to see the other options, naming one in plain words.}

## Learn more

- [Documentation]({the docs site's root URL}): {the complete guide}
- [{Page}]({relative link}): {the question the page answers, in the reader's words}
- {Three to five links in all: the docs site first, then the first-use page, then concepts, and status last.}

## Help and contributing

{Where to look first, linked.} {Where bugs and requests go.} {What CONTRIBUTING.md is for, linked.}

## License

[{License name}]({relative link to the license file})
```

## The arc

Each section answers the question the section before it raised; the tagline is the one exception, marking the turn from describing the project to showing it. Nothing appears before the question it answers: no features before "what is it", no status before "how do I get it".

| # | Slot | The reader's question | Budget | Stays out (and lives where) |
| --- | --- | --- | --- | --- |
| 1 | Name and badges | Whose is this, and is it alive? | One heading, live badges only | Badge walls, sponsors, testimonials |
| 2 | Role, audience, foundation | What is it, is it for me, and what is it built on? | One bold sentence and up to two more | Internal names, mechanics (the docs) |
| 3 | Mission | Why does it exist? | One or two sentences | How it works in detail (the docs) |
| 4 | Curation, if the project carries choices | Why trust its choices? | One to three sentences; each pick named once | Rule counts, versions, how the maintainers decided (the page that owns the choices) |
| 5 | Tagline, if the project has a brand line | (the turn from describing to showing) | One line | A second slogan |
| 6 | Demo and caption, if the first run can be shown | Show me. | One recording, one line | Claims the recording does not show |
| 7 | Install | How do I get it? | One or two code blocks; at most three lines of prose | Every platform's steps, troubleshooting (the install guide) |
| 8 | First result | How do I start? | One code block, two or three sentences | Tutorials, option lists (the quickstart, the CLI reference) |
| 9 | Learn more | Where next? | Three to five links, the docs site first, status last | Anything those pages own |
| 10 | Help and contributing | Where do I ask, and how do I help? | Up to three sentences | Development setup, security policy, conduct, who maintains it (CONTRIBUTING.md and the community files) |
| 11 | License | Can I use it? | One line | The license text |

## Writing for a first-time reader

1. **Known words first.** Describe each thing by what it is, never by an internal name: "a template for Streamlit apps", not "the Streamlit app".
2. **Gloss or leave out.** A term a newcomer cannot decode is explained in the sentence that introduces it, or it stays in the docs.
3. **Say what is optional.** Mark the parts a solo reader can skip, such as team features.
4. **The instruction before its caveat,** and the caveat as an action: "Don't use `pip install boilerplate`", not the naming history.
5. **Say what a piped script installs,** and link the script, before asking anyone to run it.
6. **Link text in the reader's words:** the question the page answers, not the project's vocabulary.

## Durability rules

1. **One owner per fact.** The README states only the front-door facts in slots 2 to 8. Everything else links to the page that owns it.
2. **Facts that age get one home and an owner.** The README names no version: its commands name the branch that holds the latest release. The picks appear only in the curation sentence. No counts, dates, status or planned lists, or issue and pull request numbers.
3. **Names that change appear as few times as the page allows.** Commands, the demo's caption and an installer's consent line name only what they run or install. When a pick, a template name or a command changes, change the README together with the pages that own it.
4. **The page matches each release.** The commands name the branch that holds the latest release, so every release moves that branch. Any installer they fetch installs the CLI from the same branch, and the demo shows that release. Only other branches and versioned docs pin a version.
5. **Stable link targets.** The docs site's root URL, which redirects to the latest release; relative links for files in the repository, which GitHub resolves per branch; other external links only to stable pages.
6. **One role line on every surface.** The role line is the same sentence wherever the project says what it is: the README, the repository's About field, the package description, the CLI's help line, and the docs site's description and home. Where the name already shows beside it, the sentence drops its subject. Change them in one pull request, and change the About field, a repository setting, in the same sitting.
7. **The demo, its alt text and its caption change together,** along with any other page that embeds the same recording. The alt text says what the recording is for, so a re-recording that keeps its purpose keeps its text.
