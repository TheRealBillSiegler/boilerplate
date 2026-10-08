# Composition probes

Reproducible evidence for the composition design: each test re-runs one scenario probe against real Copier and asserts what the probe observed. These are not product tests. They sit outside `testpaths`, so `uv run pytest` and CI never run them.

A failure means a claim no longer holds (Copier, Git or the bundled templates changed). Revisit the design that rests on it, starting with [design 04 §Safe Update](../../docs/design/04-composition-engine.md#safe-update), before changing the expected value.

## Run

```console
uv run pytest probes/composition                      # every scenario
uv run pytest probes/composition/test_views.py        # one group
uv run pytest probes/composition -k TestRenamedQuestion  # one scenario, by its test class
```

Every scenario builds its template repositories and project under pytest's temp directory and points `TMP`, `TEMP` and `TMPDIR` there, so Copier's clones and update copies stay inside it. The scoped-view harness lives in `tests/boilerplate/templates/conftest.py`; `builders.py` holds the template builders, `extensions/` the probe-only Jinja extensions.

## Last verified

2026-10-06 on Windows 11, Python 3.14.3, Copier 9.18.1, Git 2.55.0.windows.3.

## Scenarios

Rows marked *added* are checks written with this suite, not taken from a probe log.

| ID | Question | Claim | Tests |
| --- | --- | --- | --- |
| C1 | What does a layer's scoped view hold? | Its own and its ancestors' questions and importable extensions only. | `test_views.py::TestScopedViews` |
| C2 | Does a descendant's context hook reach ancestor files? | Under the full view it rewrites project's `pyproject.toml` and `__init__.py`; under the scoped view only streamlit's own README. | `test_views.py::TestComposeUnderEachView::test_descendant_hook_reaches_only_the_files_its_view_renders`, `::test_views_write_the_same_files_and_differ_only_where_the_hook_reaches` |
| C3 | What does each answers file record? | Scoped: each layer's own view (project's file has no `container_registry`). Full: everything, everywhere. | `test_views.py::TestComposeUnderEachView::test_project_answers_file_records_the_questions_of_its_view`, `::test_streamlit_answers_file_records_its_whole_view` |
| C4 | Do both layers walk two releases cleanly, in either order and view? | Yes, user line kept; the full view keeps leaking into project's files. | `test_views.py::TestWalkThroughReleases` |
| S10a | Scoped update, no questionnaire pass: does streamlit's override of a new project question land? | No: project renders and records MIT; streamlit records MIT or Apache-2.0 by order. | `test_question_changes.py::TestAddedQuestionWithOverride::test_override_reaches_only_the_layers_its_mechanism_lets_it[S10a-*]` |
| S10b | Does one pass over the full view at the target fix it? | Yes: Apache-2.0 in the file and both answers files, either order. | same test `[S10b-*]`, `::test_questionnaire_pass_answers_the_new_question_with_the_override` |
| S10c | Does the full view see the override? | Yes: Apache-2.0 everywhere. | same test `[S10c-*]` |
| S11 | Does a diamond scope each layer to its transitive ancestors and update cleanly? | Yes in both views; an edit beside a changed line conflicts in both. | `test_views.py::TestDiamond`, `::TestDiamondUpdates` |
| S12 | Does removing a question break the old copy? | No: the old copy renders the recorded answer; the answers file drops the key. | `test_question_changes.py::TestRemovedQuestion` |
| S12 control | Does forced data reach the old copy? | No: it renders from the answers file, also with `data={}`. | `test_update_mechanics.py::TestEachCopyRendersItsOwnRelease`; *added*: `::test_forced_data_never_reaches_the_old_copy` |
| S13 | What happens to a recorded answer the new type or choices reject? | Forced: raw `ValueError` before any render. Castable: carried as the new type. Vanilla: silently replaced by the default. | `test_question_changes.py::TestRetypedQuestion` |
| S14 | Does a renamed question's value survive behind a migration? | Lock order or a migration in both layers: yes. Reverse order with project's migration only: streamlit records the default, which reaches the README. | `test_question_changes.py::TestRenamedQuestion` |
| S14 *added* | Does the update questionnaire pass respect the migration? | No: it forces the renamed question's default over the migrated answer in both layers, either order. | `test_question_changes.py::TestRenamedQuestion::test_update_questionnaire_pass_forces_the_renamed_questions_default` |
| S15 | What does a validator the recorded answer fails do? | Forced: `ValueError` before render. Vanilla: fails if the default is invalid too, else silently swaps in the default. | `test_question_changes.py::TestTightenedValidator` |
| S16 | Where do tasks run? | Compose: once each, in the destination, in the final layer's context. Update: the layer's own task in the old copy, in place and in the new copy. | `test_update_mechanics.py::TestTasks` |
| S17 | Can the unified questionnaire run interactively in-process? | Yes via prompt_toolkit pipe input; prompts show streamlit's overrides; `project_name` defaults to the scratch directory's name. | `test_prompting.py::TestInteractivePrompting` |
| S18 | Can Boilerplate compose from git-repository layers? | No: `git_index_modes`' path keys fail the composer's JSON check, also via `new`; without that attribute it works and records the latest tag. | `test_sources.py::TestComposeFromGitSources` |
| S19 | Can a descendant use an ancestor's file-path extension? | Only once it is registered as a module; registered per render's ref it updates, registered at the target only it silently stays. | `test_extensions.py::TestRegistrationAtCompose`, `::TestRegistrationPerRef` |
| S20 | Does a conflicting user edit pause the update? | Yes: inline markers, no exception, README unmerged with stages 1-3, no `.rej`. | `test_update_mechanics.py::TestConflictPauses` |
| S21 | What does the shipped `new` record, and is `update` a command? | Every answers file records the whole merged questionnaire; `update` exits 3, no such command. | `test_cli_baseline.py` |
| S22 | Does a three-layer chain scope and update cleanly? | Yes in both orders; the leaf's override reaches every layer that asks the question. | `test_views.py::TestChain`, `::TestChainUpdates` |
| D17 | Which spellings of another template's extension file resolve? | Walk-out relative: locally only. Drive-less absolute: everywhere. Drive-letter absolute (Windows): never, it splits at the drive colon. | `test_extensions.py::TestFilePathSpellings` |
| *added* | Do a layer's own answers beat its ancestors' in the scoped data? | Yes. | `test_update_mechanics.py::test_layers_own_recorded_answer_beats_its_ancestors` |
