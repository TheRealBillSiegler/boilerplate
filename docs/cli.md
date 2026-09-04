# Boilerplate CLI reference

Use the Boilerplate CLI to scaffold projects, inspect compositions, and list templates. See also [CLI Examples](cli-examples.md) for common workflows.

::: mkdocs-typer
     :module: boilerplate.cli.cli
     :command: app
     :prog_name: boilerplate

## Exit codes

Every command exits with one of six codes (defined in `boilerplate.constants.ExitCode`):

| Code | Name | Meaning |
| --- | --- | --- |
| 0 | SUCCESS | Command completed. |
| 1 | FAILURE | Unexpected error. |
| 2 | CONFIG_ERROR | Invalid configuration or unknown command/option. |
| 3 | VALIDATION_ERROR | Input failed validation (bad answers, missing TTY, conflicting options). |
| 4 | ACTION_REQUIRED | Recoverable pause; user intervention needed. Defined in the taxonomy but not yet produced by any shipped command — its first producer will be the planned `update` conflict pause. |
| 130 | USER_CANCELLED | Cancelled at a prompt (Ctrl+C). |

## Where next

- [Examples](cli-examples.md) — copy-pastable commands for common tasks.
- [Customization](customization.md) — pre-filled answers and extra template layers.
- [Merging and precedence rules](reference/merging.md) — what composed output means.
