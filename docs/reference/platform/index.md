<!-- markdownlint-disable MD046 -->
<!-- MD046 false positives: mkdocs-material admonitions and content tabs require indented blocks -->

# Developer platform architecture

This page is the reference model behind Boilerplate: a tool landscape feeding a curated stack, a golden path, starter templates, and guardrails. Each element has a single responsibility, from cataloging available tools to enforcing standards automatically.

In platform-engineering terms, an internal developer platform (IDP) is the self-service layer an organization runs for its own developers — templates plus CI/CD, provisioning, deployment, and operations, usually behind a portal. Boilerplate is open-source tooling for the scaffolding-and-environment slice of that: the curated stack, starter templates, and dev-time guardrails, with the golden path pre-built — where most platform tools hand you the machinery and leave the path to you. Deployment and operations are out of scope.

!!! note "Scope"
    The reference implementation documented here is Boilerplate's own: Python-focused, with one curated stack. It is one worked example, not a general prescription for other contexts.

## The model

``` mermaid
flowchart TD
    accTitle: Platform reference model overview
    accDescr: Shows the Tool Landscape feeding a Developer Platform boundary that contains the Curated Stack, Golden Path, Starter Templates, and Guardrails, with the stack driving the path, templates, and guardrails, and the path and templates also flowing into guardrails.
    L["Tool Landscape\nDescriptive context"]

    subgraph Platform["Developer Platform"]
        P["Curated Stack\nPrescriptive stack"]
        G["Golden Path\nPrescriptive workflow"]
        T["Starter Templates\nImplementation scaffolds"]
        R["Guardrails\nAutomated enforcement"]
    end

    L ==> P
    P ==> G
    P ==> T
    G ==> T
    T ==> R
    P ==> R
    G ==> R
```

| Element | Type | Question | Artifact |
| --- | --- | --- | --- |
| Tool landscape | Descriptive | What exists? | Survey, catalog |
| Curated stack | Prescriptive | What do we use? | Stack list |
| Golden path | Prescriptive | How do we work? | Workflow definition |
| Starter templates | Implementation | How do we start? | Project scaffolds |
| Guardrails | Enforcement | How do we comply? | Automated policies |

The landscape describes available options; the stack and path prescribe specific choices; templates automate setup; guardrails automate verification.

## The tool landscape

The tool landscape is the descriptive catalog of tools, technologies, and practices available in a domain.

It sits outside the platform itself — it's the knowledge base platform decisions draw from — and answers *what tools and categories exist?*

Boilerplate maintains this as [The Development Environment Landscape](../../design/dev-environment-landscape.md), a taxonomy covering language runtimes, dependency management, code quality, testing, and CI/CD tooling.

Category names in the curated stack below are drawn from it.

## The curated stack

The curated stack is the standardized technology stack: the subset of the landscape the organization commits to supporting. It answers *what do we use?*

The stack's picks for the inner-loop slots are what the [Environment guide](../../environment/index.md) calls the **Toolchain**; that page documents each tool's configuration and daily use.

### Boilerplate reference implementation: Stack

| Category | Standard | Rationale |
| --- | --- | --- |
| **Python interpreter** | Python 3.12+ | Modern syntax (match statement, current type-hint features), active security support |
| **Environment & package/dependency management** | uv | Fast dependency resolution and installs, pip-compatible, integrated venv management |
| **Linters & code formatters** | ruff | Combines linting and formatting in one tool, replaces flake8/black/isort, minimal config |
| **Type checkers** | pyright (strict mode) | Native VS Code integration via Pylance; strict mode catches more than default mode |
| **Testing frameworks** | pytest + pytest-cov | Fixture-based testing with a large plugin ecosystem; coverage via `pytest --cov` |
| **Build tools** | uv build (hatchling backend) | Standards-compliant (PEP 517/660), pure-Python backend |
| **Version control** | Git | Branching and merging underpin template composition and CI workflows |
| **CI/CD** | GitHub Actions (recommended) | Boilerplate's own gate runs on it |
| **Documentation generators** | MkDocs Material | Markdown-native authoring, built-in navigation and search |
| **IDEs & editors** | VS Code | Extension ecosystem (Pylance, Ruff, pytest), remote development support |

