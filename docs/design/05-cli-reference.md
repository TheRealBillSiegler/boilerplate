# CLI Reference

## Contents

- [Purpose](#purpose)
- [Invocation](#invocation)
- [Global Options](#global-options)
    - [Trust Flags](#trust-flags)
    - [Template Argument Resolution](#template-argument-resolution)
- [Help Text Structure](#help-text-structure)
    - ["Did You Mean?" for Unknown Commands](#did-you-mean-for-unknown-commands)
    - [Help Topics](#help-topics)
    - [Command Examples](#command-examples)
- [Commands](#commands)
    - Project: [new](#new) | [update](#update) | [add](#add) | [status](#status) | [adopt](#adopt) | [eject](#eject)
    - Template: [list](#boilerplate-list) | [compose](#compose) | [graph](#graph) | [validate](#validate) | [init-template](#init-template) | [test](#test)
    - System: [doctor](#doctor) | [env](#env) ([apply](#env-apply), [status](#env-status)) | [lock](#lock-verify) ([verify](#lock-verify)) | [cache warm](#cache-warm)
- [Shell Completions](#shell-completions)
- [Developer Experience Contracts](#developer-experience-contracts)
    - [Pipeline Narration](#pipeline-narration)
    - [Confirmation Contracts](#confirmation-contracts)
    - [Post-Action Guidance](#post-action-guidance)
    - [Answer Presets](#answer-presets)
    - [Interactive Prompting Contract](#interactive-prompting-contract)
- [UX Conventions](#ux-conventions)
    - [Output Display](#output-display)
    - [Terminal vs. Pipe Detection](#terminal-vs-pipe-detection)
    - [Quiet Mode](#quiet-mode)
    - [Verbose Mode](#verbose-mode)
    - [Terminal Accessibility](#terminal-accessibility)
- [Error Handling](#error-handling)
- [Exit Code Reference](#exit-code-reference)
- [Flag Reference Summary](#flag-reference-summary)
- [Constraints and Invariants](#constraints-and-invariants)
- [CI/CD Quick Reference](#cicd-quick-reference)

---

## Purpose

This document specifies the Boilerplate CLI surface: every command, flag, argument, output contract, and behavioral invariant. The CLI is an opinionated entry point, but it does not create lock-in — every underlying tool (Copier, Git, uv) remains directly invocable.

This document also specifies the developer experience contracts (pipeline narration, confirmation prompts, post-action guidance, answer presets, interactive prompting) that apply across all commands.

---

## Invocation

```text
boilerplate [global-options] <command> [command-options]
```

The CLI binary name is `boilerplate`. When invoked with no subcommand, the CLI MUST print the top-level help text and exit with code `0`. When `boilerplate` is invoked with no arguments, the help output MUST include a "Getting started" section at the top: `Get started: boilerplate list | boilerplate new <template> <destination>`.

---

## Global Options

These options apply to all commands and MUST be processed before any subcommand.

| Option | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--verbose` | `-v` | flag | `false` | Enable debug-level logging |
| `--quiet` | `-q` | flag | `false` | Suppress non-error output |
| `--help` | `-h` | flag | — | Print help text and exit |
| `--version` | — | flag | — | Print version and exit |
| `--templates-dir` | — | path | null | Override the template search directory for the command |
| `--format` | — | enum | varies | Output format (command-dependent: `text`, `table`, `json`, `yaml`, `tree`, `wide`) |
| `--ci` | | flag | `false` | Convenience flag equivalent to `--non-interactive --yes`. Default: `false`. See `--ci` behavior below. Component flags inapplicable to a given command (e.g. `--non-interactive` on `eject` and `adopt`) are no-ops for that command. |
| `--color` | — | enum | `auto` | Color output mode: `auto`, `always`, `never`. Default: `auto`. |
| `--offline` | — | flag | `false` | Use only the local cache; do not attempt any network access for remote catalog sources. Default: `false`. |

**Task execution truth table**: The following table defines the complete behavior of task execution flags across the two trust states. This is the authoritative reference for resolving flag interactions. For a dedicated explanation, see `boilerplate help trust`.

| Trust State | Default | `--yes` | `--no-tasks` | `--allow-tasks` | `--allow-tasks --yes` |
| --- | --- | --- | --- | --- | --- |
| trusted | prompt | execute | skip | execute | execute |
| untrusted | skip + warn | skip + warn | skip | prompt | execute |

- **prompt**: The CLI asks the user to confirm before executing tasks.
- **execute**: Tasks run without prompting.
- **skip**: Tasks are silently skipped (no warning).
- **skip + warn**: Tasks are skipped and a warning lists the skipped commands with the flag needed to enable them.

**Flag naming**: The canonical flag names are `--allow-tasks` and `--allow-extensions`. The convenience alias `--allow-untrusted` is equivalent to `--allow-tasks --allow-extensions`.

### Trust Flags

The following flags govern execution of untrusted template content and are accepted by `boilerplate new`, `boilerplate update`, and `boilerplate add`. They are defined here once; per-command sections reference this definition.

- `--allow-extensions` — Allow Jinja2 extensions declared by templates. Required when any template layer uses `_jinja_extensions`. Default: `false`.
- `--allow-tasks` — Allow task execution for untrusted templates. Default: `false`. See the [Task execution truth table](#global-options) above for trust-state rules.
- `--allow-untrusted` — Convenience alias equivalent to `--allow-extensions --allow-tasks`. Default: `false`.

**`--verbose` and `--quiet` are mutually exclusive.** If both are provided, the CLI MUST exit with code `3` and a clear error message.

**`--version`**: Prints the version string (e.g., `boilerplate 0.2.0`) and exits with code `0`.

**`--ci` behavior**: Designed for CI/CD pipelines where no human is present. `--ci` desugars to `--non-interactive --yes`: every question takes its default or forced answer, and task execution resolves under the truth table's `--yes` column, so trusted sources execute and untrusted sources skip with a warning. To execute tasks from an untrusted source in CI, pass `--ci --allow-tasks`, which resolves under the `--allow-tasks --yes` column (execute for both trust states).

**Environment variable equivalents**: `BOILERPLATE_CI` mirrors `--ci`; `BOILERPLATE_NON_INTERACTIVE` mirrors `new`'s `--non-interactive` (see below). Each is a tool-scoped opt-in following the `PIP_NO_INPUT` convention: the value is trimmed of surrounding whitespace, then enabled when the trimmed value is non-empty and not `0` or `false` (case-insensitive) — an explicit `0`/`false`, and empty or whitespace-only, all behave as unset. An explicit CLI flag always wins; the env var can only turn a behavior on, never veto a flag that is present. Both compose with the non-TTY guard (see `new` command below) exactly as the flags do. The generic `CI` environment variable is never inspected — see [adr-013-interactivity-contract.md](adr-013-interactivity-contract.md).

**`--color` modes**: `auto` uses TTY detection and `NO_COLOR`. `always` forces color on (useful when piping to `less -R`). `never` forces color off. Follows the convention established by git, cargo, and ripgrep.

**`--offline` behavior**: Operations requiring templates not present in the local cache will fail with `BP_RESOLVE_TEMPLATE_NOT_FOUND` (the template cannot be found in any available source). Local filesystem sources are always available regardless of this flag. Use `boilerplate cache warm` to pre-populate the cache for offline use.

**`--templates-dir`**: When provided, it is added to the catalog build before the configured `extra_template_dirs`. Resolution order (highest to lowest priority): `--templates-dir` (if provided) → `default_templates_dir` (the user's default template directory) → `extra_template_dirs` → first-party templates (the published per-template git repositories, [ADR-006](adr-006-template-distribution.md); implicit source) — authoritative definition in [03 §Template Directory Resolution Order](03-template-system.md#template-directory-resolution-order). The `--templates-dir` flag takes highest priority, allowing users to override all configured directories. This ensures explicit CLI arguments always win over configuration.

**`--format` per-command support**: Every command MUST support `--format json`. Additional formats are command-specific:

| Command | Supported Formats |
| --- | --- |
| `new` | `text` (default), `json` |
| `update`, `add`, `status`, `doctor`, `validate`, `init-template`, `env` | `table` (default), `json` |
| `list` | `table` (default), `json`, `wide` |
| `compose` | `yaml` (default), `json` |
| `graph` | `table` (default), `json`, `tree` |

When `--format json` is active, the command MUST output exactly one JSON object to stdout. No progress output, no human-readable messages. Errors are included in the JSON object's `error` field, not printed separately.

### Template Argument Resolution

All commands that accept a template reference use the `<template-spec>` argument name for consistency. Several commands (`compose`, `graph`, `validate`) accept a `<template-spec>` argument that may be either a template name/reference or a filesystem path. The CLI MUST resolve this argument using the following rule:

1. If the argument contains a path separator (`/` or `\`) or starts with `.`, treat it as a **filesystem path**. Load the template directly from the directory.
2. Otherwise, treat it as a **template reference** (name or `name@version`) and resolve via the catalog.

This means `boilerplate compose ./project` is always a path, and `boilerplate compose project` is always a catalog lookup. To force path resolution for a directory in the current working directory whose name matches a template, use `./name`.

---

## Help Text Structure

The `--help` output MUST use visual grouping to organize commands by domain. A `Get started:` block MUST appear before command groups to give new users an immediate entry point. Global options MUST appear at the bottom (lowest priority for new users):

```text
Usage: boilerplate [OPTIONS] COMMAND [ARGS]

  Less Yak. More Stack.

  Composable project scaffolding with template layering, lock files,
  and environment provisioning.

  Get started:
    boilerplate list                    Browse available templates
    boilerplate new <template> <dest>   Create a new project

Project commands:
  new            Create a new project from a template
  update         Update project to newer template version
  add            Add a template layer to a managed project
  adopt          Import an existing Copier project into Boilerplate
  eject          Stop Boilerplate management of a project
  status         Show project and environment state

Template commands:
  list           List and search available templates
  compose        Show template composition and merged config
  graph          Show template dependency graph
  validate       Validate a template directory
  init-template  Create a new template skeleton
  test           Run template regression tests

System commands:
  doctor         Run health checks
  env            Manage environment profiles
  cache          Pre-populate template cache
  lock           Lock file operations (verify)

Global options:
  -v, --verbose       Enable debug logging
  -q, --quiet         Suppress non-error output
      --format FMT    Output format (text, json, table, yaml, tree, wide)
      --templates-dir Override template search directory
      --ci            CI mode (non-interactive, --yes)
      --color MODE    Color output (auto, always, never)
      --offline       Use local cache only
  -h, --help          Show this message and exit
      --version       Show version and exit
```

### "Did You Mean?" for Unknown Commands

If the user types an unknown command, the CLI MUST suggest the closest match based on edit distance. Example:

```text
$ boilerplate nw streamlit
Error: Unknown command 'nw'. Did you mean 'new'?
```

### Help Topics

The CLI MUST support `boilerplate help <topic>` for extended documentation on cross-cutting concerns. Help topics are distinct from command help (`--help`) — they provide conceptual explanations rather than flag references.

**`boilerplate help trust`**: Displays the trust model documentation: the binary trusted/untrusted states and how they are assigned, the task execution truth table (from Global Options above), flag interactions, and examples of common flag combinations. See [03-template-system.md §Trust and Verification](03-template-system.md#trust-and-verification-levels) for the canonical trust model.

If `boilerplate help` is invoked without a topic, it MUST list available topics. If an unknown topic is provided, it MUST suggest the closest match.

### Command Examples

Every command's `--help` output MUST include an `Examples:` section showing at least two representative invocations. Examples MUST use realistic values, not placeholder strings like `<foo>`. They appear after the options table and before the exit codes.

Example for `new`:

```text
Examples:
  boilerplate new project my-service
  boilerplate new streamlit@1.0.0 ./my-dashboard --no-git-init
  boilerplate new streamlit my-app --answers ci/answers.yml --non-interactive
```

---

## Commands

### `new`

**Usage**: `boilerplate new <template-spec> <destination> [options]`

Resolve, compose, and render a template into a destination directory. This is the primary project creation command.

**Arguments**:

| Argument | Required | Description |
| --- | --- | --- |
| `template-spec` | Yes | Template reference: `name` or `name@version` |
| `destination` | Conditional | Target directory path. MUST be provided as an argument OR prompted interactively. |

**Version syntax**: The CLI accepts `name` (resolves to latest) or `name@version` (exact version). Version ranges (e.g., `name@>=2.0`) are NOT supported at the CLI level — they are resolved internally within `extends` chains.

If `<template-spec>` is omitted and the terminal is interactive, Boilerplate presents a simple numbered selection prompt listing available templates (name, version, one-line description) for the user to pick from. In non-interactive mode, omitting `<template-spec>` is an error.

**Template selection prompt**: When `<template-spec>` is omitted and stdin is a TTY, Boilerplate lists available templates and prompts for a selection. Selecting a template proceeds to the question prompts; pressing Ctrl+C exits without action (exit code 130), the same cancellation code used everywhere else in the CLI.

The selection prompt MUST NOT make network calls. It operates only on locally cached catalog data. If no templates are found from configured sources, it MUST list first-party templates under the heading 'First-party templates — get started quickly'. The diagnostic message suggesting `boilerplate doctor` MUST only appear if no templates are found at all, including first-party templates.

**Destination behavior**: The destination MUST be explicitly provided or interactively prompted. The CLI MUST NOT default to a template-named subdirectory. When `--non-interactive` is active and no destination is provided, the CLI MUST exit with code `3` and the message `Error: destination is required in non-interactive mode.`

**Options**:

| Option | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--force` | `-f` | flag | `false` | Overwrite destination if it already exists (no confirmation). Default: `false`. |
| `--non-interactive` | — | flag | `false` | Use defaults for all unanswered questions without prompting. Default: `false`. |
| `--dry-run` | `-n` | flag | `false` | Show the composition plan without rendering or writing files. Default: `false`. |
| `--render-to` | — | path | null | Render the template to the specified directory for inspection without creating a managed project. Default: null. |
| `--git-init` | — | flag | `true` | Initialize a Git repository in the created project directory. Default: `true`. Use `--no-git-init` to skip. |
| `--answers` | `-a` | path | null | YAML file containing question answers. Default: null. |
| `--set` | `-s` | key=value | — | Inline answer override for scalar values (repeatable). |
| `--save-answers` | — | path | null | Write final merged answers to a YAML file for CI reproducibility. Default: null. See `--save-answers` notes below. |
| `--data` | — | key=value | — | Forced answer for one question (repeatable). Never prompted for; satisfies the non-interactive required-answer pre-flight. Precedence on collision: `--data` > `--data-file` > profile pre-fills. |
| `--data-file` | — | path | null | YAML file mapping question name to forced answer, read as UTF-8. Same forced-answer semantics as `--data`; `--data` wins on a key collision. |
| `--no-tasks` | — | flag | `false` | Skip execution of all template tasks (`_tasks`). Default: `false`. |
| `--yes` | `-y` | flag | `false` | Suppress confirmation prompts for task execution and Jinja2 extension loading. Default: `false`. For untrusted templates, `--allow-tasks` (or `--allow-untrusted`) is additionally required. Does not affect interactive question prompts — use `--non-interactive` for that. |

Trust flags (`--allow-extensions`, `--allow-tasks`, `--allow-untrusted`): see [Trust Flags](#trust-flags).

**`--data`/`--data-file` vs `--answers`/`--set`/`--save-answers`**: `--data` and `--data-file` name Copier's own forced-answers channel directly (`--data`/`--data-file` in Copier itself), so the flag names carry over unchanged for anyone already familiar with Copier. `--answers`/`--set`/`--save-answers` cover the round-trip answers workflow; their overlap with the forced-answers flags is reconciled in that feature's design.

`--no-tasks` is the canonical flag name. `--skip-tasks` is accepted as an alias for compatibility but is not displayed in help text.

Short flags are reserved for options typed at a prompt, such as `-f` and `-n`. `--non-interactive` and `--no-tasks` are scripted, safety-relevant switches and have no short form; `-n` means dry run here as it does in Copier, make and rsync.

**`--dry-run` vs `--render-to`**: `--dry-run` shows the composition plan and the list of files that would be created without producing any output. To render files for inspection without committing a managed project, use `--render-to <dir>`.

**`--git-init` rationale**: Git initialization is the default because `boilerplate update` requires a Git repository.

**`--save-answers` notes**: The saved file is a YAML document containing only user-provided answer values (keys and their resolved values). It does not include Copier-internal metadata (`_commit`, `_src_path`, etc.) or default values that were not explicitly provided. Questions marked with `secret: true` in the template are excluded from the saved file; a placeholder comment indicates the omission: `# secret_question: <omitted — marked as secret>`. See [§10 Privacy](10-security.md#privacy) for details. The file can be passed directly to `--answers` in subsequent invocations.

**`--force` and `--non-interactive` are independent concerns.** `--non-interactive` means "use defaults for all questions." `--force` means "overwrite existing destination." Neither implies the other: CI may need `--non-interactive` without `--force` (fail if destination exists), and a retry may need `--force` while still prompting interactively.

**`--non-interactive` environment variable equivalent**: `BOILERPLATE_NON_INTERACTIVE` mirrors this flag with OR semantics — see the environment variable equivalents note in [Global Options](#global-options).

**Behavior**: See [06-project-lifecycle.md](06-project-lifecycle.md) for the full creation pipeline. Task execution follows the trust-level rules in the Global Options truth table above and the full safety model in [03-template-system.md §Task Execution Safety](03-template-system.md#task-execution-safety).

**Key behavioral contracts**:

- `--dry-run`: Runs resolve and compose, displays the composition plan without rendering. Exits `0` on success.
- `--render-to`: Renders to a directory for inspection without creating a managed project. Skips lock file, `.boilerplate/`, git init, and atomic staging. Tasks are not executed in `--render-to` mode by default. To execute tasks, pass `--allow-tasks`; the normal trust-level rules then apply (see Global Options truth table). Requires `--force` if target is non-empty.
- `--git-init` (default `true`): Initializes a git repo after rendering. Does not create an initial commit. If `git init` fails, emits a WARNING but does not fail the operation.

**Exit codes**:

- `0` — template rendered successfully
- `1` — rendering failed (template not found, Copier error, etc.)
- `2` — configuration could not be loaded
- `3` — input validation failed (missing destination, invalid specifier, etc.)

---

### `update`

**Usage**: `boilerplate update [options]`

Update an existing project to a newer template version. The walk runs in a temporary git worktree of the project and lands in the working tree as uncommitted changes, which is what plain Copier leaves ([06-project-lifecycle.md §Staging worktree](06-project-lifecycle.md#staging-worktree)). See [06-project-lifecycle.md](06-project-lifecycle.md) for the full update workflow.

> **Prerequisite**: The project directory MUST be a git repository. The `update` command requires git access to each layer's template source so that Copier can perform per-layer three-way merge, and uses git for the staging worktree. The working tree MUST have no uncommitted changes, untracked files included, which is Copier's own rule, and a project with submodules (`.gitmodules`) is refused. Projects created without `--git-init` that were never placed under git version control cannot be updated. Run `git init && git add -A && git commit -m 'Initial project'` first.

**Limitation**: Projects created from Copier-only templates (templates without `boilerplate.yml`) do not have a `boilerplate.lock` file and cannot be updated via `boilerplate update`. Use `copier update` directly for these projects.

**Options**:

| Option | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--dry-run` | `-n` | flag | `false` | Show update plan and exit without prompting or applying. Default: `false`. |
| `--target-version` | `-t` | string (repeatable) | null | Target version. `<version>` names the root template's target and `<layer>@<version>` names that layer's, so the option repeats to pin several layers. Default: each layer's latest. A layer the lock does not list stops the run with `BP_UPDATE_LAYER_UNKNOWN`; resolution is in [06 §Step 2](06-project-lifecycle.md#step-2-resolve-target). Refused when it differs from the targets a pending `conflict` record names. |
| `--answers` | `-a` | path | null | YAML file containing question answers. Default: null. |
| `--set` | `-s` | key=value | — | Inline answer override for scalar values (repeatable). |
| `--yes` | `-y` | flag | `false` | Skip confirmation prompt; apply immediately. Default: `false`. |
| `--non-interactive` | — | flag | `false` | Take every question's default without prompting, a recorded answer being its question's default. Default: `false`. |
| `--skip-answered` | — | flag | `false` | Ask only the questions no answers file records. Default: `false`. |
| `--no-tasks` | — | flag | `false` | Skip execution of all template tasks (`_tasks`). Default: `false`. |
| `--template-source` | — | path or URL | null | Override the template source location used by Copier when its built-in resolution cannot reach the template. Default: null. |

Trust flags (`--allow-extensions`, `--allow-tasks`, `--allow-untrusted`): see [Trust Flags](#trust-flags).

**`--skip-answered`**: Ask only the questions no answers file records, as Copier's `--skip-answered` does; every recorded answer stands without a prompt. Prompting happens inside each layer's step ([design 04 §Safe Update](04-composition-engine.md#safe-update)).

**`--non-interactive`**: Take every question's default without prompting, as Copier's `--defaults` does. A recorded answer is the default of its question, so existing answers from each layer's `.copier-answers.<layer>.yml` are reused and a new question takes its declared default.

**`--answers` and `--set`**: Both are laid over the data each layer's step receives, as Copier's own `--data` is laid over the answers it reads. A value supplied for a question whose recorded answer the target view rejects replaces that answer, and Copier validates the supplied value instead.

**Default behavior**: Compute the update plan, display it, then prompt the user for confirmation before applying. This is one command, one flow — not a two-step dry-run-then-apply cycle.

**Interactive flow** (TTY output):

```text
Update plan for my-project

  Template versions:
    project     0.1.0 -> 0.2.0  MINOR
    streamlit   0.1.0 -> 0.1.1  PATCH

  Files (12 total):
    Modified    pyproject.toml        merge required (template + local changes)
    Modified    src/config.py         clean update (template change only)
    Added       src/middleware.py
    Removed     src/legacy_config.py

  Summary: 12 files affected, 1 merge required, 0 conflicts predicted

Proceed? [y/N]
```

MAJOR updates MUST include a prominent warning about breaking changes in the plan summary.

**`--dry-run`**: Print the plan and exit without prompting or applying. For CI/scripting where you want the plan as output without any interaction.

**`--yes`/`-y`**: Print the plan, skip the prompt, apply immediately. For automation.

**Task execution**: Follows the same trust-level rules as `new` (see [03-template-system.md §Task Execution Safety](03-template-system.md#task-execution-safety)).

**Conflicts**: When a layer's update produces conflicts, the CLI brings back the layers finished so far with Copier's conflict markers in the affected files, writes no lock file and exits with code `4` (`ACTION_REQUIRED`, `BP_UPDATE_CONFLICT_PAUSED`). The user resolves the conflicts and commits as with plain Copier, then reruns `boilerplate update`, which resumes from the `conflict` record in `.boilerplate/migrations.yml`: the record names each layer's target version and the layers already finished, so the rerun skips those layers and walks the rest to the recorded targets. An explicit `--target-version` that differs from the record is refused until the user sets the partial update aside. Once the partial update is committed, `git revert` of the commit that holds it sets it aside; before the commit, `git reset` and then `git stash --include-untracked` do, added files included, and the reset comes first because `git stash` refuses the conflicted files' unmerged index entries. A rerun before the user commits stops at the clean working tree check with exit code `3` ([06-project-lifecycle.md §Step 5](06-project-lifecycle.md#step-5-failure-and-conflict)).

**Interrupted runs**: A run cut off while it copies its result back or finishes is completed by running the same command again, when the working tree holds only what the run wrote and no conflict had paused the run. The rerun finishes that run and ends with its exit code, planning no new update. Otherwise the rerun stops with `BP_UPDATE_INTERRUPTED`, and `git reset` and then `git stash --include-untracked` set the partial update aside ([06 §Interrupted copy back](06-project-lifecycle.md#interrupted-copy-back)). No flag is involved.

**File status indicators**:

| TTY Label | Non-TTY/JSON Code | Meaning |
| --- | --- | --- |
| `Modified` | `M` | Template changed this file |
| `Added` | `A` | New file from template |
| `Removed` | `D` | File removed in new template version |
| `Conflict` | `C` | Both template and local changes detected (predicted) |

TTY output uses full-word labels for immediate comprehension. Non-TTY and JSON output use single-letter codes for parseability. JSON output MUST include both fields: `"status": "M"` and `"status_label": "Modified"`.

**Confirmation rules**: MAJOR updates MUST show a risk warning in the plan summary. All updates prompt `Proceed? [y/N]` unless `--yes` is active. See [Confirmation Contracts](#confirmation-contracts).

**JSON output**: `--format json` with `--dry-run` outputs the plan (including `updates_available: bool`); with `--yes` outputs the result. `--format json` without `--dry-run` or `--yes` exits with code `3` — JSON mode requires explicit intent.

**Exit codes**: `0` on success, `1` on failure, `2` on config error, `3` on validation error.

---

### `add`

**Usage**: `boilerplate add <template-spec> [path] [options]`

Add one template layer to a project Boilerplate already manages, the way a by-hand `copier copy` with its own answers file would, and record it in `boilerplate.lock`. See [06-project-lifecycle.md §Adding a layer](06-project-lifecycle.md#adding-a-layer) for the full workflow.

**Arguments**:

| Argument | Required | Description |
| --- | --- | --- |
| `template-spec` | Yes | Template reference: `name` or `name@version` |
| `path` | No | Path to the project directory (defaults to `.`) |

**Options**:

| Option | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--dry-run` | `-n` | flag | `false` | Show the add plan and exit without prompting or applying. Default: `false`. |
| `--answers` | `-a` | path | null | YAML file containing question answers. Default: null. |
| `--set` | `-s` | key=value | — | Inline answer override for scalar values (repeatable). |
| `--yes` | `-y` | flag | `false` | Skip confirmation prompt; apply immediately. Default: `false`. |
| `--non-interactive` | — | flag | `false` | Use defaults for the layer's questions without prompting. Default: `false`. |
| `--no-tasks` | — | flag | `false` | Skip execution of all template tasks (`_tasks`). Default: `false`. |
| `--template-source` | — | path or URL | null | Override the template source location used by Copier when its built-in resolution cannot reach the template. Default: null. |

Trust flags (`--allow-extensions`, `--allow-tasks`, `--allow-untrusted`): see [Trust Flags](#trust-flags).

`add` has no `--force`: the clean working tree check cannot be skipped.

**Preconditions**: each failure happens before any file changes and exits with code `3` (`VALIDATION_ERROR`; [ADR-004](adr-004-exit-code-taxonomy.md)).

| Precondition | Error and remediation |
| --- | --- |
| The project is managed: `boilerplate.lock` exists | `BP_UPDATE_PROJECT_NOT_MANAGED`: `Project is not managed by Boilerplate. Use 'boilerplate adopt' first.` |
| The working tree is clean | `BP_UPDATE_PROJECT_NOT_READY`: `Working tree has uncommitted changes. Commit them, or run 'git reset' and then 'git stash --include-untracked', before running boilerplate add.` |
| The template is not already in the project | `BP_UPDATE_LAYER_ALREADY_ADDED`: `Template '{name}' is already in this project. Use 'boilerplate update' instead.` |
| Every template the new layer `extends`, transitively, is already in the lock | `BP_UPDATE_ANCESTORS_MISSING`. The error names each missing layer. Remediation: `boilerplate add <ancestor>` first. |
| Each such ancestor's recorded version satisfies the new layer's `extends` constraint | `BP_UPDATE_ANCESTOR_VERSION_MISMATCH`. The error names the ancestor, its recorded version and the constraint. Remediation: `boilerplate update` first. |

`add` and `update` stay separate operations: `add` never changes a layer already in the project.

**Interrupted runs**: A run cut off while it copies the layer back, writes the lock or appends the record is completed by running the same command again, when the working tree holds only what the run wrote; the rerun ends with that run's exit code and adds nothing new. A run cut off while the layer's tasks run leaves no marker, because `add` runs its tasks after the record, so the rerun stops with `BP_UPDATE_LAYER_ALREADY_ADDED` and the layer's tasks are run by hand. Otherwise the rerun stops with `BP_UPDATE_INTERRUPTED`, and `git reset` and then `git stash --include-untracked` set the partial add aside ([06 §Interrupted copy back](06-project-lifecycle.md#interrupted-copy-back)). No flag is involved.

**Default behavior**: Compute the add plan, display it, then prompt for confirmation before applying, as `update` does. `--dry-run` prints the plan and exits; `--yes` skips the prompt. The result lands as uncommitted changes, so the user reviews and commits it.

**`--answers` and `--set`**: Both are laid over the new layer's questionnaire data, as Copier's own `--data` is.

**Task execution**: The new layer's tasks run once, under the same trust-level rules as `new` (see [03-template-system.md §Task Execution Safety](03-template-system.md#task-execution-safety)).

**JSON output**: `--format json` with `--dry-run` outputs the plan; with `--yes` outputs the result. `--format json` without either exits with code `3`, as for `update`.

**Exit codes**: `0` on success, `1` on failure, `2` on config error, `3` on validation error.

---

### `list` { #boilerplate-list }

**Usage**: `boilerplate list [query] [options]`

List and search available templates from the catalog. When a query is provided, matching templates are filtered case-insensitively and returned in a deterministic order. Whether or not a query is provided, results use the same stable ordering (see Ordering below).

**Arguments**:

| Argument | Required | Description |
| --- | --- | --- |
| `query` | No | Keyword search query. Matched case-insensitively against template name, description, and tags. |

**Options**:

| Option | Description |
| --- | --- |
| `--category <cat>` | Filter by category. |
| `--tag <tag>` | Filter by tag (repeatable). |
| `--trust <state>` | Filter by trust state: `trusted`, `untrusted`. |
| `--type <type>` | Filter by classification: `boilerplate-enabled`, `copier-only`. |
| `--all-versions` | Show all versions of each template. Default: latest only. |
| `--include-archived` | Include archived templates in results. Default: excluded. |
| `--source <name>` | Restrict results to a specific catalog source. |
| `--refresh` | Sync remote sources before listing. |

**Default behavior**: Show latest published versions from all sources. Deprecated templates are shown with a warning indicator and successor reference (if declared). Archived templates are hidden.

**First-party template fallback**: When no configured catalog sources return results (fresh install, empty catalog, or all sources filtered out), `list` MUST show first-party templates under a `First-party templates` header. This ensures the "Getting started" path (`boilerplate list` → `boilerplate new`) never dead-ends on a fresh install. When truly empty (no first-party templates either), display: `No templates found. Run 'boilerplate new' to browse first-party templates interactively, or configure sources. See: boilerplate doctor.`

**Ordering**: Results use the deterministic catalog ordering defined in [03 §Result Ordering](03-template-system.md#result-ordering) — source priority (lower number first), then name, then version (descending). Trust state does not affect ordering; it is displayed in the `Trust` column. A query only filters the set; it does not reorder it.

**Output columns** (table format): `Name`, `Version`, `Type`, `Trust`, `State`, `Description`

When `--format wide` is active, also show: `Source`, `Tags`, `Path`, `Last Updated`

**Empty result behavior**: If no results match, print: `"No templates found matching '{query}'. Try --refresh to update the catalog or adjust your filters."` Exit with code `0`.

**Exit codes**:

- `0` — command completed (results may be empty)
- `1` — catalog could not be loaded

---

### `compose`

**Usage**: `boilerplate compose <template-spec> [options]`

Show the composition artifact for a template — the merged configuration produced by resolving and combining all template layers.

**Arguments**:

| Argument | Required | Description |
| --- | --- | --- |
| `template-spec` | Yes | Template reference: `name`, `name@version`, or a directory path |

**Direct path support**: Accepts a directory path in addition to catalog-registered template names. See [Template Argument Resolution](#template-argument-resolution) for disambiguation rules. When a path is provided, the template is loaded directly from disk without catalog registration.

**Options**:

| Option | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--questions` | `-Q` | flag | `false` | Show the merged questionnaire (names, types, defaults) for CI discovery. Default: `false`. |
| `--section <name>` | — | string | `final` | Composition section to display: `final`, `layers`, `states`, `deltas`, `stats` (repeatable). Default: `final`. |
| `--all` | — | flag | `false` | Include all composition sections. Default: `false`. |
| `--stats` | — | flag | `false` | Shortcut for `--section stats`. Default: `false`. |
| `--output` | `-o` | path | null | Write artifacts to a directory. Default: null. |

**Default behavior** (no flags): Display the `final` composition section in YAML format.

`--section` is repeatable: `--section layers --section deltas` displays both sections. `--all` is a convenience equivalent to specifying all five sections.

**`--questions` mode**: Shows the merged questionnaire — only user-facing questions (no `_` directives), displayed as a table of name, type, default, and help text. This is the primary discovery mechanism for CI pipelines building answer presets. With `--format json`, outputs a machine-readable schema. Each question entry includes `name`, `type`, `help`, `default`, `choices`, `required`, and a `default_is_expression` boolean (to distinguish Jinja2 expressions from literal defaults).

**Composition sections**:

| Section | Content |
| --- | --- |
| `final` | The fully merged Copier configuration |
| `layers` | Per-layer question values |
| `states` | Per-layer cumulative state |
| `deltas` | Per-layer delta from previous state |
| `stats` | Aggregate statistics about the composition |

**Output behavior**: With `--output <dir>`, writes each section as a file (`{section}.{format}`). Without `--output`, prints to stdout. `--output` MUST point to a directory.

**Exit codes**: `0` on success, `1` on failure, `3` on validation error.

---

### `graph`

**Usage**: `boilerplate graph <template-spec> [options]`

Show the dependency graph and execution sequence for a template.

**Arguments**:

| Argument | Required | Description |
| --- | --- | --- |
| `template-spec` | Yes | Template reference: `name`, `name@version`, or a directory path |

**Direct path support**: Accepts a directory path in addition to catalog-registered template names. See [Template Argument Resolution](#template-argument-resolution) for disambiguation rules. When a path is provided, the template is loaded directly from disk without catalog registration.

**Options**:

| Option | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--tree` | — | flag | `false` | Use tree format instead of numbered table. Default: `false`. |

**Default behavior**: Show the dependency execution sequence as a numbered table:

```text
#   Layer          Version   Path
1   project        2.1.0     /path/to/project
2   streamlit      1.0.0     /path/to/streamlit
```

When a diamond dependency pattern is detected (a node reachable via two or more paths), affected nodes are annotated with a `[diamond]` indicator noting which parent's files take precedence (see [04-composition-engine.md](04-composition-engine.md) for the precedence rules).

**`--tree` mode**: Hierarchical view of the dependency structure:

```text
streamlit@1.0.0
└── project@2.1.0
```

When stdout is a TTY, Unicode box-drawing characters are used. When `NO_COLOR` is set or stdout is not a TTY, ASCII equivalents are used.

**Exit codes**: `0` on success, `1` on failure, `3` on validation error.

---

### `validate`

**Usage**: `boilerplate validate <template-dir> [options]`

Validate that a template directory is well-formed and its references are resolvable.

**Arguments**:

| Argument | Required | Description |
| --- | --- | --- |
| `template-dir` | Yes | Path to the template directory to validate |

**Direct path support**: Accepts a directory path in addition to catalog-registered template names. See [Template Argument Resolution](#template-argument-resolution) for disambiguation rules.

**Checks**:

| ID | Check | Severity | Description |
| --- | --- | --- | --- |
| `V01` | `boilerplate.yml` present | error | Required file |
| `V02` | `copier.yml` present | error | Required file |
| `V03` | `boilerplate.yml` schema valid | error | All required fields, valid types |
| `V04` | `name` matches `^[a-zA-Z0-9_\-]+$` | error | Name format validation |
| `V05` | `version` is valid PEP 440 | error | Version format validation |
| `V06` | `extends` references resolvable | warning | Checks against catalog (warns if catalog unavailable) |
| `V07` | `copier.yml` loadable by Copier | error | Parsing is delegated to Copier's own config loader per [03-template-system.md](03-template-system.md#yaml-parsing-rules); Copier-native constructs such as the `!include` tag and multi-document files are valid. Loading reads configuration only — `_tasks`/`_migrations` are never executed. |
| `V08` | No duplicate keys in YAML files | error | YAML spec compliance. For `copier.yml` the check is structural (node-level scan, no tag construction), so Copier-native tags cannot break it. |
| `V09` | No custom YAML tags | error | Security constraint, scoped to `boilerplate.yml`; `copier.yml` parsing is delegated to Copier per [03-template-system.md](03-template-system.md#yaml-parsing-rules). |
| `V10` | `.gitmodules` maps `extends` parents | error | Only runs when `.gitmodules` is present: each `extends` parent maps to a submodule path and submodules are initialized. |
| `V11` | Version constraints satisfiable | error | Version constraints across the resolved `extends` chain are mutually satisfiable. Only runs when `extends` dependencies are resolvable. |
| `V12` | Composition merge conflicts | error | When the validated template has `extends` dependencies and those dependencies are resolvable from configured sources, `validate` MUST run the full Resolver → Composer pipeline and report any `MergeConflictError` as a validation error. This ensures composition issues are caught at authoring time, not at `boilerplate new` time. |
| `V13` | File path collisions across layers | warning | When a derived template provides a file at the same path as a base template, the base file is silently replaced (last layer wins). `validate` MUST detect these collisions and emit a warning: `File 'pyproject.toml' in layer 'streamlit@1.0.0' overrides the same file in 'project@2.1.0'. This is intentional (last layer wins) but may be unexpected.` This check only runs when `extends` dependencies are resolvable. |
| `V14` | Jinja extensions allowlisted | error | Declared `_jinja_extensions`, if any, resolve to packages on the system-wide allowlist (`allowed_extension_packages`, [09 §Settings](09-settings-and-configuration.md)). |
| `V15` | Extension class names unique within the scoped view | warning | When two layers in the validated template's [scoped view](04-composition-engine.md#scoped-view) declare extensions with the same class name from different import paths, `validate` MUST warn, naming the class name, both import paths and both layers; the render warns on a runtime replacement ([04 §Per-Layer Render Loop](04-composition-engine.md#per-layer-render-loop)). This check only runs when `extends` dependencies are resolvable. |
| `V16` | Overrides stay within the overridden question's scope | error | When a layer overrides a question an ancestor declares, the override's `default`, `when`, `validator` and `choices` expressions MUST reference only questions in the [scoped view](04-composition-engine.md#scoped-view) of the layer that declares the overridden question, because the ancestor's update step takes the override's definition from the full merged schema and a question only the descendant declares is undefined there. `validate` MUST report each reference outside that scope, naming the override, the question and the layer. This check only runs when `extends` dependencies are resolvable. |
| `V17` | Ancestor question not redeclared unchanged | warning | When a layer's `copier.yml` declares a question an ancestor declares and the declaration is identical to the ancestor's, `validate` MUST warn, naming the question and both layers, because the layer's [scoped view](04-composition-engine.md#scoped-view) already hands the ancestor's question to every render of the layer ([03 §Overriding a question in a derived template](03-template-system.md#example-copieryml)). It warns rather than fails because `merge_questions` merges the identical declaration harmlessly. This check only runs when `extends` dependencies are resolvable. |

Check IDs are stable and may be cited in error messages and CI output. This table is the authoritative check registry; [03 §Validation Surface](03-template-system.md#validation-surface) defines the invariants validation must uphold.

**`--strict` flag**: When `--strict` is active, warnings are promoted to errors. `validate --strict` exits `1` if any check produces a warning or error. This enables CI pipelines to enforce strict template quality: `boilerplate validate --strict ./my-template`.

**Output** (unified check-result format):

```text
Validating template at ./my-template...

  PASS  boilerplate.yml present and valid
  PASS  copier.yml present and parseable
  PASS  Name 'my-template' is valid
  PASS  Version '1.0.0' is valid PEP 440
  WARN  extends reference 'base-project' not found in catalog
        -> Refresh catalog: boilerplate list --refresh

5 checks: 4 passed, 1 warning, 0 errors
```

All check-result commands (`validate`, `doctor`, `lock verify`) use 4-character status labels: `PASS`, `WARN`, `FAIL`. Failures and warnings include inline remediation lines prefixed with `->`. See [Terminal Accessibility](#terminal-accessibility).

**Exit codes**: `0` valid (warnings only), `1` invalid (errors found or `--strict` with warnings), `3` path doesn't exist or validation could not run.

---

### `status`

**Usage**: `boilerplate status`

Reports the current state of the Boilerplate installation and, if present, the project in the working directory.

> **Roadmap note**: The `status` command is deferred to Phase 3 per the roadmap. The specification below defines its target behavior; it is not part of the current CLI surface.

**Sections**:

| Section | When shown |
| --- | --- |
| Project | When `boilerplate.lock` exists in the working directory |
| Environment | When `.boilerplate/environment.yml` exists in the working directory |
| Settings | Always |

**Update availability**: When a project is present, `status` MUST check whether newer template versions are available (cached catalog only — no network calls).

When any configured path does not exist, `status` MUST append: `Run 'boilerplate doctor' for diagnostics.`

**Exit codes**: `0` on success. `status` is informational and MUST report state issues (missing or corrupted `boilerplate.lock`, missing or corrupted `.boilerplate/environment.yml`, stale cached catalog) in its output rather than via exit code. The single exception is the universal Settings-load failure: if loading the Settings object fails, the CLI MUST exit with code `2` (`CONFIG_ERROR`) per [§09 Settings](09-settings-and-configuration.md#settings) — this rule applies to every command including `status`.

---

### `adopt`

**Usage**: `boilerplate adopt [project-dir] [options]`

Import an existing Copier-managed project into Boilerplate lifecycle management. Reads the project's Copier answers file(s) — either Copier's default singular `.copier-answers.yml` (legacy projects) or per-layer `.copier-answers.<layer>.yml` files (projects scaffolded from Boilerplate-enabled templates that declare `_answers_file:`) — resolves the template in the catalog, writes `boilerplate.lock`, and initializes `.boilerplate/migrations.yml`. The project's files are not modified — only Boilerplate state files are added.

**Arguments**:

| Argument | Required | Description |
| --- | --- | --- |
| `project-dir` | No | Path to the project directory (defaults to `.`) |

**Options**:

| Option | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--dry-run` | `-n` | flag | `false` | Show what would be written without making changes. Default: `false`. |
| `--format` | — | enum | `table` | Output format: `table`, `json`. Default: `table`. |

**Preconditions**:

- The project directory MUST contain at least one Copier answers file — either Copier's default singular `.copier-answers.yml` or one or more per-layer `.copier-answers.<layer>.yml` files (Copier-managed project)
- The project directory MUST NOT contain a `boilerplate.lock` file (not already adopted). If `boilerplate.lock` already exists, exit with code `3` and the message: 'Project already managed by Boilerplate. Use `boilerplate update` instead.'
- The template referenced by the discovered answers file(s) MUST be resolvable in the catalog. If the template has a `boilerplate.yml` (Boilerplate-compatible), the full composition chain is resolved. If it is a Copier-only template, a minimal lock file is written with a single layer.

**Behavior**: Reads the project's Copier answers file(s) (singular or per-layer; see [06-project-lifecycle.md §Project Adoption](06-project-lifecycle.md#part-25-project-adoption)), resolves the template in the catalog, writes `boilerplate.lock` and `.boilerplate/migrations.yml` (with `adopted` status), and prints adoption summary with next steps.

**Exit codes**: `0` on success, `1` on failure (template not found, copier-answers unreadable), `3` on validation error (already adopted, no copier-answers found).

---

### `eject`

**Usage**: `boilerplate eject [path] [options]`

Stop Boilerplate lifecycle management of a project. This is the exact inverse of [`adopt`](#adopt): it removes the Boilerplate-owned management state and leaves all rendered project files in place. After ejecting, the directory is a plain Copier project (or plain files) — `update`, `status`, and `lock verify` no longer apply, but the project is otherwise untouched.

**Arguments**:

| Argument | Required | Description |
| --- | --- | --- |
| `path` | No | Path to the project directory (defaults to `.`) |

**Options**:

| Option | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--yes` | `-y` | flag | `false` | Skip the confirmation prompt. Default: `false`. |
| `--dry-run` | `-n` | flag | `false` | List what would be removed without changing anything. Default: `false`. |
| `--format` | — | enum | `table` | Output format: `table`, `json`. Default: `table`. |

**What is removed** (Boilerplate-owned artifacts only):

- `boilerplate.lock`
- The entire `.boilerplate/` directory (e.g., `migrations.yml`, and `environment.yml` if present)

**What is kept** (not owned by Boilerplate):

- The Copier answers files (`.copier-answers.<layer>.yml`, or the legacy singular `.copier-answers.yml`) — these are Copier-owned, so an ejected project can still be managed as a plain Copier project.
- All rendered project files.
- `.prototools` and any proto-installed tools. **`eject` NEVER touches proto state.** Tool teardown is proto's job: the proto install store is shared across projects, so removing it on one project's behalf is unsafe. Use proto directly to remove tools.

**Behavior**:

- **Confirmation**: Because it deletes management state, the default (interactive) invocation prints a summary of what will be removed and prompts `Proceed? [y/N]` (see [Confirmation Contracts](#confirmation-contracts)). `--yes`/`-y` (or the global `--ci`, which implies `--yes`) skips the prompt; the summary is still printed to the operator log.
- **Idempotent**: `eject` is a no-op only when neither `boilerplate.lock` nor `.boilerplate/` is present (`env apply` can create `.boilerplate/environment.yml` with no lock, so the check keys on both). When the project has neither, `eject` emits a warning (`"No Boilerplate management state found; nothing to eject."`) and exits `0`. When either is present, it removes both `boilerplate.lock` (if any) and the entire `.boilerplate/` directory.
- **Mutating operation**: `eject` acquires the standard advisory mutex on the project before removing state (same rule as `new`, `update`, `add`, `adopt`, and `env apply`; see [06-project-lifecycle.md §Concurrency](06-project-lifecycle.md#concurrency)).
- **No recovery to stage**: `eject` is a delete, not a staged write — there is nothing to roll back or resume. A user who ejected by mistake can re-`adopt` the project to regenerate `boilerplate.lock` and `.boilerplate/migrations.yml` from the existing Copier answers. `eject` reuses none of `update`'s merge or backup machinery.

**`--dry-run`**: Prints the list of artifacts that would be removed and exits `0` without deleting anything or prompting.

**Example**:

```text
$ boilerplate eject
This will stop Boilerplate management of ./my-service and remove:
  boilerplate.lock
  .boilerplate/ (migrations.yml)

Rendered files and .copier-answers.<layer>.yml are kept. proto tools are not touched.
Proceed? [y/N] y
Ejected my-service. To resume management later: boilerplate adopt .
```

**Exit codes**: `0` on success (including the idempotent no-op when neither `boilerplate.lock` nor `.boilerplate/` is present), `1` on a filesystem or permission failure during removal (`BP_FILESYSTEM_PERMISSION`).

---

### `test`

**Usage**: `boilerplate test <template-path> [options]`

Run automated regression tests for a template using fixture directories. See §03 Template Testing for the fixture layout specification.

**Arguments**:

| Argument | Required | Description |
| --- | --- | --- |
| `template-path` | Yes | Path to the template directory to test |

**Options**:

| Flag | Short | Description |
| --- | --- | --- |
| `--fixture <name>` | — | Run only the named fixture; also scopes `--update-snapshots` to the named fixture. Default: run all discovered fixtures. |
| `--update-snapshots` | — | Overwrite `expected/` directories with current render output. Default: `false`. See `--update-snapshots` notes below. |
| `--match <glob>` | — | Only diff files matching the glob pattern against expected output (e.g., `--match "pyproject.toml"`). Non-matching files are ignored. |
| `--format {text\|json}` | — | Output format. Default: `text`. |

**`--update-snapshots` notes**: Use to create initial fixtures or update after intentional template changes. When combined with `--fixture`, only the named fixture's expected output is updated.

**`--match` notes**: Useful for large templates where only specific files need assertion (e.g., `--match "src/**/*.py"`).

**Fixture discovery**: Scans `{template-path}/tests/*/` for directories containing `answers.yml`. Each such directory is a fixture; the directory name is the fixture name.

**Composition behavior**: `boilerplate test` resolves the full composition chain (including `extends` dependencies) and renders the complete merged output. Base templates are resolved from configured sources. Use `--templates-dir` to include local base templates during development (e.g., `boilerplate test ./my-template --templates-dir ./`).

**Test execution**:

1. For each fixture, resolve the full `extends` chain and render the composed template to a temp directory using `answers.yml` as pre-seeded answers (non-interactive, no tasks)
2. Diff the rendered output against `{template-path}/tests/{name}/expected/`
3. Report pass (no diff) or fail (unified diff per differing file)

**Output**: Per-fixture pass/fail with unified diff on failure. Summary line: `N fixtures passed, M failed.`

**Exit codes**: 0 = all fixtures passed; 1 = one or more fixtures failed; 2 = configuration error (template not found, fixture malformed).

> **Tip**: Use `boilerplate validate` to check template structure before running tests. Use `boilerplate new --render-to <dir>` to inspect rendered output without creating a project.

---

### `doctor`

**Usage**: `boilerplate doctor`

Runs health checks and reports issues with remediation guidance.

**Checks**: Settings loadable, template directories exist, Copier available, Git available, catalog sources reachable, environment profiles valid, Windows `core.longpaths` enabled (Windows only), WSL2 proto binary not from Windows host (WSL2 only). In a project, `doctor` also reports each disagreement between a layer's answers file and `boilerplate.lock` ([04 §Safe Update](04-composition-engine.md#safe-update)) and each layer whose answers file lacks the key of a question of its scoped view at the recorded versions that is neither secret nor hidden ([04 §Safe Update](04-composition-engine.md#safe-update) defines hidden), as a hand-run update of the layer leaves it, and each such key that no layer records, naming the layer and the keys.

**Output** (unified check-result format):

```text
Boilerplate Doctor

  PASS  Configuration loaded
  PASS  Default templates dir exists (14 templates)
  PASS  Extra templates dir /opt/team-templates exists (8 templates)
  PASS  Git available (2.44.0)
  PASS  Copier available (9.4.1)
  FAIL  Extra templates dir /opt/legacy-templates does not exist
        -> Check BOILERPLATE_EXTRA_TEMPLATE_DIRS in your configuration

6 checks: 5 passed, 0 warnings, 1 error
```

Uses the same `PASS`/`WARN`/`FAIL` format as `validate` and `lock verify`.

**Exit codes**: `0` all checks pass (warnings OK), `1` any check fails.

---

### `init-template`

**Usage**: `boilerplate init-template <name> [directory]`

Create a minimal template skeleton in the target directory. This is the template authoring entry point.

**Arguments**:

| Argument | Required | Description |
| --- | --- | --- |
| `name` | Yes | Template name (must match `^[a-zA-Z0-9_\-]+$`) |
| `directory` | No | Target directory (defaults to `./<name>/`) |

**Behavior**: Creates the target directory (if it does not exist) containing:

- `boilerplate.yml` — minimal manifest with the provided name and version `0.1.0`
- `copier.yml` — minimal Copier configuration with a `project_name` question
- `{{ _copier_conf.answers_file }}.jinja` — answer persistence file for Copier
- A sample template file demonstrating variable substitution
- `tests/defaults/answers.yml` — sample answer file for the default test fixture, pre-populated with `project_name: "test-project"` and a comment: `# Run 'boilerplate test . --update-snapshots' to populate expected output.`
- `tests/defaults/expected/` — empty directory for snapshot output (populated by `--update-snapshots`)

The generated skeleton provides a minimum viable template that renders successfully out of the box. Each generated file MUST include explanatory inline comments.

If the target directory already exists and contains a `boilerplate.yml`, the CLI MUST exit with code `3`.

**Exit codes**: `0` on success, `3` on validation error (invalid name, directory already contains template).

---

### `env`

Manage environment profiles. The `env` group has one mutating subcommand (`env apply`, whose pipeline is owned by [§08 Provisioning Pipeline](08-environment-provisioning.md#part-4-provisioning-pipeline)) and one read-only inspector (`env status`). Each subcommand is documented below.

The `<profile-spec>` argument used by `env apply` follows the same `name` or `name@version` syntax as other template references. See [Template Argument Resolution](#template-argument-resolution).

To recover from a failed or partial provisioning, re-run `boilerplate env apply`; provisioning is idempotent and converges to the profile's declared tool set.

For background on environment profiles as a concept, see [01-overview.md](01-overview.md) (Environment Profiles).

### `env apply`

Apply an environment profile to the current project or directory.

```text
boilerplate env apply [options] <profile-spec>
```

**Arguments**:

- `<profile-spec>`: Profile name from the project's `boilerplate.yml` or a path to a standalone profile YAML file.

**Options**:

| Flag | Short | Description |
| --- | --- | --- |
| `--dry-run` | `-n` | Display the provisioning plan without applying changes. Default: `false`. |
| `--yes` | `-y` | Skip confirmation prompt. Default: `false`. |
| `--force` | `-f` | Re-install tools even if the correct version is already present. Default: `false`. |

**Behavior**: The full provisioning pipeline (resolve, plan, confirm, lock, stage, install, commit, record) is specified in [§08 Provisioning Pipeline](08-environment-provisioning.md#part-4-provisioning-pipeline). `env apply` invokes that pipeline; the CLI surface adds only argument parsing, plan display, and confirmation handling on top.

**Exit codes**: 0 (success), 1 (provisioning failure), 3 (validation error). `env apply` does NOT produce exit code 4: per [§08 Part 4 Stage 4](08-environment-provisioning.md), any installation failure triggers a full pipeline rollback to the pre-apply state, so there is no partial-install pause that requires user resolution. (For the resumable user-intervention pattern, see the `update` conflict pause: resolve, commit, rerun.)

### `env status`

**Usage**: `boilerplate env status`

Reports the current environment state by reading `.boilerplate/environment.yml` and `.protolock`.

Reports the current profile, applied timestamp, tool versions, and protolock integrity. If `proto_lock_hash` does not match the current `.protolock`, emits a WARNING.

**Exit codes**: 0 (informational, including warnings), 1 (error reading state files).

---

### `lock verify`

**Usage**: `boilerplate lock verify`

Verify that the current project state matches the lock file. Checks that template source checksums, commit hashes, and answer hashes are consistent. Intended for CI gates enforcing "no drift from template."

**Checks**:

| Check | Description |
| --- | --- |
| Lock file parseable | `boilerplate.lock` exists and parses correctly |
| Schema version supported | Lock file schema version is recognized. A lock whose major `schema_version` is newer than the tool supports is refused (fail closed). |
| Template sources accessible | Source paths/URLs for all layers are reachable |
| Checksums match | Template content checksums match lock file values |
| Commits match | Git commit hashes match lock file values (when source is a git repo) |
| Answers hash match | Each `.copier-answers.<layer>.yml` hash matches its entry in `copier_answers_file_hashes` |

Checksum comparisons are computed in git's content sense (line endings normalized before hashing), not on raw bytes: Copier's git-based update rewrites line endings of otherwise-untouched files under `core.autocrlf=true` ([ADR-015 §Verification](adr-015-idiomatic-artifacts.md#verification-2026-07-28)), so a raw-byte comparison would report false drift.

**Output** (unified check-result format):

```text
Verifying lock file integrity...

  PASS  Lock file parseable
  PASS  Schema version supported (boilerplate/lock@1)
  PASS  Template sources accessible
  PASS  Checksums match
  PASS  Commit hashes match
  FAIL  Answers hash mismatch
        -> A .copier-answers.<layer>.yml file has been modified since last update.
        -> Run: boilerplate update to reconcile.

6 checks: 5 passed, 0 warnings, 1 error
```

Uses the same `PASS`/`WARN`/`FAIL` format as `validate` and `doctor`.

**Exit codes**: `0` all checks pass, `1` any check fails (drift detected or verification error).

---

### `cache warm`

**Usage**: `boilerplate cache warm [source-name]...`

Pre-populate the local template cache from configured remote and archive sources. Useful for seeding CI build agents; the broader air-gapped story is an org-local clone or mirror of the published first-party repositories ([ADR-006](adr-006-template-distribution.md)), not this command. A wheel-bundled seed cache remains deferred pending demonstrated demand.

**Arguments**:

| Argument | Required | Description |
| --- | --- | --- |
| `source-name` | No | One or more source names to warm. If none provided, warms all configured remote and archive sources. |

**Options**:

| Option | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--force` | — | flag | `false` | Re-download even if the cache is current. Default: `false`. |

**Behavior**: For each targeted source, fetches the current template catalog and downloads template contents into the local cache. Already-cached and up-to-date sources are skipped unless `--force` is active. On completion, reports per-source status (cached templates count, time taken).

**Exit codes**: `0` = all sources warmed successfully; `1` = one or more sources failed (errors logged per source).

---

### `config`

Reserved for surfacing the per-user profile ([09 §Profile](09-settings-and-configuration.md#profile)); no command surface is specified.

---

## Shell Completions

Shell completions are handled by Typer's built-in `--install-completion` and `--show-completion` flags. No custom `completions` command is provided.

```text
boilerplate --install-completion    # Install completion for current shell
boilerplate --show-completion       # Show completion script
```

**Completion targets**:

| Context | Completions offered |
| --- | --- |
| Top-level | Command names |
| `new <TAB>` | Template names from the catalog |
| `new <template> <TAB>` | Directory paths |
| `add <TAB>` | Template names from the catalog |
| `compose <TAB>`, `graph <TAB>`, `validate <TAB>` | Template names from the catalog |
| `--format <TAB>` | `table`, `json`, `yaml`, `tree`, `wide` (context-dependent) |
| `--trust <TAB>` | `trusted`, `untrusted` |
| `--type <TAB>` | `boilerplate-enabled`, `copier-only` |
| `--section <TAB>` | `final`, `layers`, `states`, `deltas`, `stats` |
| `--category <TAB>` | Known category values from the cached catalog |
| `env apply <TAB>` | Profile names from the catalog |

Template name completions are loaded from the cached catalog. If the cache is empty or stale, completions fall back to an empty list (no network calls during completion).

---

## Developer Experience Contracts

The following contracts are cross-cutting. They apply to every command and workflow.

### Pipeline Narration

Boilerplate operations are multi-phase pipelines. Operations can take seconds to minutes. The user MUST see the pipeline progressing, not silence.

**When stdout is a TTY**:

| Phase | Output |
| --- | --- |
| Resolution | `Resolving {template-ref}...` followed by `Resolved {n} layers` |
| Composition | `Composing {n} layers...` |
| Rendering | `Rendering layer {i}/{n}: {name}@{version}...` per layer |
| Lock | `Writing lock file...` |
| Post-tasks | `Running post-creation tasks...` |

Each phase line replaces the previous (single-line progress). On completion, a summary line:

```text
Created my-project in 3.2s (2 layers, 47 files)
```

For updates:

```text
Updated my-project in 5.1s (project 0.1.0 -> 0.2.0, streamlit 0.1.0 -> 0.1.1, 12 files changed)
```

**When stdout is piped or `--quiet` is active**: No progress output. The completion summary is still written to stderr unless `--quiet` is active.

### Confirmation Contracts

Destructive or high-impact operations MUST require confirmation.

**Prompt format**: The CLI MUST:

1. Print a summary of what will happen (files modified, versions changed)
2. Print the prompt: `Proceed? [y/N]`
3. Default to **No** (capital N) — pressing Enter without input cancels
4. Accept `y`, `yes` (case-insensitive) as confirmation; anything else cancels

**`--yes` / `-y` flag**: All commands that require confirmation MUST accept `--yes` / `-y` to bypass the prompt. When `--yes` is active, the summary is still printed (to the operator log), but the prompt is skipped.

**When confirmation is required**:

| Trigger | Command | Summary content |
| --- | --- | --- |
| Any update (default behavior) | `update` | Update plan with version deltas and file impact |
| Adding a layer (default behavior) | `add` | Add plan with the layer, its version and file impact |
| Environment provisioning | `env apply` | Tools to install/upgrade |
| Stop management (state removal) | `eject` | Artifacts to remove (`boilerplate.lock`, `.boilerplate/`) |

Note: `--force` on `new` does NOT trigger confirmation — force implies consent. The `--yes` flag bypasses confirmation on `update`, `add`, `env apply`, and `eject`.

All `update`, `add`, `env apply`, and `eject` invocations show a plan and prompt for confirmation by default. `--dry-run` suppresses the prompt (plan only). `--yes` suppresses the prompt (plan + apply).

### Post-Action Guidance

After completing an operation, the CLI MUST print contextual next steps. Guidance sources, in display order:

1. **Default**: Always `cd {destination}`. `uv sync` follows it only when the template's setup tasks were skipped (`--no-tasks`); otherwise the tasks already installed dependencies and Next steps lists only what is left to do.
2. **Profile-derived**: If the template declares `requires_profile`, include `boilerplate env apply`.
3. **Template-declared**: `post_create_message` from `boilerplate.yml`, accumulated from all layers in topological order, labeled "From the template author:".
4. **`Tip:` block**: Save-answers hint for CI reproducibility (suppressed when `--answers` or `--ci` was used).

Template-declared guidance is informational only — MUST NOT execute automatically.

**Example (`new`)**:

```text
Created my-project in 3.2s (2 layers, 47 files)

Next steps:
  cd my-project

From the template author:
  This template uses FastAPI. Start the dev server with:
  uvicorn src.main:app --reload

Tip: Save your answers for CI reproducibility:
  boilerplate new fastapi my-project --save-answers answers.yml --non-interactive
```

**After `add`**: Show the layer added and the changed files list, then "Next steps:" (`git diff`, review, commit). The result is uncommitted.

**After `update`**: Show changed files list, then "Next steps:" (`git diff`, `uv run pytest`). When conflicts are present, "Action required:" replaces "Next steps:" with resolution instructions (resolve and commit, then rerun `boilerplate update`; `git reset` and then `git stash --include-untracked` set the partial update aside).

### Answer Presets

An **answer preset** is a YAML file that supplies answers to template questions declaratively, enabling reproducible project creation in CI/CD pipelines and scripts.

**CLI flags** (available on `new`, `update`, and `add`):

| Option | Short | Type | Description |
| --- | --- | --- | --- |
| `--answers <path>` | `-a` | path | YAML file containing question answers |
| `--set key=value` | `-s` | string | Inline answer override for scalar values (repeatable) |

**Precedence**: `--set` values take precedence over `--answers` values, which take precedence over question defaults. Prefer `--answers` for structured, multi-field, or cross-platform scenarios; use `--set` only for simple scalar overrides.

**Answer preset format**:

```yaml
# answers.yml
project_name: "my-service"
description: "Order processing microservice"
dependencies:
  - fastapi
  - pydantic
author_name: "Platform Team"
```

**Behavior**:

- If `--answers` is provided without `--non-interactive`, the user is prompted for questions NOT present in the file (partial answers)
- If `--answers` is provided WITH `--non-interactive`, unanswered questions use their declared defaults
- Answer presets MUST NOT contain underscore-prefixed keys (Copier directives); if encountered, warn and ignore
- Answer presets MUST be pure data (YAML maps). No Jinja2 expressions, no executable content.

### Interactive Prompting Contract

Boilerplate delegates prompting to Copier, but composition means the user faces a *merged* questionnaire from multiple layers.

**Principles**:

1. **One pass**: The user answers all questions once, on the first layer. Subsequent layers reuse answers silently.
2. **No surprises**: The merged questionnaire is the union of all layers' questions. The user sees one flat list, not a per-layer interrogation.
3. **Validation is immediate**: If a question declares `choices`, Copier validates the answer before moving to the next question. Invalid input is re-prompted.
4. **Partial answers merge cleanly**: When `--answers` provides some values and the mode is interactive, only unanswered questions are prompted. Answered questions are shown as a summary before prompting begins:

```text
Using answers from answers.yml:
  project_name: "my-service"
  author_name: "Platform Team"

Remaining questions:
  description [A new Python project.]: _
```

**Questionnaire ordering**: Questions from base templates first (in topological order, dependencies before dependents), then questions contributed by the root template. Within each group, declaration order from `copier.yml` is preserved.

---

## UX Conventions

### Output Display

| Message type | When used |
| --- | --- |
| `info` | Informational progress and results |
| `success` | Confirmation of a completed operation |
| `error` | Failure condition; always to stderr |
| `warning` | Non-fatal issue the user should know about |

Errors MUST be printed to stderr. All other output MUST go to stdout. This ensures shell pipelines work correctly.

### Terminal vs. Pipe Detection

The CLI MUST detect whether stdout is a terminal. When outputting to a pipe or file:

- No color codes
- No progress spinners
- Plain text only

When outputting to a terminal, rich formatting (color, tables, tree) is permitted.

### Quiet Mode

When `--quiet` is active, the command MUST produce no output to stdout under any normal condition. Only error messages (to stderr) are permitted.

**Interaction with `--format json`**: `--quiet` and `--format json` are mutually exclusive. If both are provided, the CLI MUST exit with code `3` (`VALIDATION_ERROR`) and the message: `Cannot combine --quiet (suppress output) with --format json (structured output). Use --format json without --quiet for machine-readable output, or --quiet without --format for silent operation.`

### Verbose Mode

When `--verbose` is active:

- Debug-level log messages are printed
- Debug info about resolution, composition, and rendering steps is logged

`--verbose` controls log verbosity only. To expand the `list` output columns, use `--format wide`.

### Terminal Accessibility

This section defines the universal accessibility contract for all CLI output. Individual command sections inherit these rules; per-command accessibility notes (e.g., `graph` tree rendering) supplement but do not override them.

1. **`NO_COLOR` contract**: When the `NO_COLOR` environment variable is set (to any value), the CLI MUST NOT emit ANSI escape codes or Unicode characters outside the printable ASCII range (U+0020–U+007E). This applies to all output: errors, progress, check results, tree rendering, and table formatting. The `--color never` flag has the same effect.

2. **Color is never the sole differentiator**: All status indicators MUST use text labels (`PASS`, `WARN`, `FAIL`, `Modified`, `Added`, `Removed`, `Conflict`) that carry meaning independently of color. Color is a supplementary enhancement in TTY mode, not the primary signal. This ensures usability for users with color vision deficiencies (e.g., deuteranopia).

3. **Progress output**: When stdout is not a TTY, or when `NO_COLOR` is set, progress output MUST use append mode (newline-terminated lines). Carriage-return overwrite (`\r`) MUST NOT be used in these contexts, as it is hostile to screen readers and log file consumers.

4. **`--color` flag**: The `--color auto|always|never` global flag provides explicit control over color output. `auto` (default) uses TTY detection and respects `NO_COLOR`. `always` forces color on (useful when piping to `less -R`). `never` forces color off. When `--color` is provided, it takes precedence over `NO_COLOR`.

5. **`BOILERPLATE_ACCESSIBLE` environment variable**: When enabled, activates all accessibility accommodations as a single toggle. It follows the same truthiness rule as the other `BOILERPLATE_*` boolean env vars (see the environment variable equivalents note in [Global Options](#global-options)): the value is trimmed of surrounding whitespace, then enabled when the trimmed value is non-empty and not `0` or `false` (case-insensitive). Equivalent to setting `NO_COLOR=1` plus: append-mode progress (no carriage-return overwrite), `PASS`/`WARN`/`FAIL` text labels (no Unicode symbols), and `TERM=dumb`-compatible output. This variable exists so that screen reader users and accessibility-focused workflows can enable the full suite of accommodations without remembering individual settings. When `BOILERPLATE_ACCESSIBLE` is active, `--color auto` resolves to `never`.

---

## Error Handling

All CLI commands MUST handle `BoilerplateError` subclasses by:

1. Printing a human-readable error message to stderr
2. Exiting with the appropriate exit code per [02-data-models.md §Error Hierarchy](02-data-models.md#error-hierarchy)

Each exception type maps to one or more stable `BP_*` error codes defined in [07-operational-quality.md](07-operational-quality.md). The exception hierarchy is the implementation mechanism; the `BP_*` codes are the stable public contract surfaced to the user. Unrecognized exceptions outside the `BoilerplateError` hierarchy MUST exit with code `1` (`FAILURE`).

Errors MUST NOT leak internal stack traces to the user by default. When `--verbose` is active, additional context MAY be shown.

---

## Exit Code Reference

Exit codes are defined in [02-data-models.md](02-data-models.md). Scripts SHOULD treat exit code 4 (`ACTION_REQUIRED`) as distinct from failure — it means user intervention is needed (e.g., merge conflict resolution).

---

## Flag Reference Summary

The following table summarizes flag availability across commands. **Global flags** (`--verbose`, `--quiet`, `--help`, `--version`, `--templates-dir`, `--format`, `--offline`) apply to all commands and are omitted from this table.

| Flag | `new` | `update` | `add` | `adopt` | `eject` | `list` | `compose` | `graph` | `validate` | `status` | `doctor` | `init-template` | `test` | `env` | `lock` | `cache` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `--force` | X | | | | | | | | | | | | | X | | X |
| `--non-interactive` | X | X | X | | | | | | | | | | | | | |
| `--skip-answered` | | X | | | | | | | | | | | | | | |
| `--dry-run` / `-n` | X | X | X | X | X | | | | | | | | | X | | |
| `--answers` | X | X | X | | | | | | | | | | | | | |
| `--set` | X | X | X | | | | | | | | | | | | | |
| `--save-answers` | X | | | | | | | | | | | | | | | |
| `--no-tasks` | X | X | X | | | | | | | | | | | | | |
| `--allow-extensions` | X | X | X | | | | | | | | | | | | | |
| `--allow-tasks` | X | X | X | | | | | | | | | | | | | |
| `--allow-untrusted` | X | X | X | | | | | | | | | | | | | |
| `--template-source` | | X | X | | | | | | | | | | | | | |
| `--yes` / `-y` | X | X | X | | X | | | | | | | | | X | | |
| `--git-init` | X | | | | | | | | | | | | | | | |
| `--render-to` | X | | | | | | | | | | | | | | | |
| `--target-version` / `-t` | | X | | | | | | | | | | | | | | |
| `--category` | | | | | | X | | | | | | | | | | |
| `--tag` (repeatable) | | | | | | X | | | | | | | | | | |
| `--trust` | | | | | | X | | | | | | | | | | |
| `--type` | | | | | | X | | | | | | | | | | |
| `--all-versions` | | | | | | X | | | | | | | | | | |
| `--include-archived` | | | | | | X | | | | | | | | | | |
| `--source` | | | | | | X | | | | | | | | | | |
| `--refresh` | | | | | | X | | | | | | | | | | |
| `--questions` / `-Q` | | | | | | | X | | | | | | | | | |
| `--section` (repeatable) | | | | | | | X | | | | | | | | | |
| `--all` | | | | | | | X | | | | | | | | | |
| `--stats` | | | | | | | X | | | | | | | | | |
| `--output` / `-o` | | | | | | | X | | | | | | | | | |
| `--tree` | | | | | | | | X | | | | | | | | |
| `--strict` | | | | | | | | | X | | | | | | | |
| `--fixture` | | | | | | | | | | | | | X | | | |
| `--match` | | | | | | | | | | | | | X | | | |
| `--update-snapshots` | | | | | | | | | | | | | X | | | |

**Short flag assignment**: `-f` is assigned to `--force` (on `new` and `env apply`), matching universal CLI convention (`rm -f`, `cp -f`, `docker rm -f`). `--format` uses long-form only.

---

## Constraints and Invariants

1. Every command that runs longer than 1 second MUST show progress when stdout is a TTY.
2. Every command MUST support `--format json` for machine-readable output.
3. Every destructive or high-impact action MUST support `--yes` / `-y` to bypass confirmation.
4. Post-action guidance MUST be informational only — never auto-execute commands on the user's behalf.
5. Shell completions MUST NOT make network calls.
6. `doctor` and `status` MUST NOT modify any state.
7. `validate` MUST work without a project context (it validates a template directory, not a project).
8. Answer presets MUST be pure data (YAML maps). No Jinja2 expressions, no executable content.
9. `--force` and `--non-interactive` are independent. Neither implies the other.
10. Destination for `new` MUST be explicit or interactively prompted. No implicit defaults.

---

## CI/CD Quick Reference

Common invocation patterns for automated environments:

| Scenario | Command |
| --- | --- |
| Create project, no interaction | `boilerplate new template dest --ci` |
| Create project, no interaction, env var instead of a flag (POSIX shells) | `BOILERPLATE_CI=1 boilerplate new template dest` |
| Create project, no interaction, env var instead of a flag (PowerShell) | `$env:BOILERPLATE_CI = "1"; boilerplate new template dest` |
| Create with answers file | `boilerplate new template dest --ci --answers answers.yml` |
| Create from an untrusted source, tasks allowed | `boilerplate new template dest --ci --allow-tasks` |
| Update project | `boilerplate update --ci` |
| Add a template layer | `boilerplate add template --ci` |
| Validate template | `boilerplate validate ./my-template/` |
| JSON output for scripting | `boilerplate list --format json` |
| Dry-run update | `boilerplate update --dry-run --format json` |
