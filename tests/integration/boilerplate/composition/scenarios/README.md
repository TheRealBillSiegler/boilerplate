# Composition scenarios

Reproducible evidence for the composition design: each test re-runs one scenario against real Copier and git and asserts what was observed. These are not product tests. They live under `tests/integration/`, so `uv run pytest` collects them, and a collection hook marks each one `scenario`. Deselect them with `-m "not scenario"`; the CI test job and the local gate do, and run them separately only when a composition path changed ([CI pipeline](../../../../../docs/governance/ci.md#composition-scenarios)). A full run takes about five minutes on a developer laptop with xdist.

Most scenarios run on a made-up family of six Python-project templates (`core`, `service`, `docs`, `ci`, `app`, and `handbook`, which only the add scenarios use) kept as data in `tests/fixtures/family/`. A few stay on the bundled `project` and `streamlit` layers, because the family cannot express what they claim; the table says which.

Two scenarios assert target behavior the code does not yet have. They are strict expected failures (`xfail`): they pass the run while the gap exists and fail it once the gap closes, at which point remove the marker.

A failure means a claim no longer holds (Copier, Git or the templates changed). Revisit the design that rests on it, starting with [design 04 §Safe Update](../../../../../docs/design/04-composition-engine.md#safe-update), before changing the expected value.

## Run

```console
uv run pytest tests/integration/boilerplate/composition -m scenario                         # every scenario
uv run pytest tests/integration/boilerplate/composition/scenarios/test_views.py -m scenario # one group
uv run pytest tests/integration/boilerplate/composition -m scenario -k TestRenamedQuestion  # one scenario, by its test class
```

Every scenario builds its template repositories and project under pytest's temp directory and points `TMP`, `TEMP` and `TMPDIR` there, so Copier's clones and update copies stay inside it; git checks out with LF endings there, whatever `core.autocrlf` says. The scoped-view harness lives in `tests/boilerplate/templates/conftest.py`, over the view builder, the render engine and the update pieces in `src/boilerplate/composition/views/`, `rendering/` and `updating/`; `builders.py` holds the project builders and readers, `family.py` (one folder up) builds the family, and `extensions/` holds the bundled-layer scenarios' probe-only Jinja extensions.

## How the harness works

The harness drives Boilerplate's real engine pieces, the compose loop with its questionnaire pass and each layer's update step, and Copier directly. Five views of it follow.

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
│   compose_project · ask_merged_questionnaire ·              │
│   update_layer · step_view · layer_view (thin wrappers      │
│   that resolve, compose, read answers files and call src)   │
├──────────────────────────────┬──────────────────────────────┤
│ Boilerplate engine      real │ Copier 9.18.1           real │
│   catalog · Resolver ·       │   Worker.run_copy ·          │
│   Composer · MergedTemplate  │   Worker.run_update · git    │
│   composition/views:         │                              │
│     build_layer_view ·       │                              │
│     build_step_view          │                              │
│   composition/rendering:     │                              │
│     RenderEngine ·           │                              │
│     ScopedWorker             │                              │
│   composition/updating:      │                              │
│     build_step_data ·        │                              │
│     update_layer             │                              │
├──────────────────────────────┴──────────────────────────────┤
│ Fixtures                                          test code │
│   family fixture → family.py →                              │
│   tests/fixtures/family/<layer>/<version>/                  │
└─────────────────────────────────────────────────────────────┘
```

Views come from Boilerplate's real resolver, composer and view builder, compose renders through its real `RenderEngine`, and update renders through its real `ScopedWorker` over Copier's Worker.

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
│
├─ compose_project("app", dest, answers, templates)
│    ├─ compose("app")                catalog → Resolver → Composer     real
│    │    order: core, service, docs, app
│    ├─ ask_merged_questionnaire      one pass over the full merged view   test
│    └─ for each layer, in that order:
│         layer_view(layer)           compose rooted at this layer:        real
│                                     its own and its ancestors' questions,
│                                     and the ancestors' file-path extension
│                                     files at their releases
│         MergedTemplate(view)                                             real
│         the view's ancestor files registered as modules                  real
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
                    before={…, "service": "1.0.0"}, after={…, "service": "1.1.0"},
                    work=work, step_views=True)
│
├─ templates_at for the before and after tags
└─ update_layer(project, root="app", layer="service", source=repos/service,   test
                ref="1.1.0", templates={"1.1.0": dir}, old_templates=dir)
   │
   ├─ old view    = build_step_view(compose("service", before dir),          real
   ├─ target view   compose("app", …)) at the before / after dir
   │    the questions of service's scope under the definitions of the full
   │    merged schema, so a descendant's override sets the default of a new
   │    ancestor question; two views, not one per ref: when only an ancestor
   │    moves, the layer's own ref is the same in every render
   │
   └─ composition.updating.update_layer(project, release, views, inputs)     real
      ├─ build_step_data, from the answers files as the step starts         real
      │    the data is only what the layer does not own:
      │      for each question an ancestor declares, the answer in that
      │        ancestor's file (core's), never service's own copy
      │      + the secrets asked earlier in this update
      │      + the values the user supplies (data=, the future --set)
      └─ ScopedWorker(vcs_ref="1.1.0", data, old_view, target_view,         real, over copier
                      defaults = not interactive, skip_answered)
         .run_update()
        Copier rebuilds the worker for each render; every rebuilt worker
        picks its view from its destination: the old copy's temp directory
        takes the old view, the project and the new copy's the target view.

        1  old copy   at _commit 1.0.0  old view     answers file only; data never reaches it
        2  the target release's before-migrations run; Copier re-reads the answers file
        3  in place   at 1.1.0          target view  data over the answers file
             before Copier asks, the layer's own recorded answers are checked
             against the target view's questions (type, choices, validator):
             a rejected one raises RecordedAnswerRejectedError, or with prompting
             is logged and asked again; an answer the data replaces is not checked
             Copier then asks the layer's own questions: defaults, or prompts
             with the recorded answer as the default
        4  new copy   at 1.1.0          target view  same answers, in an empty folder
        5  the user's changes (old copy → project) are applied to the in-place
           render with git apply --reject; a rejected file is merged again with
           git merge-file, which leaves conflict markers and still exits 0
        6  after-migrations run

        the step returns the secret answers it asked, for the walk to carry on
```

The step order is Copier's `_apply_update` in `copier/_main.py`. Because each render builds its own view, the old copy renders the questionnaire of the release it reconstructs, and data reaches only the in-place render and the new copy.

```text
pytest session
│
├─ tests/fixtures/conftest.py
│    collect_ignore_glob = ["family/*"]   keeps the template data out of collection
│
├─ tests/integration/boilerplate/composition/conftest.py
│    family             session scope, tmp_path_factory: built once per xdist worker
│    isolated_temp      autouse, only for scenarios/ and updating/: TMP, TEMP and
│                       TMPDIR → the test's tmp_path, so Copier's clones and old/new
│                       copies stay inside it; the rendering tests keep the real one
│
└─ tests/integration/boilerplate/composition/scenarios/conftest.py
     collection hook   marks every test in the folder `scenario`
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
| S10b | Does one pass over the full view at the target fix it? | Yes: Apache-2.0 in `LICENSE` and both answers files, either order. The step runs no such pass; the test supplies the pass's answers as data, a control for S25. | same test `[S10b-*]`, `::test_questionnaire_pass_answers_the_new_question_with_the_override` |
| S10c *bundled* | Does the full view see the override? | Yes: Apache-2.0 everywhere. The project is composed under the full view (`render_full_view`, the pre-scoped render kept as a counterfactual), which registers no ancestor's file-path extension, so the family's app still cannot be composed that way (`No filter named 'docs_anchor'`). Updating app under the full view works, since the views `ScopedWorker` renders under register them. | `test_question_changes.py::TestAddedQuestionUnderTheFullView` |
| S11 | Does a diamond scope each layer to its transitive ancestors and update cleanly? | Yes, in the scoped view: each view adds its ancestry's questions, app renders through docs' filter, docs then app update with the user line kept and only they move. *Bundled:* the same in the full view, docs' importable filter reaches only views that descend from docs, and an edit beside a changed line conflicts in both views. | `test_views.py::TestDiamond`, `::TestDiamondUpdates`; *bundled*: `::TestBundledDiamond`, `::TestBundledDiamondUpdates` |
| S12 | Does removing a question break the old copy? | No: the old copy renders the recorded `use_tests: false` (no smoke test); the answers file drops the key; service, not yet updated, keeps it. | `test_question_changes.py::TestRemovedQuestion` |
| S12 control | Does forced data reach the old copy? | No: it renders from the answers file, also with `data={}`. | `../rendering/test_scoped_worker_integration.py::TestEachCopyRendersItsOwnRelease`; *added*: `::test_forced_data_never_reaches_the_old_copy` |
| S13 | What happens to a recorded answer the new type or choices reject? | Forced as data: raw `ValueError` before any render, for the declaring layer and a descendant. Through the step: a non-interactive step raises `RecordedAnswerRejectedError` first (S28). Castable: carried as the new type. Vanilla: silently replaced by the default. The project stays untouched unless the release ships a migration, which runs first: core 2.1.0 rewrites the recorded Python version before the forced one is rejected. | `test_question_changes.py::TestRetypedQuestion`; *bundled*: `::TestNarrowedChoiceOnTheBundledLayers` (the narrowed choice with no migration) |
| S14 | Does a renamed question's value survive behind a migration? | Lock order: yes. Reverse order, with only core shipping the migration: service records the default. | `test_question_changes.py::TestRenamedQuestion` |
| S14 *added* | Does the update step keep a renamed question's migrated answer? | Yes, ancestors first: with no questionnaire pass, both layers record and render the migrated answer. | `test_question_changes.py::TestRenamedQuestion::test_ancestors_first_update_step_keeps_the_migrated_answer` |
| S15 | What does a validator the recorded answer fails do? | Forced: `ValueError` before render, for docs and app. Vanilla: silently swaps in the new default when it is valid. | `test_question_changes.py::TestTightenedValidator` |
| S16 | Where do tasks run? | Compose: once, in the destination, although five layers render. Update: the layer's own task in the old copy, in place and in the new copy; a layer with no task runs none. *Bundled:* the in-place output is undone by the merge when two layers append to one marker; on the family the appended line survives. | `test_update_mechanics.py::TestTasks`; *bundled*: `::test_in_place_task_output_is_undone_by_the_merge` |
| S17 | Can the unified questionnaire run interactively in-process? | Yes via prompt_toolkit pipe input; prompts show service's and app's overrides; `project_name` defaults to the scratch directory's name. | `test_prompting.py::TestInteractivePrompting` |
| S18, *expected failure* | Should Boilerplate compose from git-repository layers? | Not yet: `git_index_modes`' path keys fail the composer's JSON check, also via `new`; without that attribute it works and records each layer's latest tag. | `test_sources.py::TestComposeFromGitSources::test_compose_succeeds_from_git_repository_layers`, `::test_new_exits_zero_from_git_repository_layers` (target: composing and `new` succeed); the counterfactual `::test_without_git_index_modes_both_composes_record_the_latest_tag` passes |
| S19 | Can a descendant use an ancestor's file-path extension? | Only once it is registered as a module: app cannot use docs' filter unregistered and renders with it registered. The view records the file at its release under a name unique to it, and each render registers its own view's files: with docs moving 1.0.0 to 1.2.0 while app's ref stays put, app's old copy renders docs 1.0.0's filter and the in-place and new renders 1.2.0's, so the change lands with the user's edit kept and no conflict. A worker keying its views by ref gives all three the target's filter and silently keeps the old output. | `test_extensions.py::TestRegistrationOnTheFamily`, `::TestRegistrationPerRelease`, `::TestViewKeyedByRefDefect`; *bundled*: `::TestRegistrationAtCompose` |
| S20 | Does a conflicting user edit pause the update? | Yes: inline markers, no exception, README unmerged with stages 1-3, no `.rej`. The release is core 2.1.0, which moves a recorded Python 3.11 to 3.12 under a user edit of the README line that names it. | `test_update_mechanics.py::TestConflictPauses` |
| S21, *expected failure* | Does each answers file record only its own layer's view, and is update a command? | Each answers file records only its layer's and its ancestors' questions, and boilerplate.lock is written; update exits 3, no such command. | `test_cli_baseline.py::TestShippedNew::test_each_answers_file_records_only_its_layers_scoped_view` passes; `::test_update_help_exits_zero` (target: exits 0) is the only expected failure |
| S22 *bundled* | Does a three-layer chain scope and update cleanly? | Yes in both orders; the leaf's override reaches every layer that asks the question. No family shape is a chain of three: every layer extends core alone except app, which extends two. | `test_views.py::TestChain`, `::TestChainUpdates` |
| D17 | Which spellings of another template's extension file resolve? | Walk-out relative: locally only. Drive-less absolute: everywhere. Drive-letter absolute (Windows): never, it splits at the drive colon. | `test_extensions.py::TestFilePathSpellings` |
| S23 *added* | Does a migration that changes a value reach a descendant whose copy is stale? | Yes: core 2.1.0 rewrites a recorded Python 3.11 to 3.12, then service's step takes core's 3.12; both files record it and the Dockerfile renders it. Forcing service's own stale 3.11 on top is rejected. | `test_update_steps.py::TestValueChangingMigrationWithAStaleDescendant` |
| S24 *added* | Does a renamed answer survive in the descendant's file? | Yes, ancestors first, non-interactive: both answers files record `maintainer_name` and service 1.2.0's guide renders it. | `test_update_steps.py::TestRenamedAnswer` |
| S25 *added* | Does a descendant's override of a new ancestor question land in the ancestor's step? | Yes: core 1.1.0 adds `license`, app 1.1.0 overrides its default, and core's non-interactive step records and renders Apache-2.0. | `test_update_steps.py::TestDescendantOverrideOfANewAncestorQuestion` |
| S26 *added* | Does each layer's step prompt for its own questions? | Yes: core's step re-asks them with the recorded or migrated answer as the default; `skip_answered` asks what no file records (the never-recorded secret too); service's step does not ask core's. | `test_update_steps.py::TestInteractivePrompting`; `::TestSecretAskedOnce::test_service_step_does_not_ask_the_secret_or_cores_questions_again` |
| S27 *added* | Is a secret asked once per update? | Yes: answered in core's step, it reaches service's as data and stays out of every answers file; without the carry, service's step asks it again. | `test_update_steps.py::TestSecretAskedOnce` |
| S28 *added* | What does a step do with a recorded answer the target rejects? | A non-interactive step raises `RecordedAnswerRejectedError` naming docs, `docs_site_name` and the empty value; a supplied value replaces it; an interactive step logs why and the prompt takes a valid one; a recorded `"8000"` under service 1.1.0's `int` passes. | `test_update_steps.py::TestRejectedRecordedAnswer` |
| S29 *added* | What does a plain `copier update` of one git-backed layer cost? | Two limits. The answers file is rewritten to the layer's own questions (service keeps `port` and `python_version`; core's `project_name`, `author_name` and `use_tests` go). Copier renders the old copy from that file alone, so a release that edits a line rendering a computed value no file records (`package_name`) conflicts: one inline block, no other file touched. Adding the value to the answers file first, and committing, makes the update clean; `--data` cannot, because it never reaches the old copy (S12 control). | `test_hand_run_update.py::TestAHandRunUpdateOfAGitBackedLayer` |
| *added* | Does the rejected-answer check see a question the target release adds? | Yes: ci 1.2.0 adds `ci_hosted` (default true), gates `ci_provider` on it and narrows its choices to github, so a recorded gitlab is rejected; the check fills each earlier question's answer before it evaluates the next `when`, as Copier does. A `when` that cannot render (ci 1.3.0) ends the check: Copier reports the template error, not a rejection of the recorded gitlab. | `test_update_steps.py::TestRejectedAnswerBehindAWhen` |
| *added* | Does the walk heal an answers file a plain `copier update` trimmed? | Yes: a hand-run of service from 1.0.0 to 1.1.0 keeps only service's own keys; the pre-walk check passes on core's file; service's old copy renders core's recorded `project_name`, not the old copy's temp-directory name; the in-place render records core's keys again; a rename supplied to the walk reaches service's guide, because the fill reads core's file before core's step runs. | `test_update_steps.py::TestATrimmedAnswersFileHeals` |
| *added* | Does a declaring ancestor's answer beat the layer's stale copy in a step's data? | Yes; the layer's own answer on top loses. The pure rule is tested in `tests/boilerplate/composition/updating/test_update_data.py`. | `../updating/test_update_data_integration.py::test_declaring_ancestors_answer_beats_the_layers_stale_copy` |
| *added* | Does a project that grows by adds behave like one composed at once? | Yes: docs, then ci, join a core and service project; each answers file records the layer's own and its ancestors' answers at the release it joined, the lock lists the layers in join order, the log holds one record per add, and only the chosen alternative renders. The following update walks every layer in lock order, including the question core adds. Switching a layer's choice swaps its alternatives file (an edited one is deleted uncommitted, the edit surviving in git history); a file the layer lists in `_skip_if_exists` keeps the project's content while an unlisted one another layer rendered is overwritten. Five refusals (unmanaged project, dirty tree, layer present, ancestor missing, ancestor too old) come before any staging folder exists; a rejected answer changes nothing; an interactive add asks only what no answers file records. | `test_add_layer.py::TestAddingLater`, `::TestUpdateAfterAdds`, `::TestSwitchingTheChoice`, `::TestSwitchingAnEditedFile`, `::TestProjectOwnedFile`, `::TestRefusalsComeBeforeStaging`, `::TestPrompting`, `::TestAnErrorMidAdd` |
| *added* | What does a run cut off after its copy back leave, and what does the next run do? | A marker naming every target and no log record. The next `update` or `add` stops naming the run to rerun, or stops when HEAD moved; a committed or set-aside partial update meets the drift rules. The same update again finishes a run cut off in its tasks (tasks run, lock written, marker removed), repeats a copy back cut off before every file, stops on a file edited since, and runs no tasks for a run cut off as it recorded. A paused run whose conflict record a crash took appends it on rerun and ends with the pause. An add cut off in its tasks leaves no marker, and the rerun stops because the lock lists the layer. An add cut off at the lock write leaves a marker at the recording phase; the rerun writes the lock and the record, runs the layer's tasks, repeats a copy back cut off before every file, and an `update` in between stops naming the add. | `test_interrupted_run.py::TestInterruptedUpdate`, `::TestInterruptedAdd`, `::TestFinishingACutOffUpdate`, `::TestFinishingACutOffPause`, `::TestFinishingACutOffAdd` |
| *added* | Does the prompt harness end a run at once when a typed answer is rejected? | Yes: docs 1.1.0 rejects an empty `docs_site_name`, and the run ends with an error caused by end of input instead of waiting for a retyped answer. The claim is the cause, since which exception wraps it depends on the path. | `test_prompt_session.py::TestRejectedTypedAnswer` |
| *added* | Is a recorded `_commit` read as a version the way Copier reads it? | A bare release tag reads as that release, also for the commit Copier records at a tag. A `git describe` string past a tag, plain or `v`-prefixed, reads as a post-release of it, between that release and the next. A directory that is not a git repository has no version; a ref the repository lacks raises instead of reading as none. | `test_recorded_versions.py::TestARecordedTag`, `::TestACommitPastATag`, `::TestACommitThatIsNotAVersion` |
| *added* | Do the pre-walk version rules hold on real tags and a real lock? | A paused walk resumes from its record: the answers files show what it did, a layer whose own version did not move is still skipped, a release published after the pause does not move the targets, a remaining layer's old copy uses the lock's ancestor versions, an explicit target that differs is refused, and the record stops binding once the partial update is set aside. Without a binding record, a retarget after a pause and hand-runs of a layer and its ancestor stop, while a hand-run of one layer warns and proceeds. A target older than a recorded tag is refused before any layer runs. A trimmed answers file passes on the ancestor's record; a key no layer records stops naming each layer that lacks it. | `test_update_versions.py::TestAPausedWalkResumesFromItsRecord`, `::TestAmbiguousDriftStops`, `::TestDowngradesStopBeforeAnyLayerRuns`, `::TestATrimmedAnswersFile` |
| *added* | Does `Updater` walk the diamond to newer releases and bring the result back? | Yes: every answers file and the lock end at their targets, the user's edit survives with the template change merged in, one success record is appended, and the result is uncommitted changes on the checkout's own commit. A layer already at its target still runs so a supplied answer lands; the project's hooks never run; a secret is prompted once across the walk. Downgrades, drift and a dirty tree stop before any staging folder. A rejected answer in a later layer undoes the whole walk byte for byte. A conflict pauses at its layer with the remediation, the finished layers brought back and no lock, and the rerun finishes to the recorded targets. Composition tasks run once after the walk, in the checkout, and `no_tasks` skips them; a failing task under keep leaves the files, the lock and a failed record, and under undo returns the checkout as it was. A layer recorded past its tag (a `git describe` string) updates end to end and is locked. | `test_update_walk.py::TestDiamondWalkToNewerReleases`, `::TestSuppliedAnswer`, `::TestHooksNeverRun`, `::TestSecretAskedOnce`, `::TestStopsBeforeAnyStaging`, `::TestAnErrorMidWalk`, `::TestACommitPastATag`, `::TestConflictPause`, `::TestResumeAfterAConflict`, `::TestTasksAfterTheWalk`, `::TestNoTasks`, `::TestAFailingTaskUnderKeep`, `::TestAFailingTaskUnderUndo` |
| *added* | Does the family itself hold? | Every release of every layer is a valid template; the first releases compose into the documented shapes; `license` has an off choice; a project records a tag per layer. | `test_family.py` |
| *added* | Do a scenario's temp-directory lookups resolve under its `tmp_path`? | Yes: under the real autouse `isolated_temp` fixture, `TMP`, `TEMP`, `TMPDIR` and `tempfile.gettempdir` each resolve there, so Copier's clones and update copies stay inside the test's directory. | `test_temp_isolation_scenarios.py` |
