# ADR-004: Coarse exit-code taxonomy, with fine diagnosis in BP* codes

**Status**: Accepted (retroactively documented 2026-06-09; amended 2026-07-11, 2026-07-16) **Date**: documented 2026-06-09 **Deciders**: Project team

## Context

A CLI can expose either a rich set of numeric exit codes or a coarse set plus a separate diagnostic channel. The design ([02-data-models](02-data-models.md)) argues against exit-code proliferation.

## Decision

The CLI defines exactly six exit codes — `SUCCESS=0, FAILURE=1, CONFIG_ERROR=2, VALIDATION_ERROR=3, ACTION_REQUIRED=4, USER_CANCELLED=130` (`constants.py`; the canonical table is [02-data-models](02-data-models.md) §Exit Codes) — and maps the `BoilerplateError` exception hierarchy onto them in one place, the `cli_error_handler` decorator (`cli/utils.py`). Fine-grained diagnosis is carried by per-exception `BP*` codes and `remediation` hints (surfaced as `Fix:` lines), not by additional exit codes.

## Options considered

- **Rich numeric exit codes per error class** — couples scripts to internal taxonomy; proliferates.
- **Four coarse codes + structured BP* codes/remediation** (chosen) — stable script contract, with rich human/machine diagnosis carried out-of-band.

## Consequences

- Scripts branch on a small, stable set; detail comes from the `BP*` code + message.
- A new error maps to one of the coarse codes; contributors add a `BP*` code + remediation rather than a new exit code.
- `ACTION_REQUIRED=4` is reserved for recoverable workflow pauses ([02-data-models](02-data-models.md) §Exit Codes) — the operation needs user intervention before it can complete, as distinct from a hard failure (exit 1). `MergeConflictError` (the composition config-merge error) is a hard failure and stays on exit 1; the update file-conflict pause is the condition that exits 4.

## Amendment (2026-07-11)

As anticipated when this ADR was documented, the design's fifth code `ACTION_REQUIRED=4` is now wired into the `ExitCode` enum and routed in `cli_error_handler` via the `ActionRequiredError` base exception — raising four codes to five without changing the coarse-codes-plus-`BP*` principle. Amended, not superseded. The first live producer of exit 4 is the update conflict pause ([06-project-lifecycle](06-project-lifecycle.md)); no shipped operation raises `ActionRequiredError` before that lands.

## Amendment (2026-07-16)

`USER_CANCELLED=130` (128+SIGINT, the Click/Typer convention for Ctrl-C) is documented as the sixth code, raising five codes to six. It is an interrupt convention rather than a new error class, so the coarse-codes-plus-`BP*` principle is unchanged; no exception maps to it via `cli_error_handler`.

## Verification (2026-06-09, re-verified 2026-07-16)

`constants.py` defines the six-value `ExitCode` IntEnum; `cli/utils.py` `cli_error_handler` maps exception classes to them; `common/exceptions.py` carries `error_code` + `remediation`; covered by `tests/boilerplate/cli/test_utils.py`.
