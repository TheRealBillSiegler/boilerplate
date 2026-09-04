# Troubleshooting

## Installation problems

### Error: `boilerplate` command not found

The installer places the `boilerplate` executable in a user-local bin directory that may not be on your PATH yet.

<!-- markdownlint-disable MD046 -->
=== "Windows"

    - **Problem:** `boilerplate` (or `uv`) is not recognized.
    - **Cause:** PATH not refreshed in the current terminal, or `%USERPROFILE%\.local\bin` is not on PATH.
    - **Solution:**
        1. Close and reopen PowerShell (or the VS Code terminal) to pick up PATH changes written by the installer.
        2. If still not found, open **Start → Edit the system environment variables → Environment Variables** and check or add `%USERPROFILE%\.local\bin` to `Path` under *User variables*.
    - **Verify:**
        ```powershell
        boilerplate version
        Get-Command boilerplate
        ```

=== "macOS / Linux"

    - **Problem:** `boilerplate` (or `uv`) is not found.
    - **Cause:** Shell session hasn't reloaded PATH, or `~/.local/bin` is not on PATH.
    - **Solution:**
        1. Reload your login shell (`exec "$SHELL" -l`) or open a new terminal.
        2. If still not found, confirm `~/.local/bin` is on PATH: `echo $PATH | tr ':' '\n' | grep local`. If missing, add `export PATH="$HOME/.local/bin:$PATH"` to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) and reload.
    - **Verify:**
        ```bash
        command -v boilerplate
        boilerplate version
        ```
<!-- markdownlint-enable MD046 -->

### Error: Python version not supported

Boilerplate requires Python 3.12+. Update your Python installation.

## Template issues

### Error: Template not found

Verify available templates:

```bash
boilerplate list
```

### Error: Permission denied

Ensure you have write permissions to the destination directory.

## Development environment issues

### VS Code not detecting the Python interpreter

Symptoms include a missing interpreter right after cloning or generating a project, and lint or type errors that persist after a fix. See [VS Code setup: interpreter not detected](environment/vscode.md#troubleshooting-the-interpreter-isnt-detected) for the fix.

### Ruff not formatting automatically

Check VS Code settings include:

```json
{
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

!!! tip
    Sometimes, simply closing and reopening VS Code can resolve many glitches.

## Profile and render errors

Boilerplate's render pipeline emits phase-tagged error codes (`BP_RENDER_*`, `BP_INPUT_*`) for problems around destination state, required answers, and interactive-prompt failures. The code appears as a bracketed suffix on the `Error:` line alongside a remediation hint.

### `BP_INPUT_FORCE_REQUIRED` — non-interactive render requires `--force`

Destination directory exists and non-interactive mode can't safely overwrite without your explicit consent. Re-run with `--force` (or pick an empty destination).

### `BP_INPUT_ANSWERS_MISSING` — non-interactive render cannot proceed

A template question has no `default:` and you supplied no value for it in non-interactive mode. The error message names the specific fields, e.g.:

```text
Error: Non-interactive render cannot proceed — these questions have no default and no supplied value: project_name, author_email.   [BP_INPUT_ANSWERS_MISSING]
  Hint: Supply the missing values with --data key=value or --data-file <path> (a YAML mapping), add defaults for these questions in the template's copier.yml, or run without --ci / --non-interactive to prompt interactively.
```

Three ways to fix, in priority order:

1. **Template user, one-off** — pass the missing answers directly: `--data project_name=my-app --data author_email=me@example.com`, or point `--data-file` at a YAML file mapping question name to answer. Values supplied this way are forced (never prompted for) and satisfy this pre-flight without touching the template.
2. **Template author** — add `default:` to the question, ideally a computed default like `default: "{{ _folder_name }}"` so the value derives from invocation context. See [template authoring](templates-hub/authoring.md) for patterns.
3. **Template user, interactive** — run without `--ci` / `--non-interactive` and answer the prompts, or re-render the project later with the answers filled in.

### `BP_INPUT_DATA_INVALID` — `--data`/`--data-file` could not be parsed

Something about the forced-answers input itself failed to parse, ahead of any render attempt:

- A `--data` entry has no `=`, or its key is empty or whitespace-only — it must be `key=value` (repeatable for multiple answers).
- A key from either `--data` or `--data-file` starts with an underscore — those names are reserved by Copier for its own directives.
- The `--data-file` path does not exist, cannot be read, or is not valid UTF-8.
- The `--data-file` content is not syntactically valid YAML.
- The `--data-file` content parses to something other than a YAML mapping (e.g. a list or a bare scalar).
- A `--data-file` key is not a string — YAML reads unquoted `on`/`off`/`yes`/`no` and bare numbers as booleans or numbers rather than the literal text, so the intended key never matches a question name.

```text
Error: Malformed --data entry 'project_name': expected key=value.   [BP_INPUT_DATA_INVALID]
  Hint: Use --data key=value (repeatable) for individual answers, or --data-file <path> for a UTF-8 YAML mapping of question name to answer.
```

Fix the flag or file and re-run; nothing is rendered when this error fires.

### `BP_INPUT_TTY_REQUIRED` — interactive render without a terminal

`boilerplate new` was invoked in interactive mode (the default) but stdin is not a terminal — typical in CI pipelines, piped input, scripted shells, and `< NUL` redirection on Windows (which the console API rejects even though it looks like a character device). Prompts can never be answered there, so the render fails fast before Copier starts. Pass `--non-interactive` or `--yes` to render with defaults (or use the global flag: `boilerplate --ci new ...` — `--ci` precedes the subcommand), or run from an interactive terminal. `--dry-run` is exempt: it never prompts, so it works piped.

For a fleet of CI configs or scripts that invoke `boilerplate` multiple times without owning every call site, set `BOILERPLATE_NON_INTERACTIVE=1` or `BOILERPLATE_CI=1` once in the environment instead of threading the flag through each invocation — they bypass this guard exactly like their flag equivalents. The generic `CI` environment variable has no effect here; see [05-cli-reference.md §Global Options](design/05-cli-reference.md#global-options).

### `BP_RENDER_PROMPT_FAILED` — environment cannot show interactive prompts

Copier attempted to display a prompt but the terminal can't host prompt_toolkit's output backend. This happens in:

- Git Bash pseudo-TTYs on Windows (TERM=xterm-256color + no Win32 console)
- Docker entrypoints without `-it`
- Editor-embedded shells
- Windows CI runners without a real console buffer

Either run from a real terminal (PowerShell, cmd.exe, Linux tty, or a Docker container with `-it`) or pass `--ci` along with values that satisfy every question so no prompt is needed.

### `BP_RENDER_USER_CANCELLED` — cancelled at a prompt

You pressed Ctrl+C while `boilerplate new` was showing an interactive prompt. The render stops immediately and exits with code `130` (the same code every other Ctrl+C in the CLI produces); no internals or collected answers are printed. Re-run `boilerplate new` to try again, or pass `--yes`/`--non-interactive` with answers for every question to skip prompting entirely.

## General troubleshooting

For persistent issues:

1. **Restart your development environment** (VS Code, terminal session)
2. **Check for conflicting settings** in VS Code workspace or user settings
3. **Run commands via `uv run`** (e.g., `uv run pytest`) rather than relying on a manually activated virtual environment
4. **Review the logs** — re-run with `--verbose` (or set `BOILERPLATE_DEBUG=1`) for debug-level output.
5. **Check file permissions** for the project directory

If problems persist, see the [FAQ](faq.md) or report an issue on GitHub.
