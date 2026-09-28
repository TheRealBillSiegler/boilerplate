# Versioning & compatibility policy

## Overview

This is the umbrella policy for how Boilerplate is versioned and how it manages backward-incompatible change across the CLI, configuration/profiles, and the Python API. Template-specific versioning and migrations live in [Versioning and migration](../templates-hub/versioning.md).

**Principle**: [Semantic Versioning 2.0.0](https://semver.org/) — `MAJOR.MINOR.PATCH`. A breaking change requires a major bump paired with a migration path.

> **Pre-1.0 (`0.x`) scope.** Every stability guarantee here applies **from 1.0**. During `0.x` (initial development, per [SemVer §4](https://semver.org/#spec)) the **only** stable commitment is the **PyPI distribution name**; CLI commands, options, exit codes, error codes, output formats, and template variables MAY change in any `0.x` release without a major bump. The first public tag (`0.3.0`) does **not** freeze these surfaces.

---

## Two breaking-change paths

Boilerplate manages breaking changes along two paths, because the two surfaces upgrade differently:

- **Template changes — automated.** Copier's three-way merge applies migration scripts on `copier update`, so a template MAY introduce a breaking change *without* a deprecation period when it ships an automated migration.
- **CLI / Python-API changes — manual.** Scripts and library callers do not auto-upgrade, so these require a deprecation period (see [Deprecation Process](#deprecation-process)) before removal.

---

## When to choose each path

| Scenario | Path | Reasoning |
| --- | --- | --- |
| Renaming template variables | **Template** (Copier migration) | Copier transforms answers/files automatically |
| Moving/reorganizing template files | **Template** (Copier migration) | Migration scripts preserve user changes via merge |
| Removing a CLI option | **CLI** (deprecate → remove) | Used in user scripts; cannot auto-migrate |
| Changing a `profile.toml` field | **Depends** | Layout change → template migration; semantics change → CLI deprecation |
| Removing a public Python API | **CLI** (deprecate → remove) | Library consumers write against it; needs a warning first |

---

## What qualifies as breaking

**Breaking (major version):**

- Removing or changing the behavior of a CLI command or option
- Changing the default value of an option incompatibly
- Changing exit codes for error conditions
- Removing or changing the format of a `profile.toml` field
- Removing a public Python API method or class
- Removing template variables or restructuring generated file layout

**Not breaking (minor / patch):**

- Adding a new command, option, config field, or template variable (with a sensible default)
- Adding a new command alias
- Bug fixes, performance improvements, documentation
- Deprecating a feature (with a warning)

---

## Deprecation process

Applies to the manual (CLI / API / config) path. From 1.0, never remove a feature without at least one minor version of deprecation notice.

1. **Warn (minor release).** Keep the feature working but emit a warning naming the feature, the removal version, and the replacement:

    ```text
    ⚠️  'boilerplate <old>' is deprecated and will be removed in v2.0.0. Use 'boilerplate <new>' instead.
        See: <release-notes-url>
    ```

2. **Document.** Show both the current and deprecated approaches in the docs; mark the deprecation in the changelog.
3. **Remove (major release).** Remove the feature; the error message MUST reference the release notes entry that announced the removal.

**Minimum window:** at least one minor version with the warning in place before removal; 2–3 minor versions preferred. A good deprecation message states *what* is deprecated, *when* it is removed, *what to use instead*, and *where to learn more*.

Template breaking changes accompanied by a Copier migration do **not** require this period — see [Two Breaking-Change Paths](#two-breaking-change-paths).

---

## Breaking-change approval

Every breaking change requires: (1) a proposal stating the rationale, (2) discussion/feedback, (3) a migration path (automated for templates, documented for CLI/API), (4) deprecation in a prior minor version where applicable, and (5) the maintainer's approval. Proposal skeleton:

```markdown
## Breaking Change Proposal
**Version**: vX.0.0   **Component**: CLI / Template / Both
**Change**: <brief description>

### Rationale       — why is this necessary?
### Impact          — who/what breaks; estimated share of users; affected integrations
### Migration Path  — how users migrate (commands or migration-script outline)
### Alternatives    — what was considered and rejected
### Timeline        — deprecation release → removal release
```

---

## Compatibility test suite

Every release should keep a backward-compatibility suite that pins the surfaces above, plus a CI check that flags accidental breaks on each pull request. A compatibility suite is planned — see [Roadmap § Backlog](../roadmap.md#backlog).

---

## Changelog

`CHANGELOG.md` is generated by [release-please](https://github.com/googleapis/release-please) from conventional commits (grouped by commit type — Features, Bug Fixes, …); edit the prose on the release PR before merging (see [RELEASING.md](https://github.com/TheRealBillSiegler/boilerplate/blob/develop/RELEASING.md)). Mark incompatible entries **BREAKING** (a `!` commit or `BREAKING CHANGE:` footer does this automatically). Worked example of a good release entry:

```markdown
## [2.0.0] - 2026-08-01

### Added
- New `compose` command for template composition

### Changed
- **BREAKING:** renamed a command (old name removed)

### Deprecated
- A flag superseded by a clearer alias

### Removed
- **BREAKING:** a command removed after its deprecation window

### Fixed
- Template-resolution bug

### Security
- Bumped a dependency to address a CVE
```

A CLI breaking change is communicated through its changelog **BREAKING** entry and the release PR's release notes — no separate migration guide. A template breaking change publishes one using the [Migration Guide Template](../templates-hub/migration-guide-template.md).

---

## CLI stability surface

From 1.0, the stable CLI surface is: published commands and their core options, exit codes for error conditions, the environment profile format, and the machine-parseable output of commands documented as parseable. Internal Python modules (names prefixed `_`), error-message text, log format, and cache/temp-file layout are **not** stable and may change in any release.

The authoritative description of the **current** command surface is the [CLI Reference](../cli.md) (generated from the shipped CLI), mapped against the target in [Implementation Status](../status.md); the [Design Spec — CLI Reference](../design/05-cli-reference.md) describes the **target** contract.

---

## Related documents

- [Versioning and migration](../templates-hub/versioning.md) — template versioning, Copier migrations, composition constraints
- [Migration Guide Template](../templates-hub/migration-guide-template.md) — reusable skeleton for a template migration guide
- [Contributing Guidelines](./contributing.md)
- [Design Spec — CLI Reference](../design/05-cli-reference.md) — target CLI surface and behavior (current surface: [CLI Reference](../cli.md))

---

[← Back to Contribute](../contribute.md)
