# ADR-013: The Interactivity Contract

**Status**: Accepted

## Context

`boilerplate new` renders in one of two modes: interactive (Copier prompts for unanswered questions) or non-interactive (`--non-interactive` / `--ci`, where every answer must come from a default, `profile.toml`, or a forced answer). Prompting has a failure mode with no natural backstop: when stdin cannot host a real terminal session, Copier's prompt layer (`questionary` / `prompt_toolkit`) does not always raise cleanly on EOF — it can retry-loop, growing memory without bound instead of exiting. This is not hypothetical: an equivalent failure was confirmed live on this project (Windows, stdin redirected from `NUL`, which `isatty()` misreports as a terminal) reaching the prompt layer and hanging before the guard was hardened. It is also a category-wide problem — see Evidence.

This ADR records the decision rationale for the interactivity contract of `boilerplate new` (`src/boilerplate/cli/commands/new.py`, `src/boilerplate/composition/rendering/engine.py`) and its error codes (design [Operational quality](07-operational-quality.md) §Error Code Registry; design [Data models](02-data-models.md) §Error Hierarchy), surveyed against primary sources across CLI standards and peer tools, July 2026.

## Decision

### 1. Prompt gating is a proactive stdin-TTY check

Immediately after flag composition (`--ci` / `--non-interactive` resolved to their effective values), and before the template catalog, resolver, composer, or render engine are touched, `new` checks whether stdin can host prompts. If interactive mode is in effect, stdin is not a real TTY, and `--dry-run` was not passed, the command fails closed with `BP_INPUT_TTY_REQUIRED` (exit 3) and a remediation naming the substitute flags (`--non-interactive`, the global `--ci`).

Rationale: Copier's prompt layer can retry-loop on EOF instead of raising. A proactive check refuses the render before that failure mode can occur, rather than relying on the reactive layer (Clause 2) to catch it after the fact.

### 2. A reactive second layer stays

`isatty()` alone can lie. On Windows, `NUL` is a character device and `isatty()` reports `True` for it — confirmed live to pass a naive TTY check and hang in the prompt layer. The proactive guard closes that specific gap with a `GetConsoleMode` probe on the stdin handle: `GetConsoleMode` succeeds only on a genuine console input handle, the same discriminator the prompt layer itself depends on.

Hardening the proactive check does not retire the reactive one. A terminal can pass both the TTY and console-handle checks and still be unable to host `prompt_toolkit`'s rendering (Git Bash pseudo-TTYs, editor-embedded shells, some CI-provided pseudo-consoles). Prompt-layer failures that occur during rendering are still caught and translated to `BP_RENDER_PROMPT_FAILED` (exit 1). The translator additionally recognizes Copier's own `copier.errors.InteractiveSessionError`: Copier wraps EOF-during-prompt in this type with a `builtins` exception as its cause, which would otherwise evade a plain module-prefix match against `prompt_toolkit` / `questionary`. Neither layer subsumes the other — the proactive gate is cheap and catches the common case before any work starts; the reactive layer is the backstop for prompt-layer failures the proactive gate cannot anticipate.

### 3. No input-mode switching on CI environment variables

`CI=true` and vendor equivalents (`GITHUB_ACTIONS`, `TF_BUILD`, and similar) never flip `new` into a defaults-accepting mode. The only mode switches are explicit flags (`--non-interactive`, `--ci`) and their env-var equivalents, `BOILERPLATE_NON_INTERACTIVE` and `BOILERPLATE_CI`, which are tool-scoped opt-ins following the `PIP_NO_INPUT` pattern (an environment variable defined and documented by the tool it controls) — not a heuristic read of ambient CI-identity variables.

Rationale: a CI environment variable answers "am I running in CI?", not "should this tool skip prompting?" Those questions happen to have the same answer on the major CI providers today, but that is not a contract any of them make. A scaffold silently built with wrong defaults propagates through every rendered layer and is discovered late, if at all; a failed pipeline step is discovered immediately, at the point of cause, with a named fix.

### 4. Every prompt has a non-interactive substitute

No template question is reachable only through a prompt:

- **Defaults** (`--non-interactive`) — accept the template's declared `default:` for every question.
- **Persistent pre-fills** (`profile.toml`) — per-user `[defaults]` and `[templates.<name>]` tables that ride Copier's `user_defaults` channel; an interactive answer, or a forced answer, overrides them.
- **A per-invocation answers channel** (`--data` / `--data-file`) — forced answers for a single invocation, on Copier's `data` channel.

`--non-interactive` (and `BOILERPLATE_NON_INTERACTIVE`) is the only defaults-accepting mode for questions; `--yes` governs confirmation prompts only ([CLI reference](05-cli-reference.md)).

### 5. Read-only operations are exempt

`--dry-run` never prompts. It is checked ahead of the TTY guard (Clause 1) and short-circuits it, so a piped `--dry-run` invocation stays legal — there is nothing to answer and no render to protect.

## Options considered

