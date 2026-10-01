---
paths:
  - "src/boilerplate/**/*.py"
---

# CLI messages house style

Governs any string that reaches the user through the error boundary (`boilerplate.cli.utils.cli_error_handler` and its exceptions), plus every progress, success, dry-run, and warning line `Display` prints. Help text (`help=` strings and command one-liners) is out of scope; see `cli-help.md`.

## Error format

An error line opens with `Error: <description>`; when the underlying exception carries a `BP_*` code, it appears as a bracketed suffix on that line (`Error: <description>   [BP_*]`), per `docs/design/07-operational-quality.md` §Error Message Format. A remediation, when the exception carries one, follows on its own indented line labeled `Fix:` (not `Hint:`). An unlabeled indented reason line (same section) precedes `Fix:` once an exception carries a distinct root cause separate from its description; none does today, so no call site prints one yet.

An option-combination check raised before any domain exception exists (`graph`'s `--output`/`--format` conflict, `validate`'s not-a-directory check) still opens with `Error:` for the same reason. `graph`'s conflict truly has no registered code. `validate`'s does — `BP_CONFIG_DIR_INVALID`, via `DirectoryValidationError` — but routing it through that exception would move the exit code from `3` (`docs/design/05-cli-reference.md` §validate) to `2` (the registry's own mapping in `docs/design/07-operational-quality.md`), a design conflict for the owner to resolve, not this rule's to paper over.

`validate`'s own check-result rows (see below) are exempt from the `Error:` prefix above even when their status is `FAIL`: they are check results, not error-boundary output, and carry no `BP_*` code.

## Stream contract

With `--format json`, the error is a field (`error`) of the single JSON object the command prints to stdout, never a separate line (`docs/design/05-cli-reference.md` §Global Options; `docs/design/07-operational-quality.md` §Error Message Format). For every other format, the `Error:`/`Fix:` lines go to stderr and nothing else does (§Output Display, §Error Handling); `--quiet` leaves stdout empty (§Quiet Mode). The error boundary (`cli_error_handler`) renders the text form regardless of `--format`, so a command that reaches it under `--format json` still gets plain `Error:`/`Fix:` lines instead of the JSON-object form — a known gap, alongside `compose`'s pre-JSON banner, `list`/`graph`'s table/tree rendering (`Display.table` never gates on `quiet`), and `new`'s post-render "Next steps" block (`Display.write` never gates on `quiet` either) — tracked as their own defects, not fixed by this rule.

## No markup in dynamic text

`Display.info`/`success`/`warning`/`error`/`error_detail` print with `markup=False` (`src/boilerplate/cli/display/core.py`): messages carry names and paths the user typed, and a `[` in them is literal text, never parsed as Rich markup.

## Warning line shape

One shape for every warning `Display.warning` prints — a deprecation notice or `validate`'s `WARN` rows — quoting `docs/governance/versioning.md`'s deprecation-process example verbatim:

```text
⚠️  'boilerplate <old>' is deprecated and will be removed in v2.0.0. Use 'boilerplate <new>' instead.
    See: <release-notes-url>
```

One line naming what's affected, the removal version, and the replacement, with an optional indented continuation line for a pointer (`See: <url>`) or other detail. `Display.warning` itself prints no glyph — the `warning` style carries the signal the source example's `⚠️` carries in plain text — so a call site that wants the glyph adds it inline. `validate`'s `WARN  <check name>` header plus its indented `-> <message>` line already follows this header-plus-continuation structure.

## Check-result rows

`validate`'s checks print one row format (`docs/design/05-cli-reference.md` §validate, which extends the same format to the not-yet-shipped `doctor` and `lock verify`): `<STATUS>  <check name>`, `STATUS` one of `PASS`/`WARN`/`FAIL`, `<check name>` a noun phrase (`boilerplate.yml exists`, not a sentence), with any detail on an indented `-> ` continuation line. `PASS` prints via `Display.success`, `WARN` via `Display.warning` (see above), `FAIL` via `Display.error` — `FAIL` still carries no `Error:` prefix; see Error format above.

## Progress and success lines

A line announcing work in progress ends in an ellipsis and names the object (`Resolving <template>...`, `Rendering to <destination>...`); a line reporting a completed fact is past tense with no ellipsis (`Created <destination> from <template> (<n> layers).`). A dry-run line states the would-be result the same way a completed fact would, present-conditional and with no ellipsis (`Dry run: would create <destination> from <layer> → <layer>`).
