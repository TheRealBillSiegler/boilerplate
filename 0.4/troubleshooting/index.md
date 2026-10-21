# Troubleshooting

## Installation problems

### Error: `boilerplate` command not found

The installer places the `boilerplate` executable in a user-local bin directory that may not be on your PATH (the list of folders your shell searches for commands) yet.

- **Problem:** `boilerplate` (or `uv`) is not recognized.

- **Cause:** PATH not refreshed in the current terminal, or `%USERPROFILE%\.local\bin` is not on PATH.

- **Solution:**

  1. Close and reopen PowerShell (or the VS Code terminal) to pick up PATH changes written by the installer.
  1. If still not found, open **Start → Edit the system environment variables → Environment Variables** and check or add `%USERPROFILE%\.local\bin` to `Path` under *User variables*.

- **Verify:**

  ```powershell
  boilerplate --version
  Get-Command boilerplate
  ```

- **Problem:** `boilerplate` (or `uv`) is not found.

- **Cause:** Shell session hasn't reloaded PATH, or `~/.local/bin` is not on PATH.

- **Solution:**

  1. Reload your login shell (`exec "$SHELL" -l`) or open a new terminal.
  1. If still not found, confirm `~/.local/bin` is on PATH: `echo $PATH | tr ':' '\n' | grep local`. If missing, add `export PATH="$HOME/.local/bin:$PATH"` to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) and reload.

- **Verify:**

  ```bash
  command -v boilerplate
  boilerplate --version
  ```

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

Symptoms include a missing interpreter right after cloning or generating a project, and lint or type errors that persist after a fix. See [VS Code setup: interpreter not detected](https://therealbillsiegler.github.io/boilerplate/0.4/environment/vscode/#troubleshooting-the-interpreter-isnt-detected) for the fix.

### Ruff not formatting automatically

Symptoms include Python files saving without Ruff's formatting or fixes applied. See [VS Code setup: Ruff not formatting automatically](https://therealbillsiegler.github.io/boilerplate/0.4/environment/vscode/#troubleshooting-ruff-not-formatting-automatically) for the fix.

### Tests not discovered or not running in VS Code

Symptoms include the Test Explorer showing no tests, or `uv run pytest` passing while VS Code reports none. See [VS Code setup: tests not discovered](https://therealbillsiegler.github.io/boilerplate/0.4/environment/vscode/#troubleshooting-tests-not-discovered) for the fix.

## Profile and render errors

Boilerplate's render pipeline emits phase-tagged error codes (`BP_RENDER_*`, `BP_INPUT_*`) for problems around destination state, required answers, and interactive-prompt failures. The code appears as a bracketed suffix on the `Error:` line alongside a remediation hint; see [Error codes](https://therealbillsiegler.github.io/boilerplate/0.4/cli/#error-codes) for the fix for each.

- [`BP_INPUT_DEST_REQUIRED`](https://therealbillsiegler.github.io/boilerplate/0.4/cli/#error-codes) — non-interactive render names no destination.
- [`BP_INPUT_ANSWERS_MISSING`](https://therealbillsiegler.github.io/boilerplate/0.4/cli/#error-codes) — non-interactive render cannot proceed: a question has no default and no supplied value.
- [`BP_INPUT_DATA_INVALID`](https://therealbillsiegler.github.io/boilerplate/0.4/cli/#error-codes) — `--data`/`--data-file` could not be parsed.
- [`BP_INPUT_TTY_REQUIRED`](https://therealbillsiegler.github.io/boilerplate/0.4/cli/#error-codes) — interactive render without a terminal.
- [`BP_RENDER_PROMPT_FAILED`](https://therealbillsiegler.github.io/boilerplate/0.4/cli/#error-codes) — environment cannot show interactive prompts.
- [`BP_RENDER_USER_CANCELLED`](https://therealbillsiegler.github.io/boilerplate/0.4/cli/#error-codes) — cancelled at a prompt.
- [`BP_CONFIG_PROFILE_INVALID`](https://therealbillsiegler.github.io/boilerplate/0.4/cli/#error-codes) — `profile.toml` isn't valid TOML or a section isn't a table.

## General troubleshooting

For persistent issues:

1. **Restart your development environment** (VS Code, terminal session)
1. **Check for conflicting settings** in VS Code workspace or user settings
1. **Run commands via `uv run`** (e.g., `uv run pytest`) rather than relying on a manually activated virtual environment
1. **Review the logs** — re-run with `--verbose` (or set [`BOILERPLATE_DEBUG`](https://therealbillsiegler.github.io/boilerplate/0.4/cli/#environment-variables)) for debug-level output.
1. **Check file permissions** for the project directory

If problems persist, see the [FAQ](https://therealbillsiegler.github.io/boilerplate/0.4/faq/index.md) or [report a bug](https://therealbillsiegler.github.io/boilerplate/0.4/governance/contributing/#reporting-bugs-and-requesting-features).
