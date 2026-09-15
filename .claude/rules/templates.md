---
paths:
  - "src/boilerplate/templates/**"
---

# Bundled template tenets

Policy: `docs/governance/template-versioning.md` §Authoring rules. How-to, with the worked migration entry: `docs/templates-hub/authoring.md` §Keeping a project's work.

Neither the policy nor the how-to auto-loads when you edit a template. These two carry the most cost if missed:

- **Rehearse the update before you change any rendered path.** Build the layer as a tagged git repository, render a project from the old tag, edit a rendered file, then run vanilla `copier update`. A rename with no staged-move migration deletes that edit at exit 0, silently.
- **A renamed or relocated path ships its `before`-stage migration in the same change**, with a test driving a real update from the previous tag. `tests/boilerplate/templates/test_streamlit_update_migration.py` is the worked example.
