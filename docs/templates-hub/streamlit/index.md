# Streamlit template

The Streamlit template creates data applications and interactive dashboards, with container deployment to Azure Container Registry included.

## Features

- **Modern Streamlit**: Latest version with Pydantic models
- **Container ready**: Multi-stage Dockerfile with security best practices
- **Development tools**: VS Code debugger configuration, hot reload
- **Service architecture**: Separation of models, services, and UI logic
- **Testing**: Integration test scaffolding included

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
│       ├── app.py          # Main Streamlit app
│       ├── models/         # Pydantic models
│       │   ├── __init__.py
│       │   └── greeter.py  # Example model
│       └── services/       # Business logic
│           ├── __init__.py
│           └── greeter.py  # Example service
└── tests/
    └── integration/        # Integration tests
        └── my_streamlit_app/
            └── test_app.py
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

For container deployment, see [building and pushing to ACR](deployment/containers/index.md).

## Development

### Architecture

The template follows a service-oriented architecture:

- **Models** (`models/`): Pydantic models for data validation
- **Services** (`services/`): Business logic separated from UI
- **App** (`app.py`): Streamlit UI layer

Condensed from the template's `models/greeter.py`, `services/greeter.py`, and `app.py` (imports and docstrings trimmed — the rendered files are complete):

```python
# models/greeter.py
from pydantic import BaseModel

class GreeterInput(BaseModel):
    """Input model for the greeting service."""
    name: str

# services/greeter.py
class GreeterService:
    """Business logic for generating greeting messages."""

    def greet(self, data: GreeterInput) -> str:
        """Generate a personalized greeting."""
        name = data.name.strip()
        return f"Welcome, {name}!" if name else "Welcome!"

# app.py
name = st.text_input("Your name:")
if name:
    service = GreeterService()
    greeting = service.greet(GreeterInput(name=name))
    st.success(greeting)
```

### Debugging

Press `F5` in VS Code to launch the Streamlit app with the debugger attached. The `.vscode/launch.json` is pre-configured.

## Best practices

- Use session state for data persistence
- Cache expensive operations with `@st.cache_data`
- Test your app with different data scenarios

## Where next

Need container deployment details? See [building and pushing to ACR](deployment/containers/index.md). Building your own template? Start with [Template authoring](../authoring.md). Return to the [Templates Hub](../index.md).
