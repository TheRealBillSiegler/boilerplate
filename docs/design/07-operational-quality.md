# Operational Quality

## Purpose

Cross-cutting operational quality controls that apply to every feature slice: stable error codes, error attribution, structured logging, performance contracts, retry policy, the Atomic Staged Write Pattern, concurrency control, and platform portability. The security model itself lives in [10-security.md](10-security.md).

---

## Error Codes

### Design Principles

1. Error codes MUST be stable once published — **from 1.0**. During `0.x` (pre-release; see [Versioning & Compatibility](../governance/versioning.md)) codes MAY still change as the surface settles, and the rename to the `BP_{PHASE}_{DESCRIPTOR}` scheme is pre-1.0 hygiene, not a frozen contract. From 1.0, a published code MUST NOT change its meaning.
2. Each code MUST map to exactly one root cause.
3. Each code MUST carry: phase, severity, retryable flag, and remediation guidance.
4. Codes MUST NOT leak sensitive internal details.

### Code Namespace

All error codes use the prefix `BP_` followed by the phase and a short descriptor:

```text
BP_{PHASE}_{DESCRIPTOR}
```

### Phase Prefixes

| Phase prefix | Scope |
|-------------|-------|
| `BP_RESOLVE_` | Template resolution and dependency traversal |
| `BP_VERSION_` | Version parsing and constraint evaluation |
| `BP_GRAPH_` | Dependency graph building and validation |
| `BP_LOCK_` | Lock file reading, writing, and validation |
| `BP_RENDER_` | Template rendering and staging |
| `BP_INPUT_` | User input validation |
| `BP_CONFIG_` | Configuration loading |
| `BP_FETCH_` | Remote template fetching (network, authentication) |
| `BP_GIT_` | Git binary availability and Git command failures |
| `BP_ENV_` | Environment provisioning (`env apply` command group) |
| `BP_CONCURRENCY_` | Operation-level concurrency control: advisory-lock acquisition and mutex contention. Distinct from `BP_LOCK_`, which is content-level operations on the lock file artifact. |
| `BP_FILESYSTEM_` | Local filesystem failures (permission denial, path-length limits) raised by Boilerplate's I/O routines independent of pipeline stage. Example: `BP_FILESYSTEM_PERMISSION`. |
| `BP_BUNDLE_` | Integrity verification for archive and wheel-bundle template sources (archive extraction failures, checksum mismatches). Example: `BP_BUNDLE_CHECKSUM_FAILED`. The prefix covers all non-Git archive-based sources. |
| `BP_UPDATE_` | The update walk: drift between the lock and the answers files, an incomplete answers file, a resume whose targets differ from the paused update's, a resolved source that diverges from the lock (`BP_UPDATE_SOURCE_DIVERGED`, [10 §Verification Pipeline](10-security.md#verification-pipeline)), and a task that fails after the copy-back. Example: `BP_UPDATE_LAYER_DRIFT`. |
| `BP_COPIER_` | Copier-engine compatibility failures (version mismatch, unsupported Copier feature). Example: `BP_COPIER_COMPAT_FAILED`. |

> **Mapping to pipeline stages**: Error code phases are orthogonal to the operational pipeline stages defined in [06-project-lifecycle.md](06-project-lifecycle.md). The creation pipeline stages (Resolve → Compose → Render → Lock → Init) may trigger errors from multiple phases: the Resolve stage may produce `BP_RESOLVE_*`, `BP_VERSION_*`, or `BP_GRAPH_*` errors; the Render stage may produce `BP_RENDER_*` or `BP_GIT_*` errors; the Lock stage may produce `BP_LOCK_*` errors. Error code phases group errors by their root cause domain, not by the pipeline stage in which they occur.

### Error Code Registry

When new error conditions are identified during implementation, they MUST be added to the relevant design document before being implemented. Each phase prefix has a set of error codes following the principles above. Registered codes and representative examples illustrating the pattern:

