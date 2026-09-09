# Template versioning & migration policy

## Overview

This document defines versioning, breaking changes, and migration policies for Boilerplate templates.

**Principle**: Template versions evolve independently from the CLI. Breaking changes are managed through semantically versioned major bumps paired with automated migration support via Copier's three-way merge system.

The policy itself — version formats, breaking-change definitions, author responsibilities — governs today's templates. The machinery it prepares for (`copier update` orchestration, migration scripts, `boilerplate.lock`) is design-only: [Implementation status](../status.md) maps what exists, and [ADR-006](../design/adr-006-template-distribution.md) and [ADR-007](../design/adr-007-update-model.md) record the distribution and update designs. Sections below that describe that machinery are marked design-only.

!!! note
    For CLI tool versioning, see the [Versioning & Compatibility Policy](./versioning.md).

---

## Template versioning basics

### Version format

Templates use semantic versioning (`MAJOR.MINOR.PATCH`), independent from the CLI version:

```yaml
# boilerplate.yml
version: "0.1.0"  # Template version (independent from CLI)
name: project
extends:
  - base@0.1.0  # Exact-pin dependency on the base template
```

**Key**: Each template versions itself, not tied to Boilerplate CLI versions.

### Templates vs projects

- **Templates** (versioned in `boilerplate.yml`): Source code with `boilerplate.yml`, `copier.yml`, and templates
- **Projects** (not versioned): Instances created from templates, tracked via one `.copier-answers.<layer>.yml` per composed layer (`boilerplate.lock` is planned — see the design specs)

```text
Template (v0.1.0)
├── boilerplate.yml  ← Declares template version
├── copier.yml       ← Copier questions
├── project/         ← Template files
└── migrations/      ← Copier migration scripts (for breaking changes)

Project (created from template v0.1.0)
├── .copier-answers.<layer>.yml  ← Tracks each layer's source/version/commit
├── boilerplate.lock             ← Tracks full dependency graph (planned)
└── ...project files
```

---

## Migration-first philosophy

Breaking changes in templates are acceptable **IF** automated migration is provided.

### Why automated migration?

- **Preservation**: Projects preserve user customizations during updates
- **Safety**: Three-way merge (old template + user changes + new template) minimizes conflicts
- **Visibility**: Users see what changed and can make informed decisions
- **Scalability**: Enables evolution of templates without cascading manual work

### Example: renaming a configuration file

**Old Template (v1.0.0):**

```text
template/
├── config.yml      ← Old config file
└── copier.yml
```

**New Template (v2.0.0):**

```text
template/
├── .boilerplate/
│   └── config.yml  ← Moved to subdirectory
└── copier.yml
└── migrations/
    └── 001_move_config_to_subdirectory.py  ← Copier migration
```

**Migration Script (`migrations/001_move_config_to_subdirectory.py`):**

```python
"""Move config.yml to .boilerplate/config.yml"""

def migrate(project_dir):
    """Migrate project from v1 to v2."""
    import shutil
    from pathlib import Path
    
    old_path = Path(project_dir) / "config.yml"
    new_path = Path(project_dir) / ".boilerplate"
    
    if old_path.exists():
        new_path.mkdir(exist_ok=True)
        shutil.move(str(old_path), str(new_path / "config.yml"))
```

**User runs:**

```powershell
copier update
# Migration script automatically moves config.yml
# User sees: "Moved config.yml → .boilerplate/config.yml"
```

`boilerplate update` is designed but not yet implemented (see [ADR-007](../design/adr-007-update-model.md)); until it ships, use Copier's per-template `copier update`.

---

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

---

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
  - base@1.0.0  # Base template pin unchanged
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
  - base@2.0.0  # Major bump in composition pin
```

**When to bump MAJOR:**

- Remove template variables
- Rename template variables
- Restructure project layout
- Change variable types

**Migration is required** via Copier update mechanism.

---

## Migration requirements for breaking changes

*Design-only today: no shipped command runs migrations. This section specifies what template authors provide once the update spine ships ([ADR-007](../design/adr-007-update-model.md)).*

### Copier migration scripts

Every breaking change requires Copier migration scripts:

```text
template/
├── boilerplate.yml
├── copier.yml
├── migrations/
│   ├── 001_rename_config_variable.py
│   ├── 002_restructure_src_layout.py
│   └── 003_update_imports.py
└── template/
    └── ...project files
