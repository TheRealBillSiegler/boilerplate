# Versioning and migration

Template versions evolve independently from the CLI. Breaking changes are managed through semantically versioned major bumps paired with automated migration support via Copier's three-way merge system.

## Version format

Templates use semantic versioning (`MAJOR.MINOR.PATCH`), independent from the CLI version:

```yaml
# boilerplate.yml
version: "0.1.0"  # Template version (independent from CLI)
name: project
extends:
  - base@1.0.0  # exact pin
```

`extends` accepts an exact version pin (`name@1.0.0`) or an unversioned reference (`name`); range specifiers such as `^1.0` are not accepted; [Design — Template system § `extends` syntax](../design/03-template-system.md#extends-syntax) reserves them.

**Key**: Each template versions itself, not tied to Boilerplate CLI versions.

### When to bump

A template version moves once per release, measured from the last released version of that template. Take the smallest step the whole unreleased change set requires (pre-1.0: MINOR for a breaking change, PATCH otherwise) and land it once. A later unreleased change raises that step if it needs a bigger one; it MUST NOT add another bump. Bumping per change or per pull request produces version numbers no consumer ever saw.

## Templates vs. projects

**Templates** (versioned in `boilerplate.yml`): source code with `boilerplate.yml`, `copier.yml`, and template files.

A project generated from a template is not itself versioned; it tracks each composed layer's source, version, and commit in one `.copier-answers.<layer>.yml` per layer. The whole-graph lock file is design: [Design — Data models § BoilerplateLock](../design/02-data-models.md#boilerplatelock).

## Migration-first philosophy

Breaking changes in templates are acceptable **IF** automated migration is provided.

### Why automated migration?

- **Preservation**: Projects preserve user customizations during updates
- **Safety**: Three-way merge (old template + user changes + new template) minimizes conflicts
- **Visibility**: Users see what changed and can make informed decisions
- **Scalability**: Enables evolution of templates without cascading manual work

For a worked rename migration, see [Template authoring § Rename through a staged move](authoring.md#rename-through-a-staged-move). A project built from one layer updates with Copier's own `copier update`. A project built from more than one layer has no shipped update command yet: each layer must render from the composition's merged schema, which only `boilerplate update` will provide ([ADR-007](../design/adr-007-update-model.md) records that design). Run `copier update` on a child layer alone, such as `streamlit`, and it exits 0 while skipping every path under the package directory and dropping the inherited answers from that layer's answers file.

## What constitutes a breaking change

### Breaking changes (require automated migration)

- Removing template variables (Copier questions)
- Renaming template variables
- Changing variable type or validation rules
- Moving or renaming generated files
- Restructuring project directory layout
- Changing template metadata format
- Changing composition constraints (`extends` version requirements)

### Non-breaking changes (minor or patch)

- Adding new template variables (optional, with defaults)
- Adding new files
- Improving templates (content updates)
- Bug fixes to generated files
- Adding new composition methods
- Deprecating template variables (with backward compat handler)

## Semantic versioning for templates

### Pre-1.0 template versioning (0.x)

Templates in early development use `0.x.y` versioning. Semantic versioning rules differ for pre-release versions:

| Bump | Example | Semantics | Migration |
|------|---------|-----------|-----------|
| PATCH | 0.1.0 → 0.1.1 | Compatible bug fixes | None needed |
| MINOR | 0.1.0 → 0.2.0 | **Breaking changes** | Copier migration required |
| MAJOR | 0.x.0 → 1.0.0 | Release-ready; begins stable SemVer | Copier migration required |

**Key**: In pre-1.0 versioning, minor bumps signal breaking changes (like major bumps in 1.x+). This reflects that 0.x APIs are unstable and may change frequently.

**Example:**

```yaml
# project template (early development)
version: "0.1.0"  # Initial release
---
version: "0.2.0"  # Minor bump = breaking change (migrate Copier)
---
version: "1.0.0"  # Major bump = stable release (migrate Copier)
---
version: "1.1.0"  # Minor bump = new features (no migration needed)
```

**For template authors**: If your template is pre-1.0, treat minor version bumps like major version bumps—provide Copier migration scripts for any breaking changes.

### PATCH version (bug fixes)

```yaml
# boilerplate.yml (v1.0.1)
version: "1.0.1"  # Patch bump
```

**When to bump PATCH:**

- Fix typo or incorrect content in generated files
- Fix bug in template logic
- Update dependencies without breaking changes

**No migration needed.**

### MINOR version (new features)

```yaml
# boilerplate.yml (v1.1.0)
version: "1.1.0"  # Minor bump
extends:
  - base@1.0.0  # exact pin, unchanged
```

**When to bump MINOR:**

- Add new optional template variables
- Add new template variants
- Extend composition options

**No migration needed** (backward compatible).

### MAJOR version (breaking changes)

```yaml
# boilerplate.yml (v2.0.0)
version: "2.0.0"  # Major bump
extends:
  - base@2.0.0  # exact pin, major bump
```

**When to bump MAJOR:**

- Remove template variables
- Rename template variables
- Restructure project layout
- Change variable types

**Migration is required** via Copier's update mechanism.

## Migration requirements for breaking changes

*`boilerplate update` is design-only ([ADR-007](../design/adr-007-update-model.md)): no shipped command of this tool runs migrations. Vanilla `copier update` runs them now for a project built from one layer; a child layer of a composed project needs the merged schema that command does not have, so its migrations wait for `boilerplate update`. The bundled layers ship theirs under the rules below; the rules bind template authors either way.*

### Copier migration scripts

Every breaking change ships as one or more entries under `_migrations` in `copier.yml`:

```text
template/
├── boilerplate.yml
├── copier.yml       # _migrations lives here
└── template/
    └── ...project files
```

```yaml
# copier.yml
_migrations:
  - version: "2.0.0"
    when: "{{ _stage == 'before' }}"
    command:
      - "{{ _copier_python }}"
      - -c
      - |
        # move/rename/rewrite logic, guarded by a state check
```

Each entry runs a `command` (a string run through the shell, or a list run directly), optionally gated by `version` (a PEP 440 version: the entry fires only when the update crosses it, from < version <= to) and `when` (which stage to run in; defaults to the `after` stage), with `working_directory` scoping where the command runs. Typical operations: rename or move a generated file, rewrite import paths or config keys after a rename, create a directory the updated layout needs. See Copier's [migrations documentation](https://copier.readthedocs.io/en/stable/configuring/#migrations) for the full mechanism, and [Template authoring § Rename through a staged move](authoring.md#rename-through-a-staged-move) for a complete worked entry.

### Authoring rules

A migration is fix-up code, not replayed history: an update may cross several versions at once, and every crossed migration runs against one of two trees — the pre-update tree for `before`-stage entries, the target tree for `after`-stage ones (the default) — never an intermediate one. Four rules follow, specified in [ADR-007](../design/adr-007-update-model.md#amendment-2026-07-28-version-jumps-stay-single-pass-migrations-are-jump-safe-by-authoring-contract):

1. **Jump-safe.** Inspect state before acting and stay idempotent — "if the old path exists, move it," never "the tree is at the previous version, so move it."
2. **Carried forward.** Keep every historical `_migrations` entry in every later release, in ascending version order — Copier reads the list only from the version being updated *to*, and executes it in declaration order rather than sorting by version.
3. **Layer-scoped.** Touch only files your own template owns. Copier has no ownership model; a migration that rewrites a file another layer overrode destroys that override silently.
4. **Conflict-aware.** Migrations run even when the merge left unresolved conflict markers, so a migration that parses a file must tolerate them — and a non-zero exit fails the whole update.

Three further rules govern what an update costs the project. Copier removes every path the new template version stops rendering — by name, without comparing content — and its merge treats a renamed file as added on both sides. The template, not the tool, is where a project's own work survives that. Both behaviours are Copier internals rather than public API, verified against Copier 9.18.1; `tests/boilerplate/templates/test_streamlit_update_migration.py` drives a real update and fails if they change.

5. **Rename through a staged move.** A template that renames or relocates a rendered path MUST ship a `before`-stage migration that moves the project's copy to the new name *and stages the move* (`git mv`, or a move followed by `git add -A -- <old> <new>`). Staging is the load-bearing half: Copier snapshots the index before it merges, so a staged move puts the project's content under the new name on the merge's "before updating" side, and the update pauses on a conflict carrying both versions. Without the migration the project's edited copy is deleted at exit 0 — no conflict marker, no `.rej` file, no message. The worked entry is in [Template authoring](authoring.md#keeping-a-projects-work).
6. **Render nothing the render's own `.gitignore` matches.** A file git ignores never enters the index, so Copier's merge cannot see it: no three-way merge, no conflict marker, no `.rej` file, and no history to recover it from. A template MUST NOT render a path its own ignore rules match, and MUST NOT ignore a path the render tells the user to commit.
7. **Say who owns each file.** For every rendered file, choose between template-owned — the template keeps changing it, so a project that edits it risks a conflict whenever a release touches the same lines, and on a file small enough that one diff hunk spans it, any release at all ([ADR-015](../design/adr-015-idiomatic-artifacts.md#verification-2026-07-28)) — and project-owned, listed in `_skip_if_exists`, which the template never merges into again once the project has its own copy. State the choice where an author will find it; silence means template-owned. `_skip_if_exists` only stops a merge into an existing file — Copier still recreates one the project deleted — so a file meant to be deleted (a sample module) stays template-owned; project-owned is for files users are expected to keep and rewrite instead, like a README or an entry point.

### Copier update process

When a project updates, Copier:

1. **Reads** the old template version from that layer's answers file
2. **Refuses to start** unless run with `--trust`, once the update crosses any declared migration — nothing is applied without it
3. **Runs `before`-stage migrations** for every version crossed, against the pre-update tree
4. **Performs three-way merge**:
   - Old template files (v1.x)
   - User changes (what they customized)
   - New template files (v2.0.0)
5. **Runs `after`-stage migrations** — the default stage — for every version crossed, against the merged tree
6. **Leaves conflict markers** in place for incompatibilities

Conflicts do not stop migrations, and Copier's exit code stays 0 through a conflicted update: the conflict pause is where the update model in [ADR-007](../design/adr-007-update-model.md) picks up.

## Template organization constraints

### One version stream per repository

**Constraint**: All templates in a Git repository MUST share a single version stream — one tag series versioning the repository as a whole. A template that versions independently MUST therefore resolve to its own repository.

**Rationale**: Copier's version mechanics are repository-wide. It finds "latest" by sorting the repository's Git tags (PEP 440), and it records the project's template version from the nearest tag (`git describe`). Two independently versioned templates sharing a repository would interleave their tags: an update could move one template to the other's release, and a project's answers file could record the wrong template's version. Copier's `_subdirectory` supports multiple templates in one repository only when they release in lockstep under one tag series — and even then at a cost: Copier reads `_subdirectory` from the repository's *root* `copier.yml`, so serving several templates from one repository means a root config with a dynamic `_subdirectory` and every template's questions `when:`-gated in that single file, which stops per-template question schemas from being self-contained artifacts.

The bundled `project` and `streamlit` templates version independently inside the Boilerplate repository, so they do not resolve to their own repositories; release-time extraction into per-template repositories is the design in [ADR-006](../design/adr-006-template-distribution.md), and the catalog-monorepo convention for aggregating independently versioned template repositories as submodules is in [Design — Template system § Submodule Federation and Tool Ownership](../design/03-template-system.md#submodule-federation-and-tool-ownership).

## Composition constraints

Templates declare dependencies via `extends`:

```yaml
# boilerplate.yml (streamlit template)
version: "0.2.0"
name: streamlit
extends:
  - project  # unversioned reference: the latest registered project template
```

A breaking change in a base template, and how it propagates through the templates that extend it, is specified in [Design — Project lifecycle § Structural changes to the `extends` chain](../design/06-project-lifecycle.md#step-3-build-updateplan) and the `UpdatePlan`/`LayerChange` fields in [Design — Data models](../design/02-data-models.md#updateplan).

## Template author responsibilities

### Before adding breaking changes

1. **Consider Alternatives**
   - Can the change be non-breaking?
   - Can it be added as optional new variable?

2. **Plan Migration**
   - Write Copier migration scripts
   - Test with real projects
   - Document what changed

3. **Check Dependents**
   - If other templates extend this template, bump their version too
   - Update their `extends` constraint
   - Provide their migration scripts

### For each breaking change

- [ ] Bump MAJOR version (e.g., 1.0.0 → 2.0.0)
- [ ] Add the migration to `_migrations` in `copier.yml`
- [ ] Test migration with `copier update` on sample projects
- [ ] Update referenced templates' `extends` constraints
- [ ] Document migration in migration guide (see [Migration guide template](migration-guide-template.md))
- [ ] Update template documentation

### Example: renaming a template variable

Renaming a template variable (for example, `project_name` → `project_id`) bumps the major version, then ships a migration that:

- Renames the key in the layer's `.copier-answers.<layer>.yml`
- Finds and replaces the old variable name across generated files
- Updates the question definition in `copier.yml`

See Copier's [migrations documentation](https://copier.readthedocs.io/en/stable/configuring/#migrations) for the mechanism.

## Deprecation vs. breaking changes

### Features being removed (deprecation required)

Deprecation applies when removing template features with **no automated migration path**:

```text
v1.0.0: Feature works normally
v1.1.0: Feature deprecated (still works, warning in docs)
v2.0.0: Feature removed (no migration script exists)
```

Deprecation period: **At least one minor version**.

### Breaking changes (with automated migration)

Template breaking changes accompanied by Copier migrations **do not require a deprecation period**:

```text
v1.0.0: Old structure (e.g., config.yml at root)
v2.0.0: New structure (config.yml in .boilerplate/)
        + Copier migration script handles the move
        → Users update with copier update (automatic migration)
```

**Rationale**: Copier's three-way merge system preserves user customizations during updates.

See [Versioning & compatibility policy § When to choose each path](../governance/versioning.md#when-to-choose-each-path) for the distinction between template and CLI breaking changes.

## Migration guide documentation

See [Migration guide template](migration-guide-template.md) for required format. Migration guides document:

- What template changed
- Why it changed
- What migration does automatically
- What requires manual intervention (if any)
- Validation procedures

## Testing template migrations

### Test suite requirements

A migration test does three things:

- Create a project from the previous template version.
- Run `copier update` against the new version.
- Assert the migration's effect on the resulting tree — renamed or moved files exist at their new paths, and a project edit to the old path survives as a merge conflict rather than a silent deletion.

`tests/boilerplate/templates/test_streamlit_update_migration.py` drives exactly this against the streamlit layer's smoke-test rename and is the worked example for a new migration test.

## Terminology

Template, Question, Copier, `copier.yml`, and `boilerplate.yml` follow the definitions in [design 01's glossary](../design/01-overview.md#glossary). A "template variable" above is a **Question**. Migration-specific terms used on this page:

**Copier Migration**: An entry under `_migrations` in `copier.yml` — a command, gated by an optional `version` and `when` — that transforms a rendered project during `copier update`.

**Extends**: A dependency on a base template, pinned to an exact version (e.g., `project@1.0.0`) or left unversioned.

**Migration-First**: The principle that a breaking change is acceptable when an automated Copier migration handles it.

**Three-Way Merge**: Copier's merge algorithm, combining old template files, the user's customized project files, and new template files into a result that preserves user customizations.

## Where next

Authoring a template that will need to version and migrate? Start with the [Template authoring guide](authoring.md), draft the change with the [Migration guide template](migration-guide-template.md), and check whether it also needs a CLI-side deprecation path in the [Versioning & compatibility policy](../governance/versioning.md). The target machinery this page prepares for — `BoilerplateLock` and `UpdatePlan` in [Design — Data models](../design/02-data-models.md), the `extends` syntax and submodule federation in [Design — Template system](../design/03-template-system.md), structural `extends`-chain changes in [Design — Project lifecycle](../design/06-project-lifecycle.md), and the update orchestration in [ADR-007](../design/adr-007-update-model.md) — is where the rest of the story lives.
