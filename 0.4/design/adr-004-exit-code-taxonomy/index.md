# ADR-004: Coarse exit-code taxonomy, with fine diagnosis in BP\* codes

**Status**: Accepted

## Context

A CLI can expose either a rich set of numeric exit codes or a coarse set plus a separate diagnostic channel. The design ([Data models](https://therealbillsiegler.github.io/boilerplate/0.4/design/02-data-models/index.md)) argues against exit-code proliferation.

## Decision

The CLI defines exactly six exit codes — `SUCCESS=0, FAILURE=1, CONFIG_ERROR=2, VALIDATION_ERROR=3, ACTION_REQUIRED=4, USER_CANCELLED=130` (`constants.py`; the canonical table is [Data models](https://therealbillsiegler.github.io/boilerplate/0.4/design/02-data-models/index.md) §Exit Codes) — and maps the `BoilerplateError` exception hierarchy onto them in one place, the `cli_error_handler` decorator (`cli/utils.py`); the `ActionRequiredError` base exception routes to `ACTION_REQUIRED=4`. `USER_CANCELLED=130` uses 128+SIGINT, the Click/Typer convention for Ctrl-C, and `cli_error_handler` maps `UserCancelledError`, raised when the user cancels an interactive prompt, to it ([Data models](https://therealbillsiegler.github.io/boilerplate/0.4/design/02-data-models/index.md) §Exit Codes). Fine-grained diagnosis is carried by per-exception `BP*` codes and `remediation` hints (surfaced as `Fix:` lines), not by additional exit codes.

## Options considered

- **Rich numeric exit codes per error class** — couples scripts to internal taxonomy; proliferates.
- **Six coarse codes + structured BP\* codes/remediation** (chosen) — stable script contract, with rich human/machine diagnosis carried out-of-band.

## Consequences

- Scripts branch on a small, stable set; detail comes from the `BP*` code + message.
- A new error maps to one of the coarse codes; contributors add a `BP*` code + remediation rather than a new exit code.
- `ACTION_REQUIRED=4` is reserved for recoverable workflow pauses ([Data models](https://therealbillsiegler.github.io/boilerplate/0.4/design/02-data-models/index.md) §Exit Codes) — the operation needs user intervention before it can complete, as distinct from a hard failure (exit 1). `MergeConflictError` (the composition config-merge error) is a hard failure and stays on exit 1; the update file-conflict pause is the condition that exits 4.

## Verification (2026-06-09, re-verified 2026-07-16)

`constants.py` defines the six-value `ExitCode` IntEnum; `cli/utils.py` `cli_error_handler` maps exception classes to them; `common/exceptions.py` carries `error_code` + `remediation`; covered by `tests/boilerplate/cli/test_utils.py`.
