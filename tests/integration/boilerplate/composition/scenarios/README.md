# Composition scenarios

Reproducible evidence for the composition design: each test re-runs one scenario against real Copier and git and asserts what was observed. These are not product tests. They live under `tests/integration/`, so `uv run pytest` collects them, and a collection hook marks each one `scenario`. Deselect them with `-m "not scenario"`; the CI test job and the local gate do, and run them separately only when a composition path changed ([CI pipeline](../../../../../docs/governance/ci.md#composition-scenarios)). A full run takes about five minutes on a developer laptop with xdist.

Most scenarios run on a made-up family of five Python-project templates (`core`, `service`, `docs`, `ci`, `app`) kept as data in `tests/fixtures/family/`. A few stay on the bundled `project` and `streamlit` layers, because the family cannot express what they claim; the table says which.

Five scenarios assert target behavior the code does not yet have. They are strict expected failures (`xfail`): they pass the run while the gap exists and fail it once the gap closes, at which point remove the marker.

A failure means a claim no longer holds (Copier, Git or the templates changed). Revisit the design that rests on it, starting with [design 04 §Safe Update](../../../../../docs/design/04-composition-engine.md#safe-update), before changing the expected value.

## Run

```console
uv run pytest tests/integration/boilerplate/composition -m scenario                         # every scenario
uv run pytest tests/integration/boilerplate/composition/scenarios/test_views.py -m scenario # one group
uv run pytest tests/integration/boilerplate/composition -m scenario -k TestRenamedQuestion  # one scenario, by its test class
```

Every scenario builds its template repositories and project under pytest's temp directory and points `TMP`, `TEMP` and `TMPDIR` there, so Copier's clones and update copies stay inside it; git checks out with LF endings there, whatever `core.autocrlf` says. The scoped-view harness lives in `tests/boilerplate/templates/conftest.py`; `builders.py` holds the project builders and readers, `family.py` (one folder up) builds the family, and `extensions/` holds the bundled-layer scenarios' probe-only Jinja extensions.

## How the harness works

The harness stands in for a compose-and-update engine that does not exist yet, so the scenarios drive Boilerplate's real pieces and Copier directly. Five views of it follow.

```text
┌─────────────────────────────────────────────────────────────┐
│ Scenario tests                                    test code │
│   composition/scenarios/test_*.py                           │
│   pick layers and tags · compose_family or                  │
│   update_family_layer · assert through the readers in       │
│   builders.py                                               │
├─────────────────────────────────────────────────────────────┤
│ Harness                                           test code │
│   tests/boilerplate/templates/conftest.py                   │
│   compose_project · update_layer · update_data ·            │
│   layer_view · ScopedWorker                                 │
├──────────────────────────────┬──────────────────────────────┤
│ Boilerplate engine      real │ Copier 9.18.1           real │
│   catalog · Resolver ·       │   Worker.run_copy ·          │
│   Composer · MergedTemplate  │   Worker.run_update · git    │
├──────────────────────────────┴──────────────────────────────┤
│ Fixtures                                          test code │
│   family fixture → family.py →                              │
│   tests/fixtures/family/<layer>/<version>/                  │
└─────────────────────────────────────────────────────────────┘
```

The harness stands in for the compose-and-update engine that doesn't exist yet. Views come from Boilerplate's real resolver and composer, and renders from Copier's real Worker.

```text
tests/fixtures/family/core/
  1.0.0/   full template
  1.1.0/   changed files only
  2.0.0/   changed files only
  3.0.0/   changed files only, plus _deleted.txt naming the paths it removes
  …
      │  _overlay_releases: copy the previous version,
      │  lay the changes on top, delete what _deleted.txt lists
      ▼
<session tmp>/releases/core/1.0.0/  1.1.0/  2.0.0/  …    one full folder per version
      │  build_layer_repo: one commit and one tag per version, oldest first
      ▼
<session tmp>/repos/core            git: 1.0.0 ── 1.1.0 ── 2.0.0 ── …
      ▼
Family(repos, tags, releases)       the `family` fixture, built once per xdist worker

per test:
templates_at(family, work, {"core": "1.1.0", "app": "1.1.0", …})
      ▼
<work>/templates/<layers at tags>/core/  service/  docs/  app/    one folder per layer, at its chosen tag
```

The family is stored as the first release in full and each later release as the files it changes, so a release reads as its own diff. A scenario asks for a templates directory with one tag per layer.

```text
compose_family(family, work, "app", tags, answers)
│
├─ templates_at(family, work, tags)    one folder per layer, each at its tag
├─ register the ancestors' file-path extension files as importable modules
│    added to a layer's render: core's to_package for every other layer,
│    docs' docs_anchor for app
│
├─ compose_project("app", dest, answers, templates, extra_extensions)
│    ├─ compose("app")                catalog → Resolver → Composer     real
│    │    order: core, service, docs, app
│    ├─ ask_merged_questionnaire      one pass over the full merged view   test
│    └─ for each layer, in that order:
│         layer_view(layer)           compose rooted at this layer:        real
│                                     its own and its ancestors' questions
│         MergedTemplate(view)                                             real
│         Worker.run_copy(dest, data = the pass's answers)                 copier
│           → the layer's files + .copier-answers.<layer>.yml
│         the merged tasks run once, on the last layer
│
└─ make_git_project(project, repos, tags)                                  test
     each answers file: _src_path → repos/<layer>, _commit → that layer's
     tag; then git init and commit
```

Composing asks every question once over the full merged view, then renders each layer under its own scoped view, so a layer's answers file records only the questions its view asks. Each layer is committed at its own tag.

```text
update_family_layer(family, project, root="app", layer="service",
                    before={…, "service": "1.0.0"}, after={…, "service": "1.1.0"}, work=work)
│
├─ templates_at for the before and after tags
├─ the layer's ancestors' file-path extension files registered as modules
└─ update_layer(project, root="app", layer="service", source=repos/service,
                ref="1.1.0", templates={"1.0.0": dir, "1.1.0": dir}, views_by_ref)
   │
   ├─ views_by_ref = {ref: layer_view("service", dir)}, one per release     real
   │
   ├─ update_data                                                           test
   │    recorded answers: core's file, then service's laid on top
   │    + the pass's answers for questions no file records
   │
   └─ ScopedWorker(vcs_ref="1.1.0", data, views_by_ref).run_update()        copier
        Copier rebuilds the worker for each render; every rebuilt worker
        builds its template from views_by_ref[its own ref].

        1  old copy   at _commit 1.0.0  view 1.0.0  answers file only; data never reaches it
        2  the target release's before-migrations run; Copier re-reads the answers file
        3  in place   at 1.1.0          view 1.1.0  data over the answers file
        4  new copy   at 1.1.0          view 1.1.0  same answers, in an empty folder
        5  the user's changes (old copy → project) are applied to the in-place
           render with git apply --reject; a rejected file is merged again with
           git merge-file, which leaves conflict markers and still exits 0
        6  after-migrations run
```

The step order is Copier's `_apply_update` in `copier/_main.py`. Because each render builds its own view, the old copy renders the questionnaire of the release it reconstructs, and forced data reaches only the in-place render and the new copy.

```text
pytest session
│
├─ tests/fixtures/conftest.py
│    collect_ignore_glob = ["family/*"]   keeps the template data out of collection
│
├─ tests/integration/boilerplate/composition/conftest.py
│    family             session scope, tmp_path_factory: built once per xdist worker
│
└─ tests/integration/boilerplate/composition/scenarios/conftest.py
     isolated_temp      autouse: TMP, TEMP and TMPDIR → the test's tmp_path,
                        so Copier's clones and old/new copies stay inside it
     collection hook    marks every test in the folder `scenario`
```

The fixtures a scenario gets: the family once per worker, a private temp directory per test, and the `scenario` marker for the run commands above.

## Last verified

2026-10-08 on Windows 11, Python 3.14.3, Copier 9.18.1, Git 2.55.0.windows.3.

## Scenarios

Rows marked *added* are checks written with this suite. Rows marked *expected failure* list a strict `xfail` that asserts the target behavior; the Claim column states what the code does today. Rows marked *bundled* run on the bundled `project` and `streamlit` layers (plus synthetic layers beside them) because the family cannot express the claim.

| ID | Question | Claim | Tests |
| --- | --- | --- | --- |
| C1 | What does a layer's scoped view hold? | Its own and its ancestors' questions only: core's view holds core's, service's adds `port`. *Bundled:* and importable extensions only. | `test_views.py::TestScopedViews`; *bundled*: `::TestImportableExtensionsInViews::test_project_view_carries_no_descendant_extension`, `::test_streamlit_view_adds_its_own_extension` |
| C2 | Does a descendant's context hook reach ancestor files? | Service's hook (`container_user`) is file-path, so it stays in service's files: both views write one file set and differ only in core's answers file. *Bundled:* an importable hook rewrites project's `pyproject.toml` and `__init__.py` under the full view, only streamlit's own README under the scoped view. | `test_views.py::TestComposeUnderEachView::test_views_write_the_same_files_and_differ_only_in_core_s_answers`, `::test_service_hook_defines_the_container_user_in_its_own_files`; *bundled*: `::TestImportableExtensionsInViews::test_descendant_hook_reaches_only_the_files_its_view_renders`, `::test_views_write_the_same_files_and_differ_only_where_the_hook_reaches` |
| C3 | What does each answers file record? | Scoped: each layer's own view (core's file has no `port`). Full: everything, everywhere. | `test_views.py::TestComposeUnderEachView::test_core_answers_file_records_the_questions_of_its_view`, `::test_service_answers_file_records_its_whole_view` |
| C4 | Do both layers update cleanly to their next releases, in either order and view? | Yes: user line kept once, core's `LICENSE` appears, service's `port` takes its new type, both answers files end at the new tags. *Bundled:* updates under the full view keep rendering a descendant's hook in project's files. | `test_views.py::TestWalkThroughReleases`; *bundled*: `::TestImportableExtensionsInViews::test_project_file_renders_the_description_its_view_allows` |
| S10a | Scoped update, no questionnaire pass: does app's override of a question core 1.1.0 adds land? | No: core renders and records MIT; app records MIT or Apache-2.0 by order. | `test_question_changes.py::TestAddedQuestionWithOverride::test_override_reaches_only_the_layers_its_mechanism_lets_it[S10a-*]` |
| S10b | Does one pass over the full view at the target fix it? | Yes: Apache-2.0 in `LICENSE` and both answers files, either order. | same test `[S10b-*]`, `::test_questionnaire_pass_answers_the_new_question_with_the_override` |
| S10c *bundled* | Does the full view see the override? | Yes: Apache-2.0 everywhere. The family cannot compose its app under the full view, which has no way to give app docs' filter. | `test_question_changes.py::TestAddedQuestionUnderTheFullView` |
| S11 | Does a diamond scope each layer to its transitive ancestors and update cleanly? | Yes, in the scoped view: each view adds its ancestry's questions, app renders through docs' filter, docs then app update with the user line kept and only they move. *Bundled:* the same in the full view, docs' importable filter reaches only views that descend from docs, and an edit beside a changed line conflicts in both views. | `test_views.py::TestDiamond`, `::TestDiamondUpdates`; *bundled*: `::TestBundledDiamond`, `::TestBundledDiamondUpdates` |
| S12 | Does removing a question break the old copy? | No: the old copy renders the recorded `use_tests: false` (no smoke test); the answers file drops the key; service, not yet updated, keeps it. | `test_question_changes.py::TestRemovedQuestion` |
| S12 control | Does forced data reach the old copy? | No: it renders from the answers file, also with `data={}`. | `test_update_mechanics.py::TestEachCopyRendersItsOwnRelease`; *added*: `::test_forced_data_never_reaches_the_old_copy` |
| S13 | What happens to a recorded answer the new type or choices reject? | Forced: raw `ValueError` before any render, for the declaring layer and a descendant. Castable: carried as the new type. Vanilla: silently replaced by the default. The project stays untouched unless the release ships a migration, which runs first: core 2.1.0 rewrites the recorded Python version before the forced one is rejected. | `test_question_changes.py::TestRetypedQuestion`; *bundled*: `::TestNarrowedChoiceOnTheBundledLayers` (the narrowed choice with no migration) |
| S14 | Does a renamed question's value survive behind a migration? | Lock order: yes. Reverse order, with only core shipping the migration: service records the default. | `test_question_changes.py::TestRenamedQuestion` |
| S14 *added*, *expected failure* | Should the update questionnaire pass respect the migration? | No: it forces the renamed question's default over the migrated answer in both layers, either order. | `test_question_changes.py::TestRenamedQuestion::test_update_questionnaire_pass_keeps_the_migrated_answer` (target: both layers record and render the migrated answer) |
| S15 | What does a validator the recorded answer fails do? | Forced: `ValueError` before render, for docs and app. Vanilla: silently swaps in the new default when it is valid. | `test_question_changes.py::TestTightenedValidator` |
| S16 | Where do tasks run? | Compose: once, in the destination, although five layers render. Update: the layer's own task in the old copy, in place and in the new copy; a layer with no task runs none. *Bundled:* the in-place output is undone by the merge when two layers append to one marker; on the family the appended line survives. | `test_update_mechanics.py::TestTasks`; *bundled*: `::test_in_place_task_output_is_undone_by_the_merge` |
| S17 | Can the unified questionnaire run interactively in-process? | Yes via prompt_toolkit pipe input; prompts show service's and app's overrides; `project_name` defaults to the scratch directory's name. | `test_prompting.py::TestInteractivePrompting` |
| S18, *expected failure* | Should Boilerplate compose from git-repository layers? | Not yet: `git_index_modes`' path keys fail the composer's JSON check, also via `new`; without that attribute it works and records each layer's latest tag. | `test_sources.py::TestComposeFromGitSources::test_compose_succeeds_from_git_repository_layers`, `::test_new_exits_zero_from_git_repository_layers` (target: composing and `new` succeed); the counterfactual `::test_without_git_index_modes_both_composes_record_the_latest_tag` passes |
| S19 | Can a descendant use an ancestor's file-path extension? | Only once it is registered as a module: app cannot use docs' filter unregistered and renders with it registered. *Bundled:* registered per render's ref it updates, registered at the target only it silently stays. | `test_extensions.py::TestRegistrationOnTheFamily`; *bundled*: `::TestRegistrationAtCompose`, `::TestRegistrationPerRef` |
| S20 | Does a conflicting user edit pause the update? | Yes: inline markers, no exception, README unmerged with stages 1-3, no `.rej`. The release is core 2.1.0, which moves a recorded Python 3.11 to 3.12 under a user edit of the README line that names it. | `test_update_mechanics.py::TestConflictPauses` |
| S21, *expected failure* | Should each answers file record only its own layer's view, and should `update` be a command? | Not yet: every answers file records the whole merged questionnaire; `update` exits 3, no such command. | `test_cli_baseline.py::TestShippedNew::test_each_answers_file_records_only_its_layers_scoped_view` (target: project's file lacks streamlit's questions), `::test_update_help_exits_zero` (target: `boilerplate update --help` exits 0); the other `TestShippedNew` tests pass |
| S22 *bundled* | Does a three-layer chain scope and update cleanly? | Yes in both orders; the leaf's override reaches every layer that asks the question. No family shape is a chain of three: every layer extends core alone except app, which extends two. | `test_views.py::TestChain`, `::TestChainUpdates` |
| D17 | Which spellings of another template's extension file resolve? | Walk-out relative: locally only. Drive-less absolute: everywhere. Drive-letter absolute (Windows): never, it splits at the drive colon. | `test_extensions.py::TestFilePathSpellings` |
| *added* | Do a layer's own answers beat its ancestors' in the scoped data? | Yes. | `test_update_mechanics.py::test_layers_own_recorded_answer_beats_its_ancestors` |
| *added* | Does the family itself hold? | Every release of every layer is a valid template; the first releases compose into the documented shapes; `license` has an off choice; a project records a tag per layer. | `test_family.py` |
