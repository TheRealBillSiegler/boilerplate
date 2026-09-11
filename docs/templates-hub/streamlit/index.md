# Streamlit template

The Streamlit template creates a data application that reads its own project's `uv.lock` and shows the stack it runs on, with container deployment included.

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
    │   └── services/test_inventory.py
    └── integration/
        └── my_streamlit_app/
            └── test_app.py      # Drives the page with Streamlit's AppTest
```

The package name derives from the project name. The render also inherits the project template's files: `notebooks/`, `src/<package>/module.py`, unit tests, and `.gitignore`. Each layer records its own answers file — `.copier-answers.project.yml` and `.copier-answers.streamlit.yml` — rather than a single shared one.
With `--no-tasks` or `--ci`, the inherited cleanup task never runs either, so `_scripts/post_generation.py` (from the `project` layer) is left behind and isn't gitignored.

## Usage

```bash
# Create new Streamlit app (template name, then destination)
boilerplate new streamlit ./my-data-app
cd my-data-app

# Install dependencies
uv sync

# Run the app locally (package name derives from the project name)
uv run streamlit run src/my_data_app/app.py
```

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
