# Project template

The project template creates a general-purpose Python project, with its tools configured.

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
│       ├── test_module.py  # Tests for the example module (sample_module, default on)
│       └── test_import.py  # Checks the package imports (sample_module off)
├── uv.lock                 # Pinned deps (written by the post-generation tasks)
├── .copier-answers.project.yml  # This layer's answers, for future updates
└── boilerplate.lock        # Each layer's version, source and checksum
```

`README.md` and `src/<package>/__init__.py` are project-owned: the template lists them in `_skip_if_exists`, which [governs what an update does to them](https://therealbillsiegler.github.io/boilerplate/0.4/design/04-composition-engine/#per-layer-render-loop).

Post-generation tasks create the virtual environment and `uv.lock` and initialize a git repository (skipped with `--no-tasks`). With `--no-tasks`, the cleanup step also never runs, so `_scripts/post_generation.py` is left behind in the generated project — it isn't gitignored.

## Usage

```powershell
# Create new project (template name, then destination)
boilerplate new project ./my-app
cd my-app

# Run tests
uv run pytest
```

The post-generation tasks already ran `uv sync`, so the environment is ready. If you passed `--no-tasks`, run `uv sync` before the first `uv run`.

Add dependencies with `uv add <pkg>` (see [Add a dependency](https://therealbillsiegler.github.io/boilerplate/0.4/environment/#1-start-or-clone-a-project)); `pyproject.toml` holds project metadata, entry points and scripts, and the tool configuration described under [Configuration](https://therealbillsiegler.github.io/boilerplate/0.4/environment/#configuration).

## The sample module

`module.py` and its test are a starting point, not scaffolding you must keep. Answer `sample_module` with no to render without them: `boilerplate new project ./my-app --data sample_module=false`. `tests/<package>/test_import.py` renders in their place, so `uv run pytest` still has a test to run. A template that extends `project` can set the default to off in its own `copier.yml`.

## Choose a build backend

The build backend turns the project into a wheel and an sdist. The `build_backend` question sets the `[build-system]` table in `pyproject.toml`: `uv_build` by default, `hatchling` when you answer it that way: `boilerplate new project ./my-app --data build_backend=hatchling`.

| Pick                 | Choose it when                                                                                  | Renders                                                                         |
| -------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `uv_build` (default) | The code is pure Python with a static version and one `src/<package>`, and uv is your toolchain | `requires = ["uv_build>=0.13,<0.14"]` and nothing else                          |
| `hatchling`          | You need build hooks, plugins, a version from git tags (`hatch-vcs`), or a custom file layout   | `requires = ["hatchling>=1.27"]` and a `[tool.hatch.build.targets.wheel]` table |

The `uv_build` range names the current uv minor, and the [Streamlit template](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/streamlit/index.md)'s Dockerfile installs the same minor, so uv runs its bundled backend and fetches nothing from a package index. A newer uv still builds, with a warning on each `uv sync` until you raise the cap. An older uv fetches `uv-build` from your default index, so a private `package_index_url` must mirror it.

`uv_build` builds from static metadata and ships a git-ignored file that sits inside the package directory. If you need a dynamic version or generated files in the package tree, pick `hatchling`.

Compiled code (Rust through maturin, C or C++ through scikit-build-core) is a hand edit: replace the `[build-system]` table, then follow uv's [extension module guide](https://docs.astral.sh/uv/concepts/projects/init/#projects-with-extension-modules). The template scaffolds no `Cargo.toml` or `CMakeLists.txt`. [ADR-017](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-017-build-backend/index.md) compares nine backends and holds the reasoning behind these two.

## Where next

Need a Streamlit UI on top of this? See the [Streamlit template](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/streamlit/index.md). Building your own template? Start with [Template authoring](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/authoring/index.md). Return to the [Templates Hub](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/index.md).
