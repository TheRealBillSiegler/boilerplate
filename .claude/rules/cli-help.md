---
paths:
  - "src/boilerplate/cli/**/*.py"
---

# CLI help-text house style

Applies to every `help=` string on a `typer.Option` or `typer.Argument`, and to the first line of each command's docstring (Typer's one-liner). Error messages, docs pages, and the app description are out of scope.

## Tenets

1. **Open with the verb, or the value.** An option that acts starts with an imperative verb ("Skip the template's post-creation tasks."). An option that takes a value starts with a noun naming it ("Path to the template directory to validate."). Never "Whether to", "If true", or "The --x option".
2. **Sentence case, closing period.** Typer appends `[default: x]` after the text, so the text ends first.
3. **One sentence, 80 characters.** A second sentence is allowed only for a relation, a repeat rule ("May be repeated."), or a hard precondition ("Required unless a terminal can prompt for it."). Rationale, tips, and what each value means go on the docs page.
4. **Relations take one of five forms.** "Implies --x." "Does not imply --x." "Cannot be combined with --x." "Requires --x." "Equivalent to --x." A value or a command may follow ("Equivalent to --sections stats.", "Implies --non-interactive on new."). No backticks, which rich markup prints literally, and no parenthesised relation.
5. **Leave to Typer what Typer prints.** Defaults, env vars, and Enum choices already render in brackets or the metavar, so restating them prints them twice. Prefer an Enum to a str with a value list.
6. **Present tense, effects only.** No "will", "now", "currently", "soon", "planned", "allows", no version history, no marketing adjectives, no "mode" as a label ("CI mode:").
7. **A one-liner is a verb and its object.** Imperative, one sentence, under 70 characters, no option names ("List the templates you can create a project from.").
8. **One text per behavior.** An option bound on several commands reads the same everywhere it does the same thing. Where it behaves differently on one command, it reads differently there instead of forcing a shared text (`--quiet` and `--output` read differently on `compose` than elsewhere).

## Test contract

`tests/boilerplate/cli/test_help_style.py` walks the Click command tree Typer builds from `boilerplate.cli.cli.app` and checks every option, argument, and command one-liner:

- First character upper case, last character a period.
- At most 80 characters (70 for a one-liner).
- At most one `. `; a second sentence opens with a relation form, "May be repeated", or "Required".
- No backtick, no parenthesised relation, none of tenet 6's banned words.
- An Enum-typed option names none of its own members.
- An option name carries one text across every command that binds it, except the tenet 8 exceptions the test names.

Provenance: tenets drawn from a survey of 273 options across 77 commands in 25 popular CLI tools (uv, ruff, git, kubectl, and others). Full evidence table: the pull request that landed this guide.
