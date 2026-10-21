# Compose and update with plain Copier

A Boilerplate project is plain Copier output: one `.copier-answers.<layer>.yml` per layer, each written by Copier. You can compose a project and update its layers with `copier` alone. This page shows the commands, what they leave out, and which layers can update.

## Run Copier where Boilerplate is importable

The `project` template loads extensions from the `boilerplate` package and from `copier-template-extensions`, and Copier runs template code only with `--trust`. Run `copier` from a checkout of the repository, which has both:

```bash
BP=/path/to/boilerplate    # your checkout
uv run --project "$BP" copier --version
```

The compose commands below use `uv run --project "$BP" copier` and run from the folder that holds your project, so `--project` leaves the working directory alone; the update command runs from the project root.

## Compose `streamlit` over `project`

Two `copier copy` runs build what `boilerplate new streamlit` builds. Run `project` first, with the two defaults `streamlit` overrides:

```bash
uv run --project "$BP" copier copy --trust --defaults \
  --data project_name="Probe App" \
  --data description="A probe." \
  --data author_name="Ada Probe" \
  --data author_email=ada@example.com \
  --data 'dependencies=["streamlit","pydantic>=2"]' \
  --data sample_module=false \
  "$BP/src/boilerplate/templates/project" probe-app
```

Then remove the project's `README.md` and run `streamlit` over it, reading `project`'s answers and supplying the two values it never records:

```bash
rm probe-app/README.md
uv run --project "$BP" copier copy --trust --defaults --overwrite \
  --data-file probe-app/.copier-answers.project.yml \
  --data project_slug=probe-app \
  --data package_name=probe_app \
  "$BP/src/boilerplate/templates/streamlit" probe-app
```

| Step                                             | Why                                                                                                                                                                                                             |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dependencies`, `sample_module` on the first run | `streamlit` overrides both defaults, and `project` renders `pyproject.toml` and the sample module from them.                                                                                                    |
| `rm probe-app/README.md`                         | `streamlit` lists `README.md` in `_skip_if_exists`. Copier honors that list over `--overwrite`; `boilerplate new` ignores it.                                                                                   |
| `project_slug`, `package_name`                   | `project` computes both from `project_name` (`probe-app`, `probe_app`) and never records them. Without `package_name`, Copier silently skips every file in a `<package_name>` folder under `src/` and `tests/`. |

`project`'s post-generation tasks run in the first command, before `streamlit`'s files exist. Add `--skip-tasks` there to run them yourself afterwards.

### What differs from `boilerplate new`

The rendered files are identical. Two things differ:

| File                            | By hand                                                                                          | `boilerplate new`                   |
| ------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------- |
| `boilerplate.lock`              | Not written.                                                                                     | Written.                            |
| `.copier-answers.streamlit.yml` | Records only `streamlit`'s own questions: `container_registry`, `dependencies`, `sample_module`. | Also records `project`'s questions. |

## Update a git-backed layer

A layer updates with `copier update` when its answers file records a `_commit`, which means its template came from a git repository. From the project root, with the working tree committed (Copier refuses a dirty tree):

```bash
uv run --project "$BP" copier update --trust --defaults \
  --answers-file .copier-answers.streamlit.yml \
  --data-file .copier-answers.project.yml \
  --data project_slug=probe-app \
  --data package_name=probe_app \
  --vcs-ref <tag>
```

Copier accepts `--data-file` once: a second flag stops with `Switch --data-file already given`. Pass the answers file of the layer's direct parent (`project`'s file, since `streamlit` extends `project`). A base layer such as `project` needs none.

- A parent's file that `boilerplate new` wrote also records the parent's own ancestors' answers.
- A file from a by-hand `copier copy`, or one an earlier by-hand update trimmed, holds only that parent's own questions. Supply the rest with `--data key=value`, which wins over the same key in the file.

Pass the two derived names too, as in the compose step: no answers file records them. Without `package_name`, Copier exits 0 and silently skips every file in a `<package_name>` folder under `src/` and `tests/`. Use the names your project has.

Omit `--vcs-ref` to take the latest tag. Update one layer at a time, lower layers first: the `layers` list in `boilerplate.lock` is the order, and without a lock you read the templates' `extends` chains. `_src_path` in each answers file must be an absolute path or URL.

Two limits come with updating one layer by hand:

- **The answers file shrinks.** After the update, the layer's file holds only the questions its own `copier.yml` declares, so answers inherited from a parent drop out of it. The `--data-file` supplies them from then on, so pass it on every update: without it, the next update renders the inherited answers empty.
- **A changed line that renders an unrecorded value conflicts.** Copier renders the old copy from the answers file alone, so a value the file lacks, such as the computed `package_name`, renders empty there and your rendered value reads as your edit. A release that changes that line produces an inline conflict (`<<<<<<<`) in that file and nowhere else. `--data` and `--data-file` do not help, because neither reaches the old copy. Resolve the conflict in the file and commit.

## Bundled layers are copy-only

`boilerplate new` renders `project` and `streamlit` from the template folders inside the installed package. Those folders are not git repository roots, so Copier records no `_commit` in `.copier-answers.project.yml` or `.copier-answers.streamlit.yml`, and `copier update` stops with "cannot obtain old template references". This holds for the by-hand compose above too, which uses the same folders. A layer you render from a git repository updates; to refresh a bundled layer, run its `copier copy` command again.

Back to [Template composition](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/composition/index.md) · Next: [Versioning and migration](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/versioning/index.md)
