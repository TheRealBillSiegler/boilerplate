# Changelog

All notable changes to this project will be documented in this file.

From 0.4.0 on, [release-please](https://github.com/googleapis/release-please) writes each entry from [Conventional Commits](https://www.conventionalcommits.org/), breaking changes first, then Features, Bug Fixes and Performance Improvements; the 0.3.0 entry predates it and follows [Keep a Changelog](https://keepachangelog.com/). This project adheres to [Semantic Versioning](https://semver.org/).

## [0.4.0](https://github.com/TheRealBillSiegler/boilerplate/compare/v0.3.0...v0.4.0) (2026-10-21)


### ⚠ BREAKING CHANGES

* **new:** `boilerplate new` into a directory that already holds files or folders, hidden ones included, now exits 3 unless `--force` is passed. It used to prompt per conflicting file, fail with `BP_RENDER_PROMPT_FAILED` (exit 1) without a console, or let a later layer replace your file with exit 0. Pass `--force` to overwrite, or render into an empty directory.
* **new:** `-n` now means `--dry-run`, and `--yes`/`-y` is rejected as an unknown option. Scripts that used `-n` or `--yes` to skip prompts must pass `--non-interactive`.
* **cli:** `--ci` and `BOILERPLATE_CI=1` now run the template's post-creation tasks. Add `--no-tasks` to keep skipping them.
* **cli:** The `boilerplate version` command and the `-V` option are gone. Run `boilerplate --version`, which prints the same `boilerplate X.Y.Z` line. `boilerplate version --format json` has no replacement.
* **list:** `boilerplate list` with no templates now exits 0 instead of failing, and its JSON output no longer has an `error` key.
* **new:** A malformed `name@version` in a template's `extends` now exits 3 with `BP_INPUT_SPECIFIER_INVALID` instead of exiting 1 with `BP_RESOLVE_DEP_NOT_FOUND`.

### Features

* **new:** `boilerplate new` writes `boilerplate.lock` to the new project, recording each layer, its version and how it joined the project. Commit it with the rest of the project.
* **new:** A project made from several layers asks each question once, then renders each layer with only the answers it declares.
* **new:** `new` requires a destination when it cannot prompt for one.
* **project template:** Added a `build_backend` choice, `uv_build` (default) or `hatchling`.
* **project template:** Added `pyright` to the dev dependencies.
* **project template:** `sample_module` is now optional. Turning it off renders an import test in place of the sample test, and the README quick start adjusts.
* **project template:** Container scripts honor the answers given at render time.
* **streamlit template:** The sample app is now a stack-at-a-glance demo in place of the greeter. The streamlit layer turns the sample module off, requires `pydantic>=2` and renders its own line-ending rules.
* **templates:** Template files are licensed under MIT-0.
* **cli:** Top-level help opens with a banner, grouped by what you are doing. `--quiet` hides the banner.
* **cli:** `--ci` and `--verbose` can be combined.
* **cli:** `--color always` overrides `NO_COLOR`; `--color never` and `NO_COLOR` render bare text.

### Bug Fixes

* **new:** A layer's own `skip_if_exists` no longer applies in a composed render, so a later layer no longer skips files an earlier layer wrote.
* **new:** `boilerplate.yml` versions are reported for plain-folder templates.
* **new:** Post-creation tasks run only when Copier copies, and the `uv sync` hint appears under Next steps only when tasks are skipped.
* **new:** The render announcement appears only when nothing is asked first.
* **cli:** Unknown `--color` and `--format` values are rejected.
* **cli:** Text you supply appears in messages as typed.
* **cli:** `Error:` prefixes the `graph` option-conflict, `validate` not-a-directory and settings-load messages, the remediation line is labeled `Fix:`, and it goes to stderr under `--quiet`.
* **cli:** `--force` help says it overwrites a non-empty destination.
* **list:** Descriptions in the table wrap instead of being truncated.
* **install:** The installer starts under Windows PowerShell 5.1, installs the CLI release it ships with (including after the PowerShell 7 relaunch), and stops when winget is missing and a tool is not installed.
* **install:** Installer narration matches between `install.ps1` and `setup-wsl-env.sh`, and its output no longer includes emoji.
* **project template:** Names that make no importable Python package, and answers containing quotes, backslashes or line breaks that would break `pyproject.toml`, are refused.
* **project template:** `pyproject.toml` no longer declares a license named "None".
* **project template:** Rendered projects stay LF on every platform, `uv.lock` is committed rather than ignored, dependency lists render without blank lines, coverage reports the rendered package, docstring summaries start on the opening line, and the scaffolded READMEs name ruff's fixing flag.
* **project template:** The venv keeps its managed Python interpreter at runtime, and container scripts read the image name with POSIX awk.
* **streamlit template:** The smoke test is collectible and finite, and the project owns it. `launch.json` uses forward slashes.
* **docs:** Corrected claims about `--dry-run`, `validate` exit codes, `extends` pins and generated-project CI.
* **docs:** The 404 page recovery links resolve under versioned docs.

### Performance Improvements

* **docs:** Mermaid loads only on pages with diagrams.

## [0.3.0] - 2026-09-04

### Added

- ADR-015 records the composition paradigm — a composed project is indistinguishable from N hand-run Copier applications: per-layer answers files written by Copier, update as an orchestrated walk of vanilla `copier update` per layer, sources (remote git, local git, plain directory) inherited from Copier with per-layer updateability; ADR-006 amended to make the published per-template repos the canonical distribution channel (wheel bundle demoted to a deferred offline seed cache); ADR-007 amended to affirm single-pass version jumps on evidence and to specify the jump-safe migration authoring contract
- "Did you mean?" suggestions for mistyped commands
- GitHub Actions CI pipeline: lint, typecheck, ShellCheck, the full test suite from the repo root with an explicit doctest step (pushes run every OS on Python 3.13 plus Ubuntu on 3.12; pull requests run Ubuntu only), and a strict docs build, behind a single required gate check
- CODEOWNERS file
- GitHub issue templates (bug report, feature request) and PR template
- Post-creation guidance after `boilerplate new` with next steps (`cd`, `uv sync`)
- Pipeline narration during `new` command (resolving, composing, rendering phases)
- Help text command grouping: Project, Template, and System command panels
- "Get started" block in `--help` output with example commands
- Shell completion documentation in README
- Global flags: `--quiet`/`-q`, `--color auto|always|never`, `--version`/`-V`
- `--ci` global flag (implies `--quiet --non-interactive --yes --no-tasks`)
- `new` command flags: `--yes`/`-y`, `--dry-run`, `--no-tasks`
- `new` command flags: `--data key=value` (repeatable) and `--data-file <path>` supply forced, per-invocation answers on Copier's `data` channel — never prompted for, and satisfy the non-interactive missing-required-answers pre-flight; `--data` wins over `--data-file`, both win over `profile.toml`
- Phase-tagged `BP_{PHASE}_{DESCRIPTOR}` error codes and remediation hints on most exception types; the rendered `Error:` line carries the code as a bracketed suffix
- Six-value exit-code taxonomy: `ACTION_REQUIRED` (4) joins the canonical set for recoverable workflow pauses, routed in the CLI error boundary (no shipped operation produces it yet)
- Strict-JSON structured logging: non-TTY stderr (or `--ci` on any terminal) emits one JSON object per log event with `phase`, `operation`, `request_id`, `success`, and `error_code` on failure; `BOILERPLATE_REQUEST_ID` is used verbatim as the correlation ID when set
- Hardened YAML loader shared by all boilerplate-owned parse sites: duplicate mapping keys are an error and total alias expansion is capped, defusing billion-laughs inputs; `validate` delegates `copier.yml` parsing to Copier's own config loader so Copier-native tags validate correctly
- Per-user `profile.toml` customization: `[defaults]` and `[templates.<name>]` tables pre-fill template questions as ordinary, overridable Copier answers
- `BOILERPLATE_ACCESSIBLE` env var for screen-reader-friendly output
- `--format json` on `version`, `list`, and `new` commands (compose and graph already had it)
- `validate` command with 9 structural checks, `--strict` mode, and JSON output
- This changelog
- ADR-013 recording the interactivity contract: stdin-TTY-gated prompting, fail-closed with named substitute flags, two-layer enforcement, and the rejection of CI-env-var input-mode switching
- `BOILERPLATE_NON_INTERACTIVE` and `BOILERPLATE_CI` env vars mirror `--non-interactive` and `--ci` (full implication chain, OR semantics with the flag, compose with the non-TTY guard exactly like the flags); the generic `CI` variable is still never inspected
- Bundled templates gained org-customization questions: `package_index_url` (project) and `container_registry` (streamlit), replacing hard-coded organization values
- CI pipeline reference (`docs/governance/ci.md`) with a full-flow diagram: triggers, change dispatcher, draft economy, matrix policy, gate contract, and the `scripts/check.py` local gate
- Versioned documentation via mike: `mkdocs.yml` declares the version selector (`extra.version`, one docs version per MAJOR.MINOR, `latest` alias) and `site_url`; deploys start with 0.3 at public cutover per RELEASING.md

### Changed

- Composed projects now carry per-layer Copier answers files (`.copier-answers.<layer>.yml`, one per composed template); the single canonical `.copier-answers.yml` is no longer written
- Docs golden-path pass: the nav is reordered into the audience journey (Install and Quickstart before project status; the command reference lives in the Reference section as "Commands"), every section exit hands off somewhere, voice and naming are unified under the brand register (one name per concept: override, option, locked dependencies), examples lead their pages and show captured real output, repo-history references are scrubbed from durable prose, Mermaid is vendored locally — byte-identical to upstream's published build, with upstream's LICENSE beside it — so the site makes no external fetch at view time and the offline bundle renders diagrams, and three unused markdown extensions plus an unused theme feature are dropped
- Docs candor pass: the platform reference page now uses standard platform-engineering vocabulary (curated stack, golden path) and separates what templates scaffold from recommended-but-unshipped tooling (CI workflows); the merging reference describes the real per-layer `Worker` behavior instead of an isolation model that never existed and leads with a worked example; exit code 4, migration machinery, and the template-versioning constraint (now "one version stream per repository", deferring mechanism to the distribution ADR) are labeled design-only where unbuilt; CLI and installer examples are synced with their sources
- Docs overhauled from a full audit: false capability claims cut (no `copier update` path exists yet; the container push script only authenticates against ACR; a documented merge rule that was never implemented is gone), each repeated fact now has one owning page with links elsewhere (PATH remediation, the VS Code interpreter fix, tool descriptions), the platform reference cut from ~4,800 to ~1,400 words of what the tool actually does, broken code-fence rendering on the environment page repaired, and the CLI/Help/Contribute nav groups gained orienting section pages
- Implementation status (`docs/status.md`) is the single owner of current-state facts: the composition engine is rated Partial with design 04's open contracts named (graph limits, `CopierWorker`) and the shipped extension-injection divergence stated, the env-driven `Settings` surface is documented as shipped, the specified-command inventory includes `eject`, and the roadmap points there instead of embedding status — phase completion is recorded by releases, not page annotations
- README rewritten with clear value proposition, install instructions, and quick start
- `boilerplate version` output simplified to `boilerplate X.Y.Z`
- Errors and warnings now route to stderr instead of stdout
- `BoilerplateError` base class maps to exit code 1 (FAILURE) instead of 2 (CONFIG_ERROR)
- pyproject.toml description updated from placeholder to accurate one-liner
- Bundled templates enriched with `schema_version`, YAML comments explaining fields and composition
- Documentation nav restructured: internal roadmap separated from user-facing reference
- Docs site repo link points at GitHub
- Quickstart code examples changed from PowerShell to cross-platform bash
- Installation reduced to the single public path: `scripts/install.ps1` installs uv and boilerplate from the public git URL; organizations layer their own configuration on top

### Fixed

- `project` restates Copier's default exclusions, which its declared `_exclude` had silently replaced, so a vanilla Copier run from a git-backed clone of the template no longer copies the clone's `.git` into the project; `streamlit` declares the inherited answers its files use (`project_name`, `package_name`, `package_index_url`) so each bundled layer can be updated on its own with vanilla `copier update`
- Composed templates' `_tasks` now keep Copier's native shapes: plain-string tasks retain shell execution (previously wrapped into argv form, breaking any multi-word command), and mapping-form tasks keep their `when:` condition and `working_directory` (previously dropped from execution or made unconditional); malformed entries are dropped with a warning instead of silently
- The merged `_jinja_extensions` union now reaches every layer's Worker, so a question default or task using a sibling layer's filter renders instead of crashing with `No filter named ...`; alongside this, Copier's `unsafe` grant is now scoped per layer to what that Worker actually loads instead of blanket-`True`
- A layer declaring its own `_exclude` no longer forfeits Copier's built-in `DEFAULT_EXCLUDE`, so `__pycache__/`, `*.py[co]`, `.DS_Store`, `~*` backups, and `.git` can no longer leak from template sources into generated projects
- `--format json`/`yaml` output is byte-exact on every command: Rich no longer hard-wraps long lines at the console width, interprets `[...]` spans as markup (YAML flow sequences were silently swallowed), or injects ANSI codes under `--color always`
- One malformed template directory no longer breaks the whole catalog: invalid candidates are skipped with a warning naming the offending `boilerplate.yml`, a non-mapping YAML document produces a clean validation error instead of a `TypeError`, and non-permission `OSError`s are reported with their real text instead of a fabricated "Permission denied"
- The project template's post-generation summary now tells the truth: a failed `uv sync` or `git init` suppresses the success banner and exits non-zero, a cosmetic `_scripts` cleanup failure warns and continues instead of failing the whole render, and subprocess output is decoded as UTF-8 regardless of the OS locale codepage
- Templates declaring `_min_copier_version` no longer crash `compose`/`new` with a `TypeError`: the version is stringified at the Copier config extraction boundary, which also makes the merger's version-intersection strategy reachable
- License inconsistency: CONTRIBUTING.md referenced MIT but LICENSE is Apache-2.0
- structlog/stdlib logging inconsistency: CLAUDE.md and CONTRIBUTING.md now match actual stdlib usage
- Composition engine: non-first layers always overwrite. Composition is defined as layers overlaying previous output (`extends: [project]` means "write my files on top of project's"), but the engine was passing user's `--force` uniformly, so Copier prompted "Overwrite <file>?" for every file a non-first layer wrote. The user's `--force` now only governs the first layer; subsequent layers are orchestrated overlays and always overwrite.
- Composition ordering is deterministic and honors precedence: siblings apply in `extends` declaration order (later-declared siblings win file and config conflicts), with lexicographic order only across independent roots; previously sibling order could vary run to run under hash randomization
- Template metadata reads and writes pass explicit UTF-8 encoding instead of depending on the platform locale
- `--templates-dir` now adds its directory to the template search path instead of replacing it, so bundled and configured templates (and anything they're extended from) remain resolvable
- `boilerplate new` fails closed (`BP_INPUT_TTY_REQUIRED`, exit 3) when interactive mode is requested but stdin is not a TTY; previously Copier's prompt layer could retry-loop on EOF instead of raising and grow memory without bound. On Windows, stdin redirected from `NUL` — which `isatty()` misreports as a terminal — is likewise rejected via a console-handle check that would otherwise leave the prompt waiting forever on input that can never arrive. `--dry-run` never prompts and remains legal when piped.
- Ctrl+C at an interactive prompt no longer dumps Copier's internal `AnswersMap`/`Question`/`Template` repr (including collected answers and absolute template paths) to the terminal. `copier.errors.CopierAnswersInterrupt` subclasses both `CopierError` and `KeyboardInterrupt`, so it fell through to the generic exception handler; the render engine now recognizes it as user cancellation before that handler sees it and prints a single `Error: Aborted.   [BP_RENDER_USER_CANCELLED]` line with exit code 130, matching every other Ctrl+C in the CLI (Typer's own `KeyboardInterrupt` handler already exits 130).
- CLI output no longer raises `UnicodeEncodeError` on legacy Windows codepages (cp437/cp1252): stdout/stderr are reconfigured to UTF-8 with `errors=replace` at startup
- Rendered projects no longer contain layer-root `boilerplate.yml`/`copier.yml` authoring metadata, even when a layer declares its own `_exclude`
- Freshly generated projects pass their own `ruff format --check` out of the box
- The project template no longer hardcodes a Windows-specific Python interpreter path in its VS Code guidance
- `install.ps1` run under Windows PowerShell 5.1 now installs and relaunches under PowerShell 7 instead of printing a false success banner; winget steps hardened for unattended fresh-machine runs
- `extends` declaration order is preserved in the composition graph's serialized edges; they were previously emitted lexicographically, misrepresenting the sibling file-precedence order that toposort itself already honored
- A dependency diamond that resolves the same template name at two different versions now fails resolution with `BP_RESOLVE_VERSION_CONFLICT` instead of silently rendering both versions with an order-dependent result
- Git-backed template layers render and read config at Copier's own default ref (the latest tag, or a plain copy when the template isn't a git repository) instead of a dirty `HEAD`, so a layer's merged schema and its rendered files provably come from the same revision recorded in that layer's `.copier-answers.<layer>.yml`; the temporary clone Copier makes for a git-backed layer is now cleaned up on every path (render and catalog/config reads), where it previously leaked one clone per read
- CLI usage errors (an unknown option or command, a missing required argument, an invalid flag value) now exit 3 (VALIDATION_ERROR) instead of Click's default 2, which the exit-code taxonomy reserves for CONFIG_ERROR
- Errors raised inside the shared resolve-compose pipeline now render through the configured display like every other CLI error, honoring color mode and `--quiet`, instead of falling back to plain unstyled output
- The streamlit template's Dockerfile pins the `uv` base image to a minor tag (`0.12`) instead of `latest`, so rendered projects get a stable, update-tooling-bumpable value instead of an untracked moving target

### Removed

- `-f` short flag from `compose --format` and `graph --format` to avoid conflict with `new --force`
- `-t` short flag from `--templates-dir` to reserve for future `--target-version`

## [0.2.0] - 2026-03-23

### Added

- `compose` command with section-based output (final, layers, states, deltas, stats)
- `graph` command with table, tree, and JSON output formats
- Template composition engine with dependency resolution
- Three-way merge strategies for layered template configuration
