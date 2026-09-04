# VS Code configuration

Boilerplate projects ship a `.vscode/` folder so the editor is ready the moment you open the project — linting, formatting, type hints, and test discovery all work with no manual setup.

```text
.vscode/
├─ extensions.json
└─ settings.json
```

New to VS Code? After generating or cloning a project, you only need to do one thing: open the folder and accept the prompt to install the recommended extensions.

## Recommended extensions

When you open a generated project, VS Code reads `.vscode/extensions.json` and offers to install these. That file is the authoritative list; this page explains what each one is for:

- **Python** (`ms-python.python`) — the core Python experience: run and debug code, pick the interpreter, and **Pylance**, which provides IntelliSense, go-to-definition, and live type checking as you type.
- **Jupyter** (`ms-toolsai.jupyter`) — open and run `.ipynb` notebooks inside VS Code.
- **Ruff** (`charliermarsh.ruff`) — linting and formatting, wired in as the default formatter for Python and notebooks.
- **Even Better TOML** (`tamasfe.even-better-toml`) — syntax highlighting and validation for `pyproject.toml` and other TOML files.
- **Prettier** (`esbenp.prettier-vscode`) — formatting for non-Python files (JSON, Markdown, YAML).

## Workspace settings

`.vscode/settings.json` connects the editor to the project's tools:

- **Ruff** is the default formatter for Python *and* notebooks, with **format-on-save** enabled.
- **pytest** discovery is on, so tests appear in the Testing sidebar.
- **Pylance** runs in workspace mode with auto-import suggestions, and honors the `[tool.pyright]` settings in `pyproject.toml` (strict over `src/`) — so the type errors you see inline match what the configured checks enforce.
- **Debugging** — set a breakpoint and press `F5` to launch the debugger with the workspace interpreter.

The interpreter path isn't set in `settings.json` — the Python extension auto-detects `.venv` in the workspace root, and that works the same on Windows, macOS, and Linux.

## Troubleshooting: the interpreter isn't detected

Most common right after generating or cloning a project, before the virtual environment exists:

1. Run `uv sync` to create `.venv`.
2. Open the Command Palette (`Ctrl+Shift+P`) → **Python: Select Interpreter**.
3. Choose the `.venv` interpreter in your project folder.

If an extension doesn't activate, reload the window: Command Palette → **Developer: Reload Window**.

## Where next

Other symptoms (lint errors, template rendering errors)? See [Troubleshooting](../troubleshooting.md). Back to the [Development Environment overview](index.md).
