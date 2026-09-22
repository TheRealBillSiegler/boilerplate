# Project template

The project template provides a complete Python application structure with modern toolchain integration.

## Features

- **Modern toolchain**: uv, Ruff, Pyright, Pytest
- **VS Code integration**: Pinned settings and recommended extensions
- **Type safety**: Full type hint coverage
- **Testing**: Pytest with an example module and matching test
- **Notebooks**: A starter Jupyter notebook

## Project structure

For a project named `my-app` (package `my_app`):

```text
my-app/
├── pyproject.toml          # Metadata + tool config (ruff, pyright, pytest)
├── README.md               # Project documentation
├── .gitignore
├── .gitattributes          # LF line endings on every platform
├── .vscode/                # VS Code settings
│   ├── settings.json
│   └── extensions.json
├── notebooks/
│   └── notebook.ipynb      # Starter notebook
├── src/
│   └── my_app/             # Source code
│       ├── __init__.py     # Package version
│       └── module.py       # Example `add(a, b)` function (sample_module, default on)
├── tests/
│   └── my_app/
│       └── test_module.py  # Tests for the example module (sample_module, default on)
├── uv.lock                 # Pinned deps (written by the post-generation tasks)
└── .copier-answers.project.yml  # Merged answer set, for future updates
```

Post-generation tasks create the virtual environment and `uv.lock` and initialize a git repository (skipped with `--no-tasks`).
With `--no-tasks`, the cleanup step also never runs, so `_scripts/post_generation.py` is left behind in the generated project — it isn't gitignored.

## Usage

```powershell
# Create new project (template name, then destination)
boilerplate new project ./my-app
cd my-app

# Sync dependencies
uv sync

# Run tests
uv run pytest
```

Add dependencies with `uv add <pkg>` (see [Add a dependency](../environment/index.md#1-start-or-clone-a-project)); `pyproject.toml` holds project metadata, entry points and scripts, and the tool configuration described under [Configuration](../environment/index.md#configuration).

## The sample module

`module.py` and its test are a starting point, not scaffolding you must keep. Answer `sample_module` with no to render without them: `boilerplate new project ./my-app --data sample_module=false`. A template that extends `project` can set the default to off in its own `copier.yml`.

## Where next

Need a Streamlit UI on top of this? See the [Streamlit template](streamlit/index.md). Building your own template? Start with [Template authoring](authoring.md). Return to the [Templates Hub](index.md).
