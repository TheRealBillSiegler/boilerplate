# Security Model

!!! warning "Target model"
    This describes the target security model. For what is enforced today, see [ADR-003](adr-003-permissive-execution.md) and the [Status](../status.md) page.

## Purpose

This document specifies the cross-cutting security rules for Boilerplate. Security rules that are inseparable from local context live in their owning documents; this document does not restate them. Related specs:

- **Trust model** (binary trusted/untrusted classification, task-execution consent gating): [Template system and discovery](03-template-system.md)
- **Lock file integrity** (checksums, atomic writes): [Data models](02-data-models.md), [Project lifecycle](06-project-lifecycle.md)
- **Operational invariants that gate security checks** (atomic-write pattern, concurrency control, retry policy): [Operational quality](07-operational-quality.md)
- **YAML parsing, input validation, privacy, threat model**: this document

See [Data models](02-data-models.md) for exit codes. See [CLI reference](05-cli-reference.md) for CLI output conventions. See [Settings and configuration files](09-settings-and-configuration.md) for the operator-authored configuration files referenced below.

---

## Threat Model

Boilerplate operates in a trust boundary between template authors (who provide executable content via Jinja2 extensions and `_tasks`) and project consumers (who run `boilerplate new`). The threat scenarios that the design mitigates:

| Scenario | Vector | Impact |
|---|---|---|
| Tampered template source | Git repo compromise; commit replaced after publication | Malicious code in rendered project |
| Malicious Jinja2 extension | Unsafe extension loaded at render | Code execution at render time |
| Malicious `_tasks` execution | Template tasks run shell commands at user privilege | Code execution post-render |
| Dependency-chain poisoning | Transitive template replaced with malicious version | Integrity loss; unexpected behavior |
| Answers-file manipulation | User-supplied answer values hijack rendering | Misconfiguration; secret leakage |
| Lock-file forgery | Stale or fabricated lock claims success | Reproducibility failure; bypass of verification |
| Catalog metadata spoofing | False version, author, or trust claim | Trust erosion; misattribution |
| Credential leakage | Secrets in logs, URLs, or error messages | Authentication compromise |
| Supply-chain compromise | Boilerplate's own dependencies tampered | Tool-level code execution |

Each threat is mitigated by a specific design control:

