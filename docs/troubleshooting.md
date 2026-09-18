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

Symptoms include Python files saving without Ruff's formatting or fixes applied. See [VS Code setup: Ruff not formatting automatically](environment/vscode.md#troubleshooting-ruff-not-formatting-automatically) for the fix.

### Tests not discovered or not running in VS Code

Symptoms include the Test Explorer showing no tests, or `uv run pytest` passing while VS Code reports none. See [VS Code setup: tests not discovered](environment/vscode.md#troubleshooting-tests-not-discovered) for the fix.

## Profile and render errors

Boilerplate's render pipeline emits phase-tagged error codes (`BP_RENDER_*`, `BP_INPUT_*`) for problems around destination state, required answers, and interactive-prompt failures. The code appears as a bracketed suffix on the `Error:` line alongside a remediation hint; see [Error codes](cli.md#error-codes) for the fix for each.

- [`BP_INPUT_DEST_REQUIRED`](cli.md#error-codes) — non-interactive render names no destination.
- [`BP_INPUT_ANSWERS_MISSING`](cli.md#error-codes) — non-interactive render cannot proceed: a question has no default and no supplied value.
- [`BP_INPUT_DATA_INVALID`](cli.md#error-codes) — `--data`/`--data-file` could not be parsed.
- [`BP_INPUT_TTY_REQUIRED`](cli.md#error-codes) — interactive render without a terminal.
- [`BP_RENDER_PROMPT_FAILED`](cli.md#error-codes) — environment cannot show interactive prompts.
- [`BP_RENDER_USER_CANCELLED`](cli.md#error-codes) — cancelled at a prompt.
- [`BP_CONFIG_PROFILE_INVALID`](cli.md#error-codes) — `profile.toml` isn't valid TOML or a section isn't a table.

## General troubleshooting

For persistent issues:

1. **Restart your development environment** (VS Code, terminal session)
2. **Check for conflicting settings** in VS Code workspace or user settings
3. **Run commands via `uv run`** (e.g., `uv run pytest`) rather than relying on a manually activated virtual environment
4. **Review the logs** — re-run with `--verbose` (or set [`BOILERPLATE_DEBUG`](cli.md#environment-variables)) for debug-level output.
5. **Check file permissions** for the project directory

If problems persist, see the [FAQ](faq.md) or [report a bug](governance/contributing.md#reporting-bugs-and-requesting-features).