```

Typical operations a migration script performs:

- Rename or move a generated file
- Rewrite import paths or config keys after a rename
- Create a new directory required by the updated layout

See the worked config-rename example above and Copier's [migrations documentation](https://copier.readthedocs.io/en/stable/configuring/#migrations) for the mechanism and script conventions.

### Authoring rules

A migration is fix-up code, not replayed history: an update may cross several versions at once, and every crossed migration runs against one of two trees — the pre-update tree for `before`-stage entries, the target tree for `after`-stage ones (the default) — never an intermediate one. Four rules follow, specified in [ADR-007](../design/adr-007-update-model.md#amendment-2026-07-28-version-jumps-stay-single-pass-migrations-are-jump-safe-by-authoring-contract):

1. **Jump-safe.** Inspect state before acting and stay idempotent — "if the old path exists, move it," never "the tree is at the previous version, so move it."
2. **Carried forward.** Keep every historical `_migrations` entry in every later release, in ascending version order — Copier reads the list only from the version being updated *to*, and executes it in declaration order rather than sorting by version.
3. **Layer-scoped.** Touch only files your own template owns. Copier has no ownership model; a migration that rewrites a file another layer overrode destroys that override silently.
4. **Conflict-aware.** Migrations run even when the merge left unresolved conflict markers, so a migration that parses a file must tolerate them — and a non-zero exit fails the whole update.

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

Conflicts do not stop migrations, and Copier's exit code stays 0 through a conflicted update; the pause is detected and enforced by `boilerplate update` ([ADR-007](../design/adr-007-update-model.md)).

---

## Template organization constraints

### One version stream per repository

**Constraint**: All templates in a Git repository MUST share a single version stream — one tag series versioning the repository as a whole. A template that versions independently MUST therefore resolve to its own repository.

**Rationale**: Copier's version mechanics are repository-wide. It finds "latest" by sorting the repository's Git tags (PEP 440), and it records the project's template version from the nearest tag (`git describe`). Two independently versioned templates sharing a repository would interleave their tags: an update could move one template to the other's release, and a project's answers file could record the wrong template's version. Copier's `_subdirectory` supports multiple templates in one repository only when they release in lockstep under one tag series — and even then at a cost: Copier reads `_subdirectory` from the repository's *root* `copier.yml`, so serving several templates from one repository means a root config with a dynamic `_subdirectory` and every template's questions `when:`-gated in that single file, which stops per-template question schemas from being self-contained artifacts (see [ADR-006 § Options considered](../design/adr-006-template-distribution.md#options-considered)).

**How first-party templates satisfy this**: they are authored together in one repository and, per [ADR-006](../design/adr-006-template-distribution.md), extracted at release time into per-template repositories carrying their own history and `vX.Y.Z` tags (design-only today — see [Implementation status](../status.md)). A catalog monorepo aggregating independently versioned template repositories as submodules is a deferred organization convention for remote sources — see [Design Spec — Template System § Submodule Federation and Tool Ownership](../design/03-template-system.md#submodule-federation-and-tool-ownership).

---

## Composition & version constraints

### Depends on base template

Templates declare dependencies via `extends`:

```yaml
# boilerplate.yml
version: "1.1.0"
name: child
extends:
  - base@1.0.0  # Exact pin on the base layer
```

### Version constraints

`extends` entries are either a bare template name, which resolves to that template's latest registered version, or an exact `name@X.Y.Z` pin — the version must match precisely:

```yaml
extends:
  - base       # Latest registered version of base
```

```yaml
extends:
  - base@1.0.0 # Exact version match only
```

Range and compatibility operators (`^1.0`, `~1.2.0`, `>=1.0,<2.0`) are not implemented — `TemplateSpecifier` parses only an exact PEP 440 version after `@` (`src/boilerplate/types/template_specifier.py`). Version specifiers in `extends` are planned; see the [roadmap backlog](../roadmap.md#backlog).

### Composition implications

When a base template has breaking changes:

1. **New projects** automatically get new base version
2. **Existing projects** can stay on old version (no forced updates)
3. **Projects wanting to update** run `copier update` (design-only today — see [ADR-007](../design/adr-007-update-model.md)) which:
   - Updates base template + all migrations
   - Updates all dependent templates
   - Regenerates `boilerplate.lock` with the new dependency graph

**Example:**

```yaml
# OLD: project@1.0.0
# streamlit v0.2.0 extends project@1.0.0