!!! note "Planned"
    Generated projects don't scaffold CI config or a deploy-time and runtime guardrail layer: wire the three quality-check commands into your own CI provider's workflow. See the [backlog](../../roadmap.md#backlog).

Templates scaffold the interpreter, dependency-management, lint/format, type-checking, testing, and build rows. The CI/CD and documentation rows are recommended picks you wire yourself.

For detailed configuration and usage, see:

- [Environment overview](../../environment/index.md)
- [uv guide](https://docs.astral.sh/uv/)
- [Ruff guide](https://docs.astral.sh/ruff/)
- [Pyright guide](https://github.com/microsoft/pyright)
- [pytest guide](https://docs.pytest.org/)

## The golden path

A golden path is the supported, opinionated way to build one kind of project, from creating it through running it; each starter template is one, and a step along the way can have its own ([glossary](../../design/01-overview.md#glossary)). The development workflow below is one, for a general Python project. The term is Spotify's; Netflix calls the same idea the paved road. It answers *how do we work?*

The path is not mandatory — developers may diverge when circumstances warrant — but it's the most-supported, lowest-friction route, and platform investment (documentation, templates, CI automation) centers on it.

### Development workflow

``` mermaid
flowchart TD
    accTitle: Golden Path development workflow
    accDescr: A linear development flow from Create Project through Initialize Environment, Develop Features, Run Code Quality Checks, Run Tests, Build Artifacts, CI Validation, Deploy, to Operate and Monitor, with feedback arrows returning lint, type, test, CI, deploy, and incident failures to earlier stages for remediation.
    A[Create Project] --> B[Initialize Environment]
    B --> C[Develop Features]
    C --> D[Run Code Quality Checks]
    D --> E[Run Tests]
    E --> F[Build Artifacts]
    F --> G[CI Validation]
    G --> H[Deploy]
    H --> I[Operate & Monitor]

    D -->|Lint/type errors| C
    E -->|Test failures| C
    G -->|CI failures| C
    H -->|Deploy failures| G
    I -->|Incidents| C
```

### Tool engagement by stage

| Stage | Platform Tools | Guardrails Active | Template Support | Guide |
| --- | --- | --- | --- | --- |
| **Project creation** | uv, copier | — | ✓ Scaffold structure | [Quickstart](../../quickstart.md), [Templates Hub](../../templates-hub/index.md) |
| **Environment setup** | uv (sync, venv) | — | ✓ Pre-wired configs | [Install](../../install.md), [Environment](../../environment/index.md) |
| **Feature development** | VS Code, Pyright (live) | ✓ Format-on-save (optional) | ✓ Project structure guidance | [Environment](../../environment/index.md) |
| **Code quality** | ruff check, ruff format | — | ✓ Config locked in pyproject.toml | [Ruff guide](https://docs.astral.sh/ruff/) |
| **Testing** | pytest, pytest-cov | — | ✓ Test skeleton | [pytest guide](https://docs.pytest.org/) |
| **Build** | uv build | — | ✓ pyproject.toml build config | [Environment](../../environment/index.md) |
| **Operate** | Logs, metrics, error tracking | — | — | — |

### The path in practice

| Stage | Command | What you get |
| --- | --- | --- |
| Project creation | `boilerplate new project my-project` | `src/`, `tests/`, `notebooks/`, `.vscode/`, `pyproject.toml`, README, `.gitignore` |
| Environment setup | `scripts/install.ps1`, then `uv sync` | Git, uv, VS Code, and extensions on Windows (macOS/Linux install the same tools manually), then the project venv |
| Code quality | `uv run ruff check --no-fix` · `uv run ruff format --check` · `uv run pyright` | Lint, formatting, and strict type checks |
| Testing | `uv run pytest` | Auto-discovery under `tests/`; coverage available via `pytest --cov` |

Running the three quality checks plus tests on every push is the recommended CI setup.

## Starter templates

Starter templates are project scaffolds that encode platform decisions so developers can immediately follow the golden path. They answer *how do we start?*

### Boilerplate reference implementation: Templates

| Template | Use Case | Key Features |
| --- | --- | --- |
| [project](../../templates-hub/project.md) | General Python libraries/packages | Complete pyproject.toml, test suite |
| [streamlit](../../templates-hub/streamlit/index.md) | Interactive data/ML applications | Streamlit app scaffold, container deployment configs |

See [Choose a template](../../templates-hub/index.md#choose-a-template) for the full catalog. Templates use [Copier](https://copier.readthedocs.io/) for scaffolding. Complex projects can compose multiple templates; see [Template composition](../../templates-hub/composition.md).

## Guardrails

Guardrails are automated policies that convert platform standards from documentation into enforced behavior. They answer *how do we comply?*

### Boilerplate reference implementation: Guardrails

| Guardrail | Enforcement Point | Tool/Mechanism | Remediation |
| --- | --- | --- | --- |
| **Lint compliance** | Dev (optional) | `ruff check` | `uv run ruff check --fix` |
| **Format compliance** | Dev (on-save) | `ruff format --check` | `uv run ruff format` |
| **Type safety** | Dev (live) | `pyright --strict` | Add type hints; see [Pyright guide](https://github.com/microsoft/pyright) |
| **Test passage** | Dev (on-demand) | `pytest` + coverage | Fix failing tests; add tests for uncovered code |

These four are what's active today: lint, format, type, and test checks.

Ruff, Pyright, and pytest are all configured in `pyproject.toml`; see [Configuration](../../environment/index.md#configuration) for the exact section names.

## Where next

Continue to [Quickstart](../../quickstart.md) for a hands-on walkthrough, or [Templates Hub](../../templates-hub/index.md) for the template catalog. For merge and composition mechanics, see [Merging and precedence rules](../merging.md).