- **Reactive-only enforcement (no proactive TTY gate)** — rejected: relies entirely on Copier's own EOF handling, which is insufficient on its own (see Evidence — `copier-org/copier#2436`) and leaves the unbounded-retry-loop risk live for every non-TTY interactive invocation, not just the Windows `NUL` edge case.
- **Sniff `CI=true` (or vendor equivalents) to auto-switch to non-interactive** — rejected: binds correctness to an environment-identity contract no CI provider makes; the counterexamples (pnpm, uv) show that even narrowly-scoped CI heuristics are treated by their own maintainers as provisional or safety-only, never as a general "assume defaults" switch.
- **Silently substitute defaults on non-TTY stdin (the create-vite model)** — rejected for this category: workable when output is a single-shot starter reviewed immediately after generation; wrong for a composition engine whose answers propagate through every layer a template extends.
- **Collapse to a single enforcement point** — rejected: the proactive gate cannot see prompt-layer failures that only manifest mid-render (Git Bash pseudo-TTY, editor-embedded shells); the reactive translator cannot prevent Copier's retry-loop from starting in the first place. Each covers a failure mode the other cannot.

## Evidence

Verified against primary sources, July 2026.

**The pattern this decision follows:**

- [clig.dev §Interactivity](https://clig.dev/#interactivity): "Only use prompts or interactive elements if stdin is an interactive terminal (a TTY)... you should throw an error telling the user what flag to pass." §Arguments and flags: "Never require a prompt."
- [gh (cli/cli)](https://github.com/cli/cli): `CanPrompt()` requires both stdin and stdout to be a TTY (`pkg/iostreams`); commands fail closed with named-flag errors when not interactive, e.g. `pkg/cmd/pr/merge`: "`--merge`, `--rebase`, or `--squash` required when not running interactively." No `CI` (or vendor-equivalent) detection anywhere in its environment-variable surface.
- [az (microsoft/knack)](https://github.com/microsoft/knack): a stdin-only TTY check gates prompting; failure message: "Unable to prompt for confirmation as no tty available. Use --yes."
- [rustup-init.sh (rust-lang/rustup)](https://github.com/rust-lang/rustup): `[ ! -t 0 ]` gates the install prompt; failure message: "Unable to run interactively. Run with -y to accept defaults."

**Category peers get this wrong** — the proactive guard (Clause 1) is ahead of the category, not behind it:

- Copier itself reacts to `EOFError` only and still hangs on stdin that is open but never fed ([copier-org/copier#2436](https://github.com/copier-org/copier/issues/2436)).
- cookiecutter has no EOF handling; a non-TTY prompt surfaces as a raw traceback.
- Yeoman acknowledged the same gap in 2018 and closed the issue stale without a fix ([yeoman/generator#694](https://github.com/yeoman/generator/issues/694)).

**CI-detection counterexamples cut toward fail-closed, not toward auto-switching** (Clause 3):

- pnpm auto-enables `--frozen-lockfile` in CI specifically to *prevent* silent lockfile drift, not to relax behavior ([pnpm/pnpm#1994](https://github.com/pnpm/pnpm/issues/1994)).
- `uv venv` silently deleting an existing venv when non-interactive is acknowledged by its own maintainers as provisional backwards-compatibility behavior, likely to change ([astral-sh/uv#14309](https://github.com/astral-sh/uv/issues/14309)).

**The alternative model exists, and is rejected for this category** (Clause 3 / Clause 4):

- create-vite silently substitutes defaults for non-destructive choices in non-TTY mode (`argInteractive ?? process.stdin.isTTY`), failing closed only on the overwrite prompt ([vitejs/vite, `packages/create-vite`](https://github.com/vitejs/vite/tree/main/packages/create-vite)). Workable for a lightweight, single-shot starter whose output is reviewed immediately; wrong for a composition engine whose answers propagate through every rendered layer.

## Consequences

- `new` refuses to start an interactive render against non-TTY stdin instead of hanging or silently defaulting; the failure is immediate, attributed, and names the fix.
- CI pipelines and other non-interactive callers must pass an explicit flag (`--non-interactive` or `--ci`). Ambient `CI=true` has no effect on `boilerplate`'s behavior, by design; the tool-scoped env-var equivalents (`BOILERPLATE_NON_INTERACTIVE`, `BOILERPLATE_CI`) do not change this — they are explicit opt-ins, not a CI-identity heuristic.
- The TTY check and the prompt-layer translator are two independent code paths (`new.py` and `engine.py`) with different failure signatures and different exit codes (`BP_INPUT_TTY_REQUIRED` is 3; `BP_RENDER_PROMPT_FAILED` is 1). A future refactor MUST NOT collapse them into a single check without re-verifying both failure modes — `isatty()` lying, and prompt-layer failures the proactive gate cannot anticipate — stay covered.
- Clause 4's substitute set is complete: defaults via `--non-interactive`, persistent pre-fills via `profile.toml`, and per-invocation forced answers via `--data` / `--data-file`, plus the env-var equivalents (`BOILERPLATE_NON_INTERACTIVE`, `BOILERPLATE_CI`) for the flags themselves.

## Sources

- [clig.dev — Command Line Interface Guidelines, §Interactivity](https://clig.dev/#interactivity)
- [cli/cli — GitHub CLI](https://github.com/cli/cli)
- [microsoft/knack](https://github.com/microsoft/knack)
- [rust-lang/rustup](https://github.com/rust-lang/rustup)
- [copier-org/copier#2436](https://github.com/copier-org/copier/issues/2436)
- [yeoman/generator#694](https://github.com/yeoman/generator/issues/694)
- [pnpm/pnpm#1994](https://github.com/pnpm/pnpm/issues/1994)
- [astral-sh/uv#14309](https://github.com/astral-sh/uv/issues/14309)
- [vitejs/vite — create-vite](https://github.com/vitejs/vite/tree/main/packages/create-vite)
