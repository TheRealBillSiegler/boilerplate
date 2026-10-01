---
paths:
  - "src/boilerplate/templates/**"
---

# Bundled template tenets

Policy: `docs/templates-hub/versioning.md` §Authoring rules. How-to, with the worked migration entry: `docs/templates-hub/authoring.md` §Keeping a project's work.

Neither the policy nor the how-to auto-loads when you edit a template. These two carry the most cost if missed:

- **Rehearse the update before you change any rendered path.** Build the layer as a tagged git repository, compose a project from the old tag, edit a rendered file, then update the layer through the composition's merged view (`update_layer` in `tests/boilerplate/templates/conftest.py`). A child layer declares only its own questions, so a vanilla `copier update` of it alone, without the composition's answers passed as data, exits 0 while skipping every path that uses `package_name`, rendering other files with the inherited answers empty, and keeping only the layer's own keys in its answers file; with the answers passed as data, the files that render derived answers conflict instead. A rename with no staged-move migration deletes that edit at exit 0, silently.
- **A renamed or relocated path ships its `before`-stage migration in the same change**, with a test driving a real update from the previous tag. `tests/boilerplate/templates/test_streamlit_update_migration.py` is the worked example.

## Voice

Two voices, never mixed. Boilerplate speaks in its own voice wherever the person is talking to Boilerplate, not to their project: every `copier.yml` `help:` string (Copier shows a `help` line as the prompt itself, so write it as a description of the value: a noun phrase plus any guidance, never a question and never a bare label) and `_scripts/post_generation.py`'s console narration. Every rendered file speaks in the generated project's own neutral voice instead — `README.md.jinja`, `app.py.jinja`, deploy scripts, scaffold comments — because the reader is now working in their own project, not running the scaffolder. A rendered file never names Boilerplate, the tool, except in its closing provenance line, which MAY name and link the tool. A rendered file also MAY say which template a file comes from (for example, that the base template contributes .gitignore); the closing provenance line naming the template and its answers file is one such mention.

A `help:` change also updates the `copier.yml` example in `docs/templates-hub/authoring.md`.

A Copier-declared input is a **Question**, not a variable (`CONTEXT.md`).
