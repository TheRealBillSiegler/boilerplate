# Boilerplate CLI reference

Use the Boilerplate CLI to scaffold projects, inspect compositions, and list templates. See also [CLI Examples](cli-examples.md) for common workflows.

::: mkdocs-typer
     :module: boilerplate.cli.cli
     :command: app
     :prog_name: boilerplate
     :depth: 1

## Option notes

Detail cut from an option's own help text to keep it short.

| Option | Note |
| --- | --- |
| `--color auto` | Colors output only when stdout is a terminal, and honors `NO_COLOR`. |
| `list --format wide` | Adds each template's path as a column. |
| `new --format json` | One JSON object with `template`, `destination`, and `layers`; `--dry-run` adds `dry_run: true`. |

## Environment variables

Every environment variable the CLI reads. The generic `CI` variable is never read — only the `BOILERPLATE_`-prefixed flags below switch modes. `BOILERPLATE_CI`, `BOILERPLATE_NON_INTERACTIVE`, and `BOILERPLATE_ACCESSIBLE` are on for any value except unset, empty, `0`, or `false` (case-insensitive); `NO_COLOR` is on by mere presence, any value included; the `Settings`-parsed variables below accept `1/0`, `true/false`, `yes/no`, `on/off`, and exit 2 (CONFIG_ERROR) on anything else. The `Settings` variables are also read from a `.env` file in the working directory. `PYTHONIOENCODING` is forced to `utf-8` while a template renders and restored afterward — it's not read as a setting.

