# Migration guide template

Use this template when documenting breaking changes in **Boilerplate templates**. Boilerplate leverages Copier's automated template update mechanism to handle migrations. Migration guides focus on what the automation does, edge cases requiring manual intervention, and validation procedures.

!!! info "Important"
    This template is for **template migrations** (projects updating to new template versions via `copier update`).

    - For **CLI tool** migration guides (command renames, option changes), see the [Versioning & Compatibility Policy](./versioning.md).
    - For context on both template and CLI migration approaches, see [Versioning & Compatibility Policy § Two Breaking-Change Paths](./versioning.md#two-breaking-change-paths).

**Reference**: [Template Versioning Policy—Semantic versioning and compatibility](./template-versioning.md)

---

## Template

```markdown
# Migration guide: <feature or tool> v<OLD_VERSION> → v<NEW_VERSION>

## What's changing

[1–2 sentence summary of the breaking change and why it was necessary.]

### Example

Before (v<OLD_VERSION>):
\`\`\`python
# Old way
from boilerplate import render_template
result = render_template("my-template", answers={...})
\`\`\`

After (v<NEW_VERSION>):
\`\`\`python
# New way
from boilerplate import Composer
result = Composer("my-template", answers={...}).render()
\`\`\`

## Automated migration

Copier handles this migration automatically when you update your project:

\`\`\`powershell
# Update to latest template version
copier update
# (future) boilerplate update — not yet shipped, see design/adr-007-update-model.md
\`\`\`

### What the automation does

The update process will:

1. **Update configuration**: Automatically transform `<old_config>` to `<new_config>` format.
2. **Rename files**: Move `old_structure/` to `new_structure/` preserving your customizations.
3. **Update imports**: Replace deprecated import paths with new ones in `.py` files.
4. **Merge conflicts**: Present interactive prompts for conflicting customizations.

**No manual intervention needed** for these transformations.

### Files affected

| File pattern | Change | Automatic | Manual review needed |
|--------------|--------|-----------|----------------------|
| `pyproject.toml` | Version pins updated | ✓ | No |
| `src/**/*.py` | Import paths updated | ✓ | Verify custom imports |
| `.vscode/settings.json` | New settings added | ✓ | Merge with custom settings |
| `README.md` | Template sections refreshed | ✓ | Preserve custom content |

## Manual intervention (if needed)

### Scenario 1: Custom <component> modifications

**If** you have heavily customized `<component>`, the automated merge may require review:

\`\`\`powershell
# After running update, check for merge markers
git diff
\`\`\`

Look for conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`). Resolve by choosing the appropriate sections or merging both.

### Scenario 2: External dependencies on old API

**If** you have external scripts or tools calling the old API:

\`\`\`python
# Update external scripts from:
old_function(param1, param2)

# To:
new_function(param1=param1, param2=param2)
\`\`\`

These changes are **outside** the template-managed files and require manual updates.

## Testing and validation

Verify the automated migration succeeded:

\`\`\`powershell
# Run quality gates
uv run ruff check
uv run pyright
uv run pytest
\`\`\`

**Expected results**:
- ✓ No linting errors
- ✓ No type checking errors  
- ✓ All tests pass
- ✓ Application starts successfully: `uv run python -m <your_app>`

## Rollback procedure

If critical issues arise:

\`\`\`powershell
# Option 1: Revert the update commit
git revert HEAD
uv sync --locked

# Option 2: Restore from backup (if you created one)
git checkout <branch-before-update>
\`\`\`

Then open an issue with:
- The error encountered
- Your project structure (especially customizations)
- Output from `boilerplate --version` or `copier --version`

## Troubleshooting

### Merge conflicts during automated update

**Symptom**: Copier reports conflicts and stops the update.

**Cause**: Your customizations conflict with template changes.

**Solution**:
\`\`\`bash
# Review conflicts
git status
# Edit files with markers (<<<<<<<, =======, >>>>>>>)
# Choose appropriate sections
git add <resolved-files>
git commit -m "chore: resolve migration conflicts"
\`\`\`

### Type errors after migration

**Symptom**: `pyright` reports type mismatches in updated code.

**Cause**: API signature changes not fully applied to custom code.

**Solution**:
\`\`\`powershell
# Identify failing imports/calls
uv run python -m pyright --verbose
# Update your custom code to match new signatures (see examples above)
\`\`\`

### Tests fail after update

**Symptom**: Previously passing tests now fail.

**Cause**: Breaking changes in behavior, not just API.

**Solution**:
\`\`\`powershell
# Review test failures for deprecated patterns
uv run python -m pytest -v
# Update test assertions and mocks to match new behavior
\`\`\`

## Getting help

- Review the [<Feature> documentation](<link>).
- Search existing GitHub issues: [Link to GitHub search]
- Open a new issue with your error and environment details: [Link to new issue template]

## Summary of changes

| Component | What changed | Why |
|-----------|--------------|-----|
| Config | Property renamed | Improved clarity |
| API | Function signature | Enhanced flexibility |
| CLI | Command structure | Consistency with other tools |

## Timeline

| Version | Status | Support until |
|---------|--------|----------------|
| v1.x | Deprecated | [ISO-8601 date] |
| v2.0 | Current | Ongoing |

---

_Migration guide created: [ISO-8601 date]_

_For latest updates, see the [release notes](link)._
```

---

## Checklist: before publishing a migration guide

- [ ] Provide clear rationale for the breaking change.
- [ ] Include at least one before/after code example.
- [ ] Document what the automated migration does (file transformations, renames, updates).
- [ ] List all affected file patterns with automatic vs. manual review indicators.
- [ ] Identify scenarios requiring manual intervention (customizations, external dependencies).
- [ ] Provide validation steps (quality gates, application startup).
- [ ] Explain rollback procedure (git revert, restore from backup).
- [ ] Provide troubleshooting for common automated migration issues (merge conflicts, type errors).
- [ ] Link to detailed documentation for behavior changes.
- [ ] Specify deprecation timeline (when old version ends support).
- [ ] Test the automated migration on a sample project before publishing.
- [ ] Have a Boilerplate maintainer review before merging.