| Threat | Mitigation | Reference |
|---|---|---|
| Tampered template source | Commit-pinned lock + per-layer checksum | §06 Lock Files; §02 `boilerplate.lock` |
| Malicious Jinja2 extension | Module-import blocklist + `SandboxedEnvironment` + user consent (`--allow-extensions`) | [§03 Jinja2 Extension Safety](03-template-system.md#jinja2-extension-safety) |
| Malicious `_tasks` execution | Default-deny task gating: tasks run only after the consent prompt or `--allow-tasks`; `--no-tasks` skips them entirely | [§03 Task Execution Safety](03-template-system.md#task-execution-safety) |
| Dependency-chain poisoning | Lock integrity verified before render; per-node provenance recorded | §06; `boilerplate lock verify` |
| Answers-file manipulation | Immutable answers on update (Copier contract); answer values bypass Jinja2 pipeline | [§03 Copier Integration Contract](03-template-system.md#copier-integration-contract); §Answer Preset Safety below |
| Lock-file forgery | Lock integrity check before render/update | `boilerplate lock verify` |
| Catalog metadata spoofing | Trusted/untrusted source classification; metadata hash + provenance per source | [§03 Trust and Verification Levels](03-template-system.md#trust-and-verification-levels) |
| Credential leakage | Git credential helper exclusivity; redaction processor; URL credential stripping | §Credential Handling below; [§07 Redaction](07-operational-quality.md#redaction) |
| Supply-chain compromise | Pinned dependencies + lock; out of scope for the spec but addressed in repo CI | (engineering practice) |

---

## Verification Pipeline

Security checks run at defined phases — never lazily. A check that detects a violation MUST fail the operation with a `BP_*` error before any irreversible work proceeds:

| Phase | Security check | Failure mode |
|---|---|---|
| Fetch | Verify resolved commit matches lock (if lock present); record content checksum | `BP_FETCH_CHECKSUM_MISMATCH` |
| Resolve | Every node in the dependency graph has provenance (source URL + commit-or-checksum; trust value optional) | `BP_RESOLVE_PROVENANCE_MISSING` |
| Render (pre) | Lock integrity verified; extension allowlist evaluated; user consent gates fired | `BP_LOCK_INTEGRITY_FAILED`, `BP_RENDER_UNSAFE_EXTENSION`, `BP_RENDER_TASKS_NOT_AUTHORIZED` |
| Update | New resolution diffed against existing lock; unexpected source changes flagged | `BP_UPDATE_SOURCE_DIVERGED` |

---

## Security Invariants

Across all operations, the following invariants MUST hold; violation is a contract bug:

- Every resolved template node in `boilerplate.lock` MUST record its source URL, its commit, and its checksum; a node missing any of these MUST fail resolution. The commit and checksum MUST be verified before render or update proceeds. A trust value (the optional `trust_tier` field) MUST be recorded when the source declares one, but its absence MUST NOT fail resolution (local sources declare no trust value).
- The full template source MUST be available before YAML parse or Copier invocation; the canonical statement of this submodule-initialization-before-render rule lives in [§03](03-template-system.md#boundary-invariants).
- A Jinja2 extension MUST NOT be loaded unless its package is on the system-wide allowlist AND user consent has been granted.
- Answer-preset values MUST never pass through `jinja2.Environment.from_string()` (architectural, not validation-based).

---

## Credential Handling

Boilerplate MUST use the Git credential helper (`git credential fill` / `git credential approve`) as the exclusive mechanism for authenticating to remote Git repositories. Embedding credentials directly in Git URLs (e.g., `https://token@host/repo`) is prohibited. Credentials in URLs are exposed in process argument lists (visible via `ps` or Task Manager), shell history, CI logs, and Git's own diagnostic output.

If the Git credential helper is not configured or fails to provide credentials, Boilerplate MUST fail with `BP_GIT_AUTH_FAILED` and provide remediation guidance directing the user to configure `git credential-manager` or the appropriate platform credential helper.

---

## File Permissions

Boilerplate MUST create files and directories with sensible default permissions unless the template explicitly overrides them. Staging directories MUST be restricted to owner-only access to prevent other users from reading or modifying in-progress renders. On Windows, Boilerplate relies on the default ACL inheritance of the parent directory.

---

## Trust Boundaries

All external inputs MUST be validated at trust boundaries before processing. A trust boundary exists wherever data enters Boilerplate from an external source: user CLI arguments, YAML files on disk, answer presets, and template content.

- **Remote template source responses**: Content fetched via `git clone` from remote repositories transitions from untrusted network data to local filesystem content. The initial fetch is trust-on-first-use (TOFU); subsequent fetches are validated against the lock file's commit hash and content checksum.
- **Proto plugin execution**: WASM plugins executed by proto during environment provisioning represent a trust boundary. Plugins are fetched from the proto plugin registry and execute tool installation logic. *Reserved for Phase 4 (remote / third-party sources):* a proto WASM plugin allowlist that constrains which plugins are permitted. Currently, toolchains are provisioned from local, operator-authored profiles only.

---

## Checksum Scope

**Checksum scope clarification**: Two distinct checksums appear in Boilerplate's data model:

1. **Template source checksum**: computed from the template directory contents at the locked commit (pre-render). The exclusion list for this checksum is: `.git/`, `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `node_modules/`. See [§06 Project Lifecycle](06-project-lifecycle.md) for the authoritative list.
2. **Rendered output checksum**: computed from the project directory contents after rendering. The exclusion list for this checksum SHOULD be extensible: template authors MAY declare `checksum_excludes` in their `boilerplate.yml` to add project-specific exclusions (e.g., `.venv/`, `.tox/`, `node_modules/`, `.pytest_cache/`). Boilerplate ships with default exclusions: `.git/`, `__pycache__/`, `.boilerplate/`. Exclusions are matched as prefix paths relative to the project root.

---

## Catalog Source Configuration

Catalog sources beyond the default filesystem directories are configured in a `boilerplate-sources.yml` file. This file defines catalog sources with their type, location, priority, and trust classification. The full schema, validation rules, and read protocol are specified in [09-settings-and-configuration.md §Catalog Source Configuration File](09-settings-and-configuration.md#catalog-source-configuration-file), including credential references, file permissions, and trusted/untrusted classification.

---

## YAML Parsing Security

YAML parsing MUST follow the security rules defined in [03-template-system.md §YAML Parsing Rules](03-template-system.md#yaml-parsing-rules).

---

## Jinja2 Sandbox

See [§03 Template System §Jinja2 Sandbox](03-template-system.md#jinja2-sandbox) for the normative spec.

---

## Answer Preset Safety

Answer preset values MUST be treated as literal strings and passed to Copier without Jinja2 rendering. Implementations MUST NOT attempt to detect or reject Jinja2 syntax in answer values (a value like `{{ example }}` may be a legitimate literal string, e.g., documenting a Jinja2 template). Instead, the safety guarantee is architectural: answer values bypass the Jinja2 rendering pipeline entirely. They are injected as pre-resolved answers into Copier's data context, never passed through `jinja2.Environment.from_string()`.

> **Double-rendering risk**: An answer value containing Jinja2-like syntax (e.g., `{{ secret }}`) is passed to Copier as a literal and never re-rendered, so its curly braces appear in output as text, not as a Jinja2 expression. This single-pass guarantee is a property of Copier's pipeline, not Boilerplate's. Implementations MUST verify this behavior against the supported Copier version range in integration tests.

Note: each layer's `.copier-answers.<layer>.yml` is a separate artifact owned by Copier (per the per-layer pattern). Boilerplate MUST NOT write to or validate any of them.

---

## Input Validation

All user-provided inputs -- CLI arguments, interactive prompts, and file-based inputs -- MUST be validated against expected formats before use. The `BP_INPUT_INVALID_FORMAT` error code MUST be raised for any input that fails validation.

---

## Privacy

- Logs, error messages, and diagnostic output MUST NOT contain secrets, passwords, API tokens, or PII.
- Personal data MUST be redacted before emission to any output channel (terminal, log file, structured log event).

Answers to questions marked `secret: true` (Copier's secret question flag) MUST NOT reach any file Boilerplate writes. Copier leaves them out of each `.copier-answers.<layer>.yml`, which is why that file is safe to pass to `--data-file` as an answer preset; a secret answer is supplied again with `--data` on the next run.

See also [§07 Redaction](07-operational-quality.md#redaction) for the systematic log redaction mechanism and [§07 Structured Logging](07-operational-quality.md#structured-logging) for required log fields and privacy invariants.

---

## Error Message Hygiene

Error messages presented to users MUST NOT leak internal file paths, stack traces, or implementation details. Diagnostic details SHOULD be available only via `--verbose` or `DEBUG`-level logging.

In `--verbose` mode, Boilerplate MAY include additional diagnostic context such as resolved template paths, Copier invocation arguments (excluding credentials), and timing details. Verbose output MUST NOT include: credential values, answer values marked as secret (`secret: true`), full file contents, or environment variable values. Template source URLs are acceptable in verbose output but MUST have any embedded credentials stripped.

---

## CI/CD Lock Verification

**RECOMMENDED CI gate**: Include `boilerplate lock verify` as a step in your CI pipeline. This step SHOULD run before any `boilerplate update` invocation in CI.

`boilerplate lock verify` checks:

- All template layer sources are reachable and contain the locked commits
- Template layer content checksums match recorded values
- Each `.copier-answers.<layer>.yml` hash matches its entry in `copier_answers_file_hashes` (if present)

It does NOT verify:

- Lock file integrity (no cryptographic signature; the file is trusted as-is)
- That re-rendering would produce identical output (Copier behavioral differences across versions may affect output)
- Answer correctness (only that answers haven't changed since last operation)

`lock verify` is a supply chain drift detector, not a full integrity guarantee. For stronger assurance, combine with content signing (planned for a future release). Example GitHub Actions step:

```yaml
- name: Verify template lock integrity
  run: boilerplate lock verify
```