| Variable | Effect | Where it's read |
| --- | --- | --- |
| `BOILERPLATE_CI` | Same as the global `--ci` flag: forces CI mode (non-interactive; post-generation tasks still run unless `--no-tasks` is passed) and one-JSON-object-per-event logs on stderr. | `boilerplate.cli.cli` |
| `BOILERPLATE_NON_INTERACTIVE` | Same as `boilerplate new --non-interactive`: renders without prompting. | `boilerplate.cli.commands.new` |
| `BOILERPLATE_ACCESSIBLE` | Same as `--color never`: forces color-free output. | `boilerplate.cli.display.core` |
| `NO_COLOR` | The standard color-disable convention; disables console color and switches log output from Rich to one JSON object per event. | `boilerplate.cli.display.core`, `boilerplate.logging_config` |
| `BOILERPLATE_DEBUG` | Same as `--verbose` when `--verbose` isn't passed: sets DEBUG-level logging. | `boilerplate.settings.Settings`, applied in `boilerplate.cli.cli` |
| `BOILERPLATE_REQUEST_ID` | Correlation ID attached to every structured log line for the invocation; auto-generated once per run when unset. | `boilerplate.logging_config` |
| `BOILERPLATE_DEFAULT_TEMPLATES_DIR` | Overrides the bundled templates directory searched first. | `boilerplate.settings.Settings` |
| `BOILERPLATE_EXTRA_TEMPLATE_DIRS` | Adds directories searched after the default, as a JSON array: `["C:/tpls","D:/more"]`. | `boilerplate.settings.Settings` |
| `BOILERPLATE_LOG_DIR`, `BOILERPLATE_FILE_LOGGING_ENABLED` | Parsed and validated at startup (an invalid value exits 2); no command consumes them yet. | `boilerplate.settings.Settings` |
| `APPDATA` | Locates the config directory holding `profile.toml` on Windows (`%APPDATA%\boilerplate\`). | `boilerplate.settings.paths` |
| `XDG_CONFIG_HOME` | Locates the config directory holding `profile.toml` on POSIX (`$XDG_CONFIG_HOME/boilerplate/`, falling back to `~/.config/boilerplate/`). | `boilerplate.settings.paths` |

## Exit codes

Every command exits with one of six codes (defined in `boilerplate.constants.ExitCode`):

| Code | Name | Meaning |
| --- | --- | --- |
| 0 | SUCCESS | Command completed. |
| 1 | FAILURE | Unexpected error. |
| 2 | CONFIG_ERROR | Configuration could not be loaded. |
| 3 | VALIDATION_ERROR | Input failed validation (an unknown command or option, bad answers, missing TTY, conflicting options). |
| 4 | ACTION_REQUIRED | Recoverable pause; user intervention needed. Defined in the taxonomy but not yet produced by any shipped command — its first producer will be the planned `update` conflict pause. |
| 130 | USER_CANCELLED | Cancelled at a prompt (Ctrl+C). |

`boilerplate validate <template_dir>` reports a template that fails its own checks (missing or malformed `boilerplate.yml`/`copier.yml`, duplicate keys, schema errors, or a `--strict` warning) on exit code 1 (FAILURE), not 3 — exit 3 there is reserved for a malformed invocation, namely a `template_dir` argument that isn't a directory at all.

## Error codes

Every `BP_*` code in the shipped exception hierarchy. A code the error boundary can render but no command produces is marked as such. The code appears as a bracketed suffix on the `Error:` line (e.g. `[BP_INPUT_DATA_INVALID]`), usually with a `Hint:` line giving the fix.

| Code | When it's raised | Fix |
| --- | --- | --- |
| `BP_CONFIG_DIR_INVALID` | A configured template directory (the bundled default, `--templates-dir`, or a `BOILERPLATE_EXTRA_TEMPLATE_DIRS` entry) doesn't exist, isn't a directory, or can't be read. | Point the option or environment variable at a directory that exists and is readable. |
| `BP_RESOLVE_TEMPLATE_NOT_FOUND` | Defined and rendered by the error boundary, but no shipped command raises it — a missing template surfaces as `BP_RESOLVE_DEP_NOT_FOUND`. | — |
| `BP_VERSION_INVALID` | Reserved for a version string that fails PEP 440 validation. Defined in the exception hierarchy but not yet produced by any shipped command — an invalid version inside a template reference currently surfaces as `BP_INPUT_SPECIFIER_INVALID` instead. | — |
| `BP_RENDER_DEST_NOT_EMPTY` | Defined but not produced by any shipped command; without `--force`, Copier's own per-file conflict handling applies. | — |
| `BP_INPUT_FORCE_REQUIRED` | Defined but not produced by any shipped command. | — |
| `BP_INPUT_SPECIFIER_INVALID` | A `name@version` template reference is malformed — an invalid name, or a version segment that isn't PEP 440 compliant, including inside an `extends` reference. | Use the format `name` or `name@version`. |
| `BP_RESOLVE_METADATA_INVALID` | A template's `boilerplate.yml`/`copier.yml` is invalid: schema errors, or a `name@version` tag that disagrees with the directory's declared metadata. | Fix the metadata file; `boilerplate validate <template_dir>` reports which check failed. |
| `BP_INPUT_ANSWERS_MISSING` | Non-interactive render cannot proceed: a template question has no `default:` and you supplied no value for it. The error message names the specific fields. | In priority order: pass `--data key=value` (repeatable, never prompted for) or `--data-file <path>` (a YAML mapping) for the missing answers; or have the template author add a `default:` (ideally computed, e.g. `default: "{{ _folder_name }}"` — see [template authoring](templates-hub/authoring.md)); or drop `--ci`/`--non-interactive` and answer the prompts. |
| `BP_INPUT_DATA_INVALID` | `--data`/`--data-file` failed to parse ahead of any render attempt: a `--data` entry with no `=`; an empty or whitespace-only key; a key starting with `_` (Copier's reserved namespace); a `--data-file` path that doesn't exist or isn't UTF-8; content that isn't valid YAML or isn't a mapping; or a data-file key that isn't a string (YAML reads unquoted `on`/`off`/`yes`/`no`/bare numbers as non-string values). | Fix the flag or file and re-run; nothing is rendered when this error fires. |
| `BP_INPUT_TTY_REQUIRED` | `boilerplate new` was invoked in interactive mode (the default) but stdin isn't a terminal — typical in CI pipelines, piped input, scripted shells, and `< NUL` redirection on Windows. | Pass `--non-interactive` (or the global `--ci`, which precedes the subcommand: `boilerplate --ci new …`), or set [`BOILERPLATE_NON_INTERACTIVE`/`BOILERPLATE_CI`](#environment-variables) once for a fleet of call sites; or run from an interactive terminal. `--dry-run` is exempt — it never prompts. |
| `BP_INPUT_DEST_REQUIRED` | `boilerplate new` ran with `--non-interactive` or `--ci` and no destination argument; the current directory is never assumed. | Pass the destination as the second argument: `boilerplate new <template> <destination>`. Interactively, the CLI prompts for it. |
| `BP_RENDER_PROMPT_FAILED` | Copier's prompt machinery can't display in the current terminal: Git Bash pseudo-TTYs on Windows, Docker entrypoints without `-it`, editor-embedded shells, or Windows CI runners without a real console buffer. | Run from a real terminal (PowerShell, cmd.exe, a Linux tty, or Docker with `-it`), or pass `--ci` with values that satisfy every question. |
| `BP_RENDER_USER_CANCELLED` | You pressed Ctrl+C while `boilerplate new` was showing an interactive prompt; exits `130`, the same code every Ctrl+C in the CLI produces. The render stops without printing collected answers or template paths. | Re-run `boilerplate new`, or pass `--non-interactive` with answers for every question to skip prompting entirely. |
| `BP_RESOLVE_DEP_NOT_FOUND` | An `extends` reference (or a versioned template reference) names a template that can't be resolved in the catalog. | Run `boilerplate list` and correct the reference. |
| `BP_GRAPH_CYCLE` | The dependency graph formed by `extends` references contains a cycle, including a template that extends itself. | Remove the cyclical `extends` reference. |
| `BP_RESOLVE_VERSION_CONFLICT` | The same template name resolves to two different versions within one dependency graph. | Align all references to a single exact version. |
| `BP_RESOLVE_MERGE_CONFLICT` | Layers provide incompatible values for the same question during merge — mismatched types, or no value/version supplied at all. | Reconcile the conflicting question across the layers' `copier.yml` files. |
| `BP_CONFIG_PROFILE_INVALID` | `profile.toml` exists but isn't valid TOML, or its `[defaults]`/`[templates.<name>]` section isn't a table. | Fix the file's TOML syntax or table structure; the error message names the specific section. |

## Where next

- [Examples](cli-examples.md) — copy-pastable commands for common tasks.
- [Customization](customization.md) — pre-filled answers and extra template layers.
- [Merging and precedence rules](reference/merging.md) — what composed output means.
