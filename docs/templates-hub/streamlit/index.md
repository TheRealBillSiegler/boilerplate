# Streamlit template

The Streamlit template creates a Streamlit app, built on the [general-purpose template](../project.md). The app reads its own project's `uv.lock` and shows the stack it runs on, with container deployment included.

## Features

- Stack inventory dashboard: locked package count, runtime vs. development vs. transitive dependencies, and the packages the most others depend on — no network, sample data, or fixtures needed at runtime.
- Layered architecture: models validate, services compute, an adapter reads the lock file, and `app.py` only renders.
- A unit test module per layer, plus a Streamlit `AppTest` that drives the rendered page.
- VS Code debugger configuration — press `F5` to run the app under the debugger.
- Container deployment: a Dockerfile and build/push scripts that work with whichever registry you answered at generation time.

## Project structure

```text
my-streamlit-app/
├── pyproject.toml          # Project configuration
├── README.md               # App documentation
├── uv.lock                 # Dependencies
├── Dockerfile              # Multi-stage container definition
├── .dockerignore
├── .copier-answers.project.yml    # The project layer's answers, for future updates
├── .copier-answers.streamlit.yml  # This layer's answers, for future updates
├── boilerplate.lock        # Each layer's version, source and checksum
├── .vscode/
│   ├── settings.json       # Workspace settings (inherited from project)
│   ├── extensions.json     # Recommended extensions (inherited from project)
│   └── launch.json         # Debugger configuration
├── scripts/
│   ├── build-container.sh  # Container build script
│   └── push-container.sh   # Registry push script
├── src/
│   └── my_streamlit_app/
│       ├── __init__.py
│       ├── app.py              # Widgets and layout only
│       ├── adapters/
│       │   ├── __init__.py
│       │   └── lockfile.py     # Reads uv.lock with tomllib, returns validated models
│       ├── models/
│       │   ├── __init__.py
│       │   ├── locked_package.py
│       │   ├── project_info.py
│       │   ├── stack_filter.py
│       │   ├── stack_row.py
│       │   └── stack_summary.py
│       └── services/
│           ├── __init__.py
│           └── inventory.py    # Pure functions: classify, filter, summarize
└── tests/
    ├── my_streamlit_app/
    │   ├── adapters/test_lockfile.py
    │   ├── models/
    │   │   ├── test_locked_package.py
    │   │   └── test_stack_filter.py
    │   ├── services/test_inventory.py
    │   └── test_import.py      # Checks the package imports (from project)
    └── integration/
        └── my_streamlit_app/
            └── test_app.py      # Drives the page with Streamlit's AppTest
```

The package name derives from the project name. The render also inherits the project template's `notebooks/`, `.vscode/`, `.gitignore`, and `tests/<package>/test_import.py`; the base layer's sample module stays off, and the import test renders in its place, because this template answers `sample_module` with no. Each layer records its answers in its own `.copier-answers.<layer>.yml`.

`README.md`, `src/<package>/app.py` and `tests/integration/<package>/test_app.py` are project-owned: the template lists them in `_skip_if_exists`, which [governs what an update does to them](../../design/04-composition-engine.md#per-layer-render-loop).

A project rendered by an earlier 0.1 release of this layer carries the smoke test as `tests_app.py`. On update, a before-stage migration moves it to `test_app.py` with `git mv`, so the update presents the file as a conflict holding both versions instead of deleting yours. This layer declares only its own questions and takes the rest from `project` through the composition, so updating it needs the merged schema that `boilerplate update` will provide ([ADR-007](../../design/adr-007-update-model.md) records that design); a plain `copier update` of a copy of the layer rendered from a git repository exits 0 while skipping every path under the package directory, and [Update a git-backed layer](../plain-copier.md#update-a-git-backed-layer) shows the flags that update it by hand. The copy bundled in the package cannot update with plain Copier at all ([copy-only](../plain-copier.md#bundled-layers-are-copy-only)). Copier requires `--trust` for an update that runs a migration.
With `--no-tasks`, the inherited cleanup task never runs either, so `_scripts/post_generation.py` (from the `project` layer) is left behind and isn't gitignored.

## Usage

```bash
# Create new Streamlit app (template name, then destination)
boilerplate new streamlit ./my-data-app
cd my-data-app

# Run the app locally (package name derives from the project name)
uv run streamlit run src/my_data_app/app.py
```

The inherited post-generation tasks already ran `uv sync`. If you passed `--no-tasks`, run `uv sync` before the first `uv run`.

For container deployment, see [container deployment](deployment/containers/index.md).

## Development

### Architecture

The template follows a layered architecture:

- **Models** (`models/`): Pydantic models that validate the lock file's contents and the UI's widget values.
- **Services** (`services/`): pure functions over the models — no I/O, no Streamlit import.
- **Adapters** (`adapters/`): I/O — reads `uv.lock` and returns validated models.
- **App** (`app.py`): the Streamlit UI — widgets, layout, and calls into services and the adapter.

Condensed from the template's `adapters/lockfile.py`, `models/locked_package.py`, `services/inventory.py`, and `app.py` (imports, docstrings, and the adapter's parsing body trimmed — the rendered files are complete):

```python
# adapters/lockfile.py
def read_lockfile(path: Path) -> tuple[ProjectInfo, tuple[LockedPackage, ...]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    # ... locate the root package, build ProjectInfo and every LockedPackage
    return project, packages

# models/locked_package.py
class LockedPackage(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    version: str
    source_kind: str
    dependencies: tuple[str, ...] = ()

# services/inventory.py
def build_rows(
    project: ProjectInfo, packages: Sequence[LockedPackage]
) -> tuple[StackRow, ...]:
    dependent_counts: dict[str, int] = {}
    for package in packages:
        for dependency in package.dependencies:
            dependent_counts[dependency] = dependent_counts.get(dependency, 0) + 1

    rows = [
        StackRow(
            name=package.name,
            version=package.version,
            scope=_scope_of(package.name, project),
            source_kind=package.source_kind,
            dependents=dependent_counts.get(package.name, 0),
        )
        for package in packages
        if package.name != project.name
    ]
    return tuple(sorted(rows, key=lambda row: row.name))

# app.py
project, packages = read_lockfile(LOCKFILE)
rows = build_rows(project, packages)
stack_filter = StackFilter.model_validate({"search": search, "scope": scope, "limit": limit})
st.dataframe([row.model_dump() for row in apply_filter(rows, stack_filter)], hide_index=True)
```

### Debugging

Press `F5` in VS Code to launch the Streamlit app with the debugger attached. The `.vscode/launch.json` is pre-configured.

## Tests

- `test_locked_package.py`: PEP 503 name normalization.
- `test_stack_filter.py`: widget-value validation — search pattern, scope, and limit bounds.
- `test_lockfile.py`: parses a lock file into `ProjectInfo` and `LockedPackage`; raises on a missing root package or a missing file.
- `test_inventory.py`: classification into runtime, dev, and transitive; dependent counts; filtering; summarizing.
- `test_app.py` (integration): drives the rendered page with Streamlit's `AppTest` — runs without exception, shows the correct locked-package count, and warns on invalid filter input.

## Where next

Need container deployment details? See [container deployment](deployment/containers/index.md). Building your own template? Start with [Template authoring](../authoring.md). Return to the [Templates Hub](../index.md).