# NEW: project@2.0.0 (breaking changes)
# streamlit v1.0.0 extends project@2.0.0 (re-pinned for the major bump)

# Existing project on streamlit v0.2.0 + project v1.0.0:
# User runs: copier update
# Gets: streamlit v1.0.0 + project v2.0.0 + all migrations
```

---

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
- [ ] Create Copier migration script in `migrations/`
- [ ] Test migration with `copier update` on sample projects
- [ ] Update referenced templates' `extends` constraints
- [ ] Document migration in migration guide (see [Migration Guide Template](./migration-guide-template.md))
- [ ] Update template documentation

### Example: renaming a template variable

Renaming a template variable (for example `project_name` → `project_id`) follows the same shape as the config-rename example above: bump the major version, then add a migration that:

- Renames the key in the layer's `.copier-answers.<layer>.yml`
- Finds and replaces the old variable name across generated files
- Updates the question definition in `copier.yml`

See Copier's [migrations documentation](https://copier.readthedocs.io/en/stable/configuring/#migrations) for the mechanism.

---

## Deprecation vs. breaking changes (with migration)

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

See [Versioning & Compatibility Policy § When to Choose Each Path](./versioning.md#when-to-choose-each-path) for the distinction between template and CLI breaking changes.

---

## boilerplate.lock and dependency tracking

**Planned behavior.** No lock file is written today; this section describes the target design (see the design specs and roadmap Phase 1). See [Data models § Lock File Model](../design/02-data-models.md#lock-file-model) for the schema `boilerplate.lock` will use.

---

## Migration guide documentation

See [Migration Guide Template](./migration-guide-template.md) for required format. Migration guides document:

- What template changed
- Why it changed
- What migration does automatically
- What requires manual intervention (if any)
- Validation procedures

---

## Testing template migrations

*Design-only today — migration tests become meaningful once the update spine ships.*

### Test suite requirements

```python
# tests/migrations/test_template_updates.py
"""Test template migrations."""

def test_migrate_v1_to_v2():
    """Test migration from template v1 to v2."""
    # 1. Create project with v1 template
    result = subprocess.run(
        ["copier", "copy", "--data", "version=1.0.0", 
         "template-repo", "test-project"],
        capture_output=True
    )
    assert result.returncode == 0
    
    # 2. Run copier update (simulates template upgrade)
    result = subprocess.run(
        ["copier", "update"],
        cwd="test-project",
        capture_output=True
    )
    assert result.returncode == 0
    
    # 3. Verify migration results
    config_file = Path("test-project") / ".boilerplate" / "config.yml"
    assert config_file.exists(), "Migration should create .boilerplate/config.yml"
    
    old_config_file = Path("test-project") / "config.yml"
    assert not old_config_file.exists(), "Migration should remove old config.yml"
```

---

## Terminology glossary (template-specific)

Key terms used in template versioning:

**Boilerplate.yml**: Template metadata file declaring template name, version, and composition details.

**Copier**: 3rd-party templating tool using `.yml` files for project generation with smart migrations.

**copier.yml**: Copier configuration file declaring template questions (variables) and their types.

**Copier Migration**: Custom Python script (in `migrations/` directory) that transforms generated projects during template updates.

**Extends**: Template composition dependency on a base template, by name or by exact version pin (e.g., `project@1.0.0`).

**Migration-First**: Principle that breaking changes are acceptable IF automated migration via Copier handles them.

**Three-Way Merge**: Copier's merge algorithm combining:

1. Old template files
2. User-customized files (from current project)
3. New template files
Produces merge result preserving user customizations.

**Template Variable**: Question in `copier.yml` that users answer; value stored in the layer's `.copier-answers.<layer>.yml`.

**boilerplate.lock** (planned): Project file recording full dependency graph (all templates + versions) for reproducible updates.

---

## Related documents

- [Versioning & Compatibility Policy](./versioning.md) - Breaking-change paths, approval, and the deprecation process
- [Migration Guide Template](./migration-guide-template.md) - Template for documenting migrations
- [Contributing Guidelines](./contributing.md) - How to contribute template changes
- [Design Spec — Template System](../design/03-template-system.md) - Authoritative template architecture and lifecycle

---

[← Back to Governance](contributing.md)
