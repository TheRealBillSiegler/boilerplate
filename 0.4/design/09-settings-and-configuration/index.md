# Settings and Configuration Files

## Purpose

The user-authored runtime configuration surface: the `Settings` object, a per-user profile (`profile.toml`), and the `boilerplate-sources.yml` catalog-source file — the YAML and environment-variable inputs the operator owns, separate from the domain schemas in [Data models](https://therealbillsiegler.github.io/boilerplate/0.4/design/02-data-models/index.md).

See [Product overview](https://therealbillsiegler.github.io/boilerplate/0.4/design/01-overview/index.md) for the glossary. See [Security model](https://therealbillsiegler.github.io/boilerplate/0.4/design/10-security/index.md) for the security constraints that apply to the configuration files specified here (YAML tag rejection, path traversal validation).

______________________________________________________________________

## Settings

The `Settings` object holds all runtime configuration. It is loaded once at CLI startup and passed to all application services. Settings MUST be immutable after construction.

**Loading order** (later sources override earlier):

1. Compiled-in defaults
1. `.env` file in the current working directory (if present) — standard `KEY=VALUE` format, one assignment per line, `#` for comments
1. OS environment variables

All `Settings` field names are prefixed with `BOILERPLATE_` when read from the environment, using the flat field name directly (e.g. `BOILERPLATE_DEBUG`). [Profile](#profile) has no environment-variable layer — it is TOML-file-only.

| Field                        | Env Var                                  | Type           | Default                                 | Description                                                                                                                                                                                                                                                                                                                                                           |
| ---------------------------- | ---------------------------------------- | -------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `default_templates_dir`      | `BOILERPLATE_DEFAULT_TEMPLATES_DIR`      | path           | `{user_data_dir}/boilerplate/templates` | The user's standing template directory, searched before `extra_template_dirs`. Starts empty; first-party templates do not live here.                                                                                                                                                                                                                                  |
| `extra_template_dirs`        | `BOILERPLATE_EXTRA_TEMPLATE_DIRS`        | list of paths  | `[]`                                    | Additional template directories searched after `default_templates_dir`. OS environment values are split on the platform path separator. When both sources provide `extra_template_dirs`, OS environment entries are placed before `.env` file entries in the resulting list (giving OS entries higher search priority). Deduplication preserves the first occurrence. |
| `debug`                      | `BOILERPLATE_DEBUG`                      | boolean        | `false`                                 | Enable debug-level logging; overridden to `true` by `--verbose` flag                                                                                                                                                                                                                                                                                                  |
| `render_timeout`             | `BOILERPLATE_RENDER_TIMEOUT`             | integer        | `300`                                   | Maximum seconds for a single template render                                                                                                                                                                                                                                                                                                                          |
| `proto_timeout`              | `BOILERPLATE_PROTO_TIMEOUT`              | integer        | `600`                                   | Maximum seconds for a proto install invocation. See [§08](https://therealbillsiegler.github.io/boilerplate/0.4/design/08-environment-provisioning/index.md).                                                                                                                                                                                                          |
| `fetch_timeout`              | `BOILERPLATE_FETCH_TIMEOUT`              | integer        | `60`                                    | Maximum seconds for a single network operation. See [§07](https://therealbillsiegler.github.io/boilerplate/0.4/design/07-operational-quality/index.md).                                                                                                                                                                                                               |
| `lock_timeout`               | `BOILERPLATE_LOCK_TIMEOUT`               | integer        | `60`                                    | Maximum seconds to acquire advisory lock. See [§06](https://therealbillsiegler.github.io/boilerplate/0.4/design/06-project-lifecycle/index.md).                                                                                                                                                                                                                       |
| `allowed_extension_packages` | `BOILERPLATE_ALLOWED_EXTENSION_PACKAGES` | list of string | `[]`                                    | System-wide allowlist of Python package names whose Jinja2 extensions are permitted during rendering. See [§03 Template System](https://therealbillsiegler.github.io/boilerplate/0.4/design/03-template-system/index.md).                                                                                                                                             |
| `request_id`                 | `BOILERPLATE_REQUEST_ID`                 | string or null | `null`                                  | Correlation ID for structured log events. When set (typically by CI pipelines or orchestration tools), the value is included in every structured log event as the `request_id` field. See [§07 Operational Quality](https://therealbillsiegler.github.io/boilerplate/0.4/design/07-operational-quality/index.md).                                                     |
| `accessible`                 | `BOILERPLATE_ACCESSIBLE`                 | boolean        | `false`                                 | When enabled (any value except unset, empty, whitespace-only, `0`, or `false`, case-insensitive), activates all accessibility accommodations: no color, append-mode progress, text-only status labels, no banner. See [§05 CLI Reference](https://therealbillsiegler.github.io/boilerplate/0.4/design/05-cli-reference/index.md).                                     |

**`template_dirs`** (computed, not configurable): the concatenation of `[default_templates_dir] + extra_template_dirs`. This is the ordered list of directories the catalog build process searches. First-party templates — the published per-template git repositories ([ADR-006](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-006-template-distribution/index.md)) — are registered by the catalog build as an implicit final source after all `template_dirs` entries — see [03 §Template Directory Resolution Order](https://therealbillsiegler.github.io/boilerplate/0.4/design/03-template-system/#template-directory-resolution-order); they are not a Settings path.

`{user_data_dir}` resolves to the platform-appropriate user data directory (e.g., `%LOCALAPPDATA%` on Windows, `~/.local/share` on Linux).

If loading the Settings object fails for any reason, the CLI MUST print an error and exit with code `2` (`CONFIG_ERROR`).

______________________________________________________________________

## Profile

Per-user default answers for template questions, read from `profile.toml` at the config root. Grammar: `[defaults]` (any template) and `[templates.<name>]` (one template, overrides `[defaults]`). Keys are open — they are template question names; boilerplate validates none of them. Loader: `boilerplate.settings.profile.load_profile(template_name)`; missing file yields `{}`, malformed TOML raises `ProfileError`.

The config root is platform-specific: `%APPDATA%\boilerplate` on Windows, and `$XDG_CONFIG_HOME/boilerplate` (falling back to `~/.config/boilerplate`) on POSIX.

**Precedence**, high to low: the user's interactive answer › `[templates.<name>]` › `[defaults]` › the template's own default. Defaults pre-fill prompts — the user can still override at the prompt; `--non-interactive` takes them as-is.

______________________________________________________________________

## Catalog Source Configuration File

**File location**: `{user_data_dir}/boilerplate/boilerplate-sources.yml`

This file defines the template and profile catalog sources that Boilerplate searches during resolution. It is a single YAML document with one top-level key.

**Top-level structure**:

| Field     | Type                | Required | Description                                |
| --------- | ------------------- | -------- | ------------------------------------------ |
| `sources` | list of SourceEntry | Yes      | Ordered list of catalog source definitions |

**SourceEntry schema**:

| Field             | Type           | Required | Default     | Constraints                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ----------------- | -------------- | -------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`            | string         | Yes      | —           | Human-readable source identifier. MUST be unique across all entries.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `type`            | enum           | Yes      | —           | One of: `filesystem`, `git`, `archive`. `wheel_bundle` is a deferred seed-cache type ([ADR-006](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-006-template-distribution/index.md)), not yet available for configuration. The `http`, `github`, and `oci` types are reserved for future versions.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `location`        | string         | Yes      | —           | URI or filesystem path to the source. Interpretation depends on `type`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `credentials`     | string or null | No       | `null`      | **Reserved for Phase 4 (remote / third-party sources).** Reference to a credential — an environment variable name or vault path. MUST NOT contain a literal secret value. See Validation Rules below.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `priority`        | integer        | No       | `100`       | Lower number = higher priority. Ties broken by registration order (position in the `sources` list).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `trust_level`     | enum           | No       | `untrusted` | `trusted` or `untrusted`. Governs sources configured in this file; the implicit first-party source — the published per-template repositories ([ADR-006](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-006-template-distribution/index.md)) — is `trusted` by default and does not appear here. Trusted sources may execute tasks with user consent; untrusted sources execute tasks only with explicit user authorization via `--allow-tasks` (or `--allow-untrusted`) — see [§03 Task Execution Safety](https://therealbillsiegler.github.io/boilerplate/0.4/design/03-template-system/#task-execution-safety). A lock file MAY record an independent free-form string field (`trust_tier`) for forward compatibility, but resolution logic treats only this binary enum. Absence of a recorded trust value MUST NOT fail resolution. |
| `expected_commit` | string or null | No       | `null`      | For TOFU (trust-on-first-use) pinning: the expected commit hash on first clone of a `git` source. When set, Boilerplate records the commit on first use and rejects subsequent fetches whose tip does not descend from it. Ignored for `filesystem` and `archive` types.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |

Source types that define additional fields (`checksum` for `archive`) are specified in the corresponding source model section: [ArchiveSource](https://therealbillsiegler.github.io/boilerplate/0.4/design/02-data-models/#archivesource). Those fields are included inline in the YAML entry alongside the common fields above.

**Example**:

```yaml
sources:
  - name: official
    type: git
    location: https://github.com/org/templates.git
    trust_level: trusted
    priority: 10
  - name: team-local
    type: git
    location: /home/dev/templates
    trust_level: untrusted
  - name: offline-archive
    type: archive
    location: /opt/boilerplate/archives/starter-kit.tar.gz
    checksum: "sha256:a1b2c3..."
```

**Validation rules**:

1. **Credential safety** (Phase 4): The `credentials` field is reserved for Phase 4 (remote / third-party sources). Until then, when the field is present, Boilerplate MUST reject values that appear to be literal credentials. Literal secrets MUST never appear in this file.
1. **Trust enforcement**: A source entry with `trust_level: trusted` enables task execution subject to the user consent prompt; `trust_level: untrusted` (the default) blocks task execution unless the user explicitly authorizes it with `--allow-tasks` (or `--allow-untrusted`); see [§03 Task Execution Safety](https://therealbillsiegler.github.io/boilerplate/0.4/design/03-template-system/#task-execution-safety). There is no intermediate tier.
1. **File permissions (POSIX)**: On POSIX systems, the file MUST be readable only by the owner. Boilerplate SHOULD warn or refuse to load the file if permissions are more permissive.
1. **Duplicate rejection**: Duplicate `name` values across entries MUST be rejected at parse time. Duplicate YAML keys within a single mapping MUST also be rejected.
1. **Unknown fields**: Unknown fields within a source entry SHOULD produce a warning but MUST NOT cause a hard failure, to allow forward compatibility with newer schema versions.

See [10-security.md §Catalog Source Configuration](https://therealbillsiegler.github.io/boilerplate/0.4/design/10-security/#catalog-source-configuration) for the full security constraints on catalog source configuration (YAML tag rejection, path traversal validation).
