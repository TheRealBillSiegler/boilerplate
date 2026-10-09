---
paths:
  - "src/boilerplate/templates/**"
---

# Bundled template tenets

Policy: `docs/templates-hub/versioning.md` §Authoring rules. How-to, with the worked migration entry: `docs/templates-hub/authoring.md` §Keeping a project's work.

Neither the policy nor the how-to auto-loads when you edit a template. These two carry the most cost if missed:

- **Rehearse the update before you change any rendered path.** A rename with no staged-move migration deletes the project's edit at exit 0, silently, so walk the update in a test first, with the helpers in `tests/boilerplate/templates/conftest.py`:
  - Build the layer as a tagged git repository, and compose a project from a plain copy of the old release; composing directly from the old tag fails because `boilerplate new` cannot compose from git-backed template directories (`docs/design/adr-015-idiomatic-artifacts.md` §Verification (2026-09-04)); drop this workaround when that limit lifts.
  - Rehome the layer to its tag (`rehome_layer`).
  - Edit a rendered file.
  - Update the layer through the layer's scoped view (`update_layer`). A child layer declares only its own questions, so a vanilla `copier update` of it alone, without the composition's answers passed as data, exits 0 while skipping every path that uses `package_name`, rendering other files with the inherited answers empty, and keeping only the layer's own keys in its answers file; with the answers passed as data, the files that render derived answers conflict instead.
- **A renamed or relocated path ships its `before`-stage migration in the same change**, with a test driving a real update from the previous tag. `tests/boilerplate/templates/test_streamlit_update_migration.py` is the worked example.

## Voice

Two voices, never mixed. Boilerplate speaks in its own voice wherever the person is talking to Boilerplate, not to their project: every `copier.yml` `help:` string (Copier shows a `help` line as the prompt itself, so write it as a description of the value: a noun phrase plus any guidance, never a question and never a bare label) and `_scripts/post_generation.py`'s console narration. Every rendered file speaks in the generated project's own neutral voice instead — `README.md.jinja`, `app.py.jinja`, deploy scripts, scaffold comments — because the reader is now working in their own project, not running the scaffolder. A rendered file never names Boilerplate, the tool, except in its closing provenance line, which MAY name and link the tool; a rendered file MAY name a template anywhere, for example to say that the base template contributes .gitignore or, in the provenance line, to give the template and its answers file.

A `help:` change also updates the `copier.yml` example in `docs/templates-hub/authoring.md`.

A Copier-declared input is a **Question**, not a variable (`CONTEXT.md`).