| Code | Severity | Retryable | Description |
|------|----------|-----------|-------------|
| `BP_RESOLVE_TEMPLATE_NOT_FOUND` | error | no | Template reference cannot be found in the catalog |
| `BP_RESOLVE_DEP_NOT_FOUND` | error | no | A template referenced in `extends` cannot be found in the catalog. Attribution: Template Author |
| `BP_RESOLVE_MERGE_CONFLICT` | error | no | Two layers declare incompatible values for the same configuration key. Exit code 1. Attribution: Template Author |
| `BP_RESOLVE_METADATA_INVALID` | error | no | Template metadata (`boilerplate.yml`) is malformed, missing required fields, or inconsistent. Exit code 3. Attribution: Template Author |
| `BP_RESOLVE_VERSION_CONFLICT` | error | no | Diamond dependency at incompatible versions. Attribution: Template Author |
| `BP_RESOLVE_PROFILE_MISSING` | error | no | Template's `requires_profile` is not satisfied: the named profile is absent from the project's environment state, or its version does not satisfy the profile-version constraint. Exit code 3. Attribution: User / Template Author |
| `BP_VERSION_INVALID` | error | no | A version string is not PEP 440 compliant. Exit code 3. Attribution: User |
| `BP_GRAPH_CYCLE` | error | no | The template dependency graph contains a cycle. Exit code 1. Attribution: Template Author |
| `BP_LOCK_READ_FAILED` | error | no | `boilerplate.lock` cannot be read as a lock file: unparseable YAML, a truncated write or a body that does not match the schema. Boilerplate does not repair it; the message gives the recreate remediation ([06 §Lock File Recovery](06-project-lifecycle.md#lock-file-recovery)). Attribution: User |
| `BP_LOCK_SCHEMA_UNSUPPORTED` | error | no | Lock file's `schema_version` major exceeds the major supported by the running tool (the project was created by a newer Boilerplate). Fail closed; do not read or mutate. Attribution: User |
| `BP_RENDER_STAGING_FAILED` | error | yes | Rendering failed during staging; staging was cleaned up |
| `BP_RENDER_UNSAFE_EXTENSION` | error | no | A Jinja2 extension is not on the allowed list. Attribution: User / Template Author |
| `BP_RENDER_DEST_NOT_EMPTY` | error | no | The render destination exists and is non-empty, and `--force` was not provided. Exit code 3. Attribution: User |
| `BP_RENDER_PROMPT_FAILED` | error | no | Copier's prompt machinery failed because the environment cannot host interactive prompts. Exit code 1. Attribution: System |
| `BP_RENDER_USER_CANCELLED` | error | no | The user cancelled an interactive prompt (e.g. Ctrl+C). Exit code 130. Attribution: User |
| `BP_INPUT_SPECIFIER_INVALID` | error | no | A template specifier (`name@version`) fails name or version validation. Exit code 3. Attribution: User |
| `BP_INPUT_FORCE_REQUIRED` | error | no | A multi-layer render in non-interactive mode requires `--force`. Exit code 3. Attribution: User |
| `BP_INPUT_ANSWERS_MISSING` | error | no | Non-interactive render cannot proceed: required questions have no default and no supplied answer. Exit code 3. Attribution: User / Template Author |
| `BP_INPUT_ANSWER_REJECTED` | error | no | `update` cannot proceed: a recorded answer fails the target view's question type, choices or validator (a retyped question or a tightened validator). The check runs inside the layer's step, after its migrations and Copier's re-read of the answers file, so a migration that repairs the answer clears it first; the message names the layer, the question and the recorded value ([04 §Safe Update](04-composition-engine.md#safe-update)). A value for the question supplied by `--set` or `--answers` replaces the recorded answer, so the check applies only to a recorded answer nothing replaces; the message names the remediation `--set <question>=<value>`. In a terminal, the question's prompt shows why the answer is rejected and asks for a valid one. Exit code 3. Attribution: User / Template Author |
| `BP_UPDATE_TASK_FAILED` | error | no | A task failed after the update's files were copied back. Under `--non-interactive` the update keeps the files, writes the lock, and names the failed task and how to rerun it ([04 §Safe Update](04-composition-engine.md#safe-update)). Exit code 1. Attribution: Template Author |
| `BP_UPDATE_ANSWERS_INCOMPLETE` | error | no | `update` found, before any layer ran, a question of a layer's scoped view at the recorded versions that is neither secret nor hidden that neither the layer's own answers file nor its declaring layer's file records, so the walk has no answer to fill the old copy with. The message lists the layer and the keys and the remediation: undo the hand-run update that trimmed the file, with `git stash --include-untracked` if it is uncommitted or `git revert` of the commit that holds it, then run `boilerplate update` again ([04 §Safe Update](04-composition-engine.md#safe-update)); `doctor` reports a trimmed file and any key no layer records. Exit code 3. Attribution: User |
| `BP_UPDATE_LAYER_DRIFT` | error | no | `update` found, before any layer ran and with no pending `conflict` record to resume, a layer and one of its ancestors that both disagree with `boilerplate.lock`. The message names each layer's `_commit` and the lock's version, and the remediation: `git stash --include-untracked` sets the partial update aside, then run `update` again ([04 §Safe Update](04-composition-engine.md#safe-update)). Exit code 3. Attribution: User |
| `BP_UPDATE_TARGET_MISMATCH` | error | no | An explicit `--target-version` differs from the targets the pending `conflict` record names. The message tells the user to set the partial update aside first (`git stash --include-untracked`) and run `update` again ([04 §Safe Update](04-composition-engine.md#safe-update)). Exit code 3. Attribution: User |
| `BP_UPDATE_DOWNGRADE_REJECTED` | error | no | `update` found, before any layer changed, a target older than the version a layer's answers file records in `_commit`, or a recorded `_commit` that yields no version. There is no override; the message names the layer, its recorded version and the target ([06 §Step 2: Resolve Target](06-project-lifecycle.md#step-2-resolve-target)). Exit code 3. Attribution: User |
| `BP_UPDATE_PROJECT_NOT_READY` | error | no | `update` or `add` found that the project is not a git repository root with at least one commit, or that its working tree has uncommitted changes, untracked files included (Copier's own rule: `git status --porcelain` is not empty). The staging worktree is not created ([06 §Pre-Flight Check](06-project-lifecycle.md#pre-flight-check)). Exit code 3. Attribution: User |
| `BP_UPDATE_PATH_OBSTRUCTED` | error | no | Before the copy back, a path the walk added already exists in the checkout as a file or directory git ignores. The checkout is unchanged; the message names each path ([06 §Staging worktree](06-project-lifecycle.md#staging-worktree)). Exit code 3. Attribution: User |
| `BP_UPDATE_INTERRUPTED` | error | no | The last migration record is still `in_progress`: an earlier update was interrupted after its copy back started. The message names that update's targets and `git stash --include-untracked` ([06 §Migration Records](06-project-lifecycle.md#migration-records)). Exit code 3. Attribution: User |
| `BP_UPDATE_COPY_BACK_FAILED` | error | no | Copying the staging worktree back into the checkout failed partway. The checkout is restored to the starting commit and the staging worktree is kept; the message names its path so the walk's result is not lost ([06 §Staging worktree](06-project-lifecycle.md#staging-worktree)). Exit code 1. Attribution: System |
| `BP_UPDATE_PROJECT_NOT_MANAGED` | error | no | `add` found no `boilerplate.lock` in the project. Nothing is staged, and the remediation points to `boilerplate adopt` ([05 §add](05-cli-reference.md#add)). Exit code 3. Attribution: User |
| `BP_UPDATE_LAYER_ALREADY_ADDED` | error | no | `add` named a template the project's lock already lists. The remediation points to `boilerplate update` ([05 §add](05-cli-reference.md#add)). Exit code 3. Attribution: User |
| `BP_UPDATE_ANCESTORS_MISSING` | error | no | `add` found that a template the new layer `extends`, directly or transitively, is not in the lock. The message names each missing layer, and the remediation is `boilerplate add <ancestor>` first ([05 §add](05-cli-reference.md#add)). Exit code 3. Attribution: User |
| `BP_UPDATE_ANCESTOR_VERSION_MISMATCH` | error | no | `add` found an ancestor whose recorded version fails the new layer's `extends` constraint. The message names the ancestor, its recorded version and the constraint, and the remediation is `boilerplate update` first ([05 §add](05-cli-reference.md#add)). Exit code 3. Attribution: User |
| `BP_UPDATE_SUBMODULES_UNSUPPORTED` | error | no | `update` or `add` found a `.gitmodules` file in the project. The staging worktree is not created, and the message names the submodule paths ([06 §Pre-Flight Check](06-project-lifecycle.md#pre-flight-check)). Exit code 3. Attribution: User |
| `BP_UPDATE_CHECKOUT_CHANGED` | error | no | The user's checkout changed after the staging worktree was created, so the copy back would overwrite work. The worktree is discarded and nothing is written ([06 §Staging worktree](06-project-lifecycle.md#staging-worktree)). Exit code 3. Attribution: User |
| `BP_INPUT_TTY_REQUIRED` | error | no | Interactive render requested but stdin is not a TTY, so prompts can never be answered. Exit code 3. Attribution: User |
| `BP_INPUT_DEST_REQUIRED` | error | no | Non-interactive render names no destination; the current directory is never assumed. Exit code 3. Attribution: User |
| `BP_INPUT_DATA_INVALID` | error | no | `--data`/`--data-file` input fails validation: a malformed or empty `--data` key, an underscore-prefixed (Copier-reserved) key, an unreadable or non-UTF-8 `--data-file`, invalid YAML, a non-mapping document, or a non-string YAML key. Exit code 3. Attribution: User |
| `BP_CONFIG_DIR_INVALID` | error | no | A required directory path is missing, not a directory, or otherwise invalid. Exit code 2. Attribution: User |
| `BP_CONFIG_PROFILE_INVALID` | error | no | `profile.toml` exists but is not valid TOML, or a reserved section is not a table. Exit code 1. Attribution: User |
| `BP_CONCURRENCY_CONTENTION` | error | yes | Another Boilerplate process may be operating on the same project |
| `BP_FETCH_NETWORK_FAILED` | error | yes | Network error when fetching a remote template source |
| `BP_GIT_AUTH_FAILED` | error | no | Git authentication failed. Attribution: Git |
| `BP_ENV_APPLY_FAILED` | error | yes | Environment provisioning failed. Attribution: Boilerplate / proto |
| `BP_FILESYSTEM_PERMISSION` | error | no | Insufficient filesystem permissions. Attribution: System |

Each error code carries severity, retryable flag, a human-readable description, remediation guidance, and attribution. The registry grows as new failure modes are identified, but published codes are immutable from 1.0 (see Design Principle 1). Domain-specific codes are documented in their owning specification (e.g., `BP_ENV_*` in [§08 Environment Provisioning](08-environment-provisioning.md)).

### Error Message Format

Every error emitted to the user MUST include the following components, presented in inverted pyramid order (most actionable first):

1. **Error description**: A concise, human-readable `Error: ...` line with the `BP_*` code as a bracketed suffix
2. **Reason**: The root cause or context (indented below)
3. **Fix**: A concrete, actionable remediation step (indented, labeled "Fix:")
4. **Code**: The stable `BP_*` code (shown as suffix on the Error line)
5. **Attribution**: Which component owns the failure — shown only in `--verbose` mode
6. **Exit code**: Shown only in `--verbose` mode

**For interactive (TTY) output**, error messages MUST use the inverted pyramid pattern — lead with the human-readable description, promote the fix, demote metadata:

```text
Error: Render failed while processing template "streamlit-app".   [BP_RENDER_TEMPLATE_FAILURE]
  Missing include file _base/project/copier.yml.
  Fix: git submodule update --init --recursive
```

**For verbose mode** (`--verbose`), the full diagnostic format is shown:

```text
Error: Render failed while processing template "streamlit-app".   [BP_RENDER_TEMPLATE_FAILURE]
  Missing include file _base/project/copier.yml.
  Fix: git submodule update --init --recursive
  Attribution: YAML
  Exit code: 1
```

**For JSON output** (`--format json`), all fields are included in the JSON error object.

**Multi-step remediation**. When the fix requires more than one action, the `Fix:` line MAY expand into a multi-line block introduced by `→` arrows:

```text
Error: Template not found in catalog: pyhton-web   [BP_RESOLVE_TEMPLATE_NOT_FOUND]
  Searched catalogs: official, community.
  Did you mean 'python-web' (92% match)?
  Fix:
    → boilerplate catalog sync
    → boilerplate new python-web
```

Each arrow is a discrete remediation step. The arrow prefix is reserved for remediation-step lines; other guidance uses normal indentation.

### Error Attribution

| Attribution | Meaning |
|-------------|---------|
| `Boilerplate` | The failure is in Boilerplate's own logic |
| `Copier` | Copier reported a rendering or task error |
| `Git` | A git operation failed |
| `YAML` | YAML parsing or include resolution failed |
| `User` | The error is due to invalid user input |
| `Network` | A remote operation failed due to connectivity |
| `System` | A required system dependency is missing or misconfigured |
| `proto` | The proto toolchain manager reported an error |
| `Template Author` | The error is due to a defect in template configuration |

**Attribution decision rules for boundary cases**:

- Copier fails due to invalid Jinja2 in a template → **Template Author** (the template has a syntax error)
- Copier fails due to an internal bug → **Copier** (Boilerplate has no control over Copier internals)
- Git authentication fails → **User** if credentials are misconfigured; **Network** if the server is unreachable
- Template declares an invalid `_min_copier_version` → **Template Author** (the template metadata is wrong)
- Lock file checksum mismatch → **System** (disk corruption or external modification)

When multiple parties are involved, attribute to the **root cause** — the party whose action or configuration caused the failure, not the component that reported it.

---

## Structured Logging

### Logging Levels

| Level | When to use |
|-------|-------------|
| `ERROR` | Operation failed; user action required |
| `WARNING` | Non-fatal issue the user should know about |
| `INFO` | Normal progress and completion events |
| `DEBUG` | Detailed diagnostic information (enabled by `--verbose`) |

### Required Log Fields

Every structured log event MUST include: the operation phase, the specific operation, the template being processed (if applicable), a correlation ID (`request_id`), success/failure status, duration, and the `BP_*` error code on failure.

Task execution events MUST additionally include the command executed, the source template, execution order, exit code, and duration. Task stdout and stderr MUST be captured and logged at DEBUG level to enable post-incident investigation of what tasks ran and which template authored them.

**Privacy invariants**:
- Logs MUST NOT contain secrets, passwords, API tokens, or PII
- Personal data MUST be redacted before emission
- Only structural identifiers (template names, versions, paths) are permitted

### Redaction

Log redaction MUST be systematic rather than per-log-statement. A centralized redaction mechanism MUST scrub sensitive patterns (credentials, tokens, URL userinfo) from all log output, including captured subprocess output, before emission. Sensitive values MUST use a type that refuses to serialize to string representations, preventing accidental leakage.

### Log Output

**Terminal**: When stderr is a TTY and `NO_COLOR` is not set, use rich-formatted output with colors and structured layout. Non-TTY stderr receives a single JSON object per log event.

**Structured output**: All machine-readable log output is emitted as JSON to stderr. Logging is stderr-only by design — no file-based logging, rotation, or external aggregation. Consumers that need persistence may redirect stderr.

**Correlation ID passthrough**: When `BOILERPLATE_REQUEST_ID` is set in the environment, its value MUST be used as the correlation ID for all log entries in that invocation, overriding any auto-generated ID. This enables parent service correlation in pipeline and orchestration contexts.

### Subprocess Correlation

The per-invocation `request_id` MUST be propagated to all subprocesses as the environment variable `BOILERPLATE_REQUEST_ID`. When `BOILERPLATE_REQUEST_ID` is already set in the environment (e.g., by a parent orchestration process), Boilerplate MUST use the provided value rather than generating a new one. This enables correlation with parent process traces and distributed tracing systems. While external tools (Copier, Git, proto) do not consume this variable, it enables:

- Correlation of Boilerplate's structured logs with subprocess output captured at DEBUG level
- External log aggregation systems to group all activity from a single Boilerplate invocation

All subprocess stdout and stderr MUST be captured and logged at DEBUG level with the `request_id` and `phase` fields attached.

### Phase Vocabulary

The `phase` log field uses a closed enum aligned with the operation pipeline: `resolve`, `fetch`, `render`, `update`, `lock`, `catalog`, `env_apply`, plus `internal` for events outside any pipeline phase (bootstrap, configuration loading, third-party library records). Implementations MUST NOT emit `phase` values outside this set without first extending the enum here. This pipeline-phase vocabulary is distinct from the error-code phase prefixes defined above.

### Logging Invariants

- There MUST be exactly one terminal log event per high-level request (success or failure). Step-level events MAY occur en route, but the terminal event is the canonical record.
- Every terminal log event with `success: false` MUST carry a `BP_*` `error_code` field. No anonymous failures.
- `duration_ms` MUST appear only on the terminal log event, never on step events.

---

## Performance Contracts

**Invariants**:

- DX commands (status, validate, shell completions) MUST complete within 500ms on a developer machine with a local catalog of up to 200 templates.
- Long-running operations MUST show progress feedback.
- Algorithmic complexity MUST be linear in the size of the template graph.

### Retry Policy

Only errors marked `retryable: true` in the error code registry MAY be retried. Non-retryable errors (validation failures, not-found, cycles, conflicts) MUST fail immediately.

Retryable errors use exponential backoff with jitter. Between retry attempts, the staging directory MUST be completely removed and recreated to prevent corrupted results from partial output.

**Default parameters**:

| Parameter | Value | Description |
|-----------|-------|-------------|
| Base delay | 1 second | Initial delay before first retry |
| Maximum delay | 30 seconds | Cap on exponential growth |
| Maximum attempts | 3 | Total attempts including the initial try |
| Jitter | Full jitter | Random value between 0 and the computed delay (`delay = random(0, min(max_delay, base * 2^attempt))`) |

These defaults apply to all retryable operations (network fetches, transient subprocess failures). Individual operations MAY override `max_attempts` via configuration but MUST NOT disable jitter.

**Transient vs. deterministic classification**: Rendering failures (`BP_RENDER_TEMPLATE_FAILURE`) are retryable only for transient causes (subprocess timeout, OOM kill). Deterministic failures (Jinja2 syntax errors, missing variables) MUST fail immediately. Implementations MUST classify the error before deciding retryability.

### Network Timeouts

All network operations MUST enforce a configurable timeout to prevent indefinite hangs against unresponsive servers. Network timeouts and rendering timeouts are independent and independently configurable.

---

## Security Model

The full security model lives in [10-security.md](10-security.md). Operational invariants that gate the security checks (atomic-write pattern, concurrency control, retry policy, redaction mechanism, structured logging) remain in this document; the security rules cite them where needed.

---

## Atomic Staged Write Pattern

Both project creation ([§06](06-project-lifecycle.md)) and environment provisioning ([§08](08-environment-provisioning.md)) follow the same staged-write-with-intent-journal pattern. This section defines the shared invariants; each feature documents its specific file names, phase values, and recovery procedures.

**Core invariant**: All destructive operations follow a stage → validate → commit sequence. Work is performed in an isolated staging directory. An intent journal tracks the current phase for crash recovery. On success, staged output is atomically moved into place and the journal is deleted. On failure or interruption, the staging directory is cleaned up and the project directory is left in its pre-operation state.

**Stale cleanup**: Before creating a new staging directory, stale staging directories (older than 1 hour; see [06-project-lifecycle.md](06-project-lifecycle.md)) from previous interrupted operations are detected and cleaned up. For `update` and `add`, whose staging directory holds a git worktree ([06 §Staging worktree](06-project-lifecycle.md#staging-worktree)), the cleanup removes only worktrees Boilerplate created, identified by the journal and the owner check, and then runs `git worktree prune` in the project the journal's `destination` names, which drops the registration of a worktree whose folder is gone. A staging folder is stale only when it is older than the window and no running operation holds the exclusive lock each operation takes on its journal for the operation's lifetime: age alone would remove an update that is waiting at a prompt. `git worktree prune` runs only in this cleanup, never when an operation removes its own worktree, so the user's own worktree registrations are left alone.

**Intent journal invariants**:

- Written atomically and updated before each phase transition.
- Deleted on successful completion.
- If present but unparseable after a crash: left for user inspection without automated recovery.

**Signal handling**: Process termination signals MUST trigger the same cleanup as a failure. Untrappable signals are handled by stale cleanup and journal recovery on the next invocation.

**Retry behavior**: On retry, the previous attempt's staging directory and intent journal are cleaned up before creating a new staging directory.

**Single-file invocation**: When the staged unit is a single append-only file rather than a directory tree, the same stage → validate → commit principle applies via tmp-then-rename: read existing content, construct the updated content in memory, write to a sibling temporary file (`<filename>.tmp.{random_suffix}`) in the same directory, then atomically rename it to the target name. This prevents a crash during write from leaving a truncated file. Used by `.boilerplate/migrations.yml` and similar single-file audit logs.

### Concurrency Control

Boilerplate does not support concurrent mutating operations on the same target. Before any mutating operation, Boilerplate MUST acquire a platform-native advisory file lock (POSIX `fcntl`/`flock`; Windows `LockFileEx`) with a configurable timeout (default: 60 seconds, `BOILERPLATE_LOCK_TIMEOUT`). If the lock cannot be acquired, fail with `BP_CONCURRENCY_CONTENTION`. The lock is held for the duration of the operation and MUST be released when the operation completes or the holding process exits (the OS releases advisory file locks on process termination). On POSIX, ownership means the lock file's UID matches the effective UID. On Windows, ACL-based ownership applies.

---

## Platform Portability

Cross-cutting platform constraints that apply across all Boilerplate operations.

### Path Limits (Windows)

Boilerplate MUST fail fast before rendering if any rendered file path would exceed the Windows path limit and long paths are not enabled. `boilerplate doctor` MUST check this setting.

### Filesystem Differences

- Line endings: first-party templates carry a `.gitattributes` with `* text=auto eol=lf`, and third-party templates should ([03 §Template Authoring Constraints](03-template-system.md#template-authoring-constraints)). `boilerplate doctor` SHOULD validate that the file is present and declares it.
- Git submodule paths can be problematic on NTFS. Submodule initialization failures MUST produce clear errors with remediation (see [06-project-lifecycle.md](06-project-lifecycle.md)).

### Network Filesystems

Advisory file locking is unreliable on network filesystems. `boilerplate doctor` MUST detect network filesystems and warn. Staging directories SHOULD be created on local storage when possible.

### WSL2 Cross-Filesystem Access

Accessing Windows filesystems from WSL2 incurs significant I/O overhead. Template sources and project directories on the native WSL2 filesystem perform significantly better.

### Environment Variables (Windows)

Windows treats environment variables as case-insensitive. This cannot be enforced for `BOILERPLATE_`-prefixed variables on Windows.

---

## Exit Code Reference

Exit codes are defined in [02-data-models.md](02-data-models.md). An implementer MUST use those codes exactly -- no custom codes beyond those defined in §02.
