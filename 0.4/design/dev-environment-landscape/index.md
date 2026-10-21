# The Development Environment Landscape

The reference taxonomy of what a Python development environment comprises. Boilerplate's design vocabulary calls each recurring role in this taxonomy a [slot](https://therealbillsiegler.github.io/boilerplate/0.4/design/01-overview/#term-slot). This document catalogues the landscape; the [§How Boilerplate maps onto the landscape](#how-boilerplate-maps-onto-the-landscape) section records which slots Boilerplate opines on.

> **Provenance.** Transcribed from the project author's *Python Development Environment* mind map, committed alongside this document as the [XMind source](https://therealbillsiegler.github.io/boilerplate/0.4/assets/python-development-environment.xmind). This transcription is the repo-canonical text form. Category definitions are the author's; example tools are illustrative, not exhaustive, and not endorsements.

## Definition

Tools, libraries, and configurations that enable scalable and maintainable Python application development, enhancing productivity, code quality, reliability, and maintainability.

## Taxonomy

### Environment

The context in which Python code runs, including the interpreter, libraries, and configurations. Effective environments ensure isolated and reproducible builds, reducing conflicts between dependencies. (In this taxonomy, *Environment* names the runtime context specifically — a narrower sense than the glossary's domain-level term.)

- **Python Interpreter** — software that reads and executes Python code. Examples: CPython, PyPy, IronPython, Jython, GraalPy, MicroPython, Stackless Python.
- **Environment Management** — tools for isolating project dependencies, preventing conflicts, and ensuring consistent builds. Examples: venv, conda, uv.

### Package/Dependency Management

Software that simplifies the installation, upgrading, and removal of Python libraries, ensuring projects have the correct versions of all required packages. Examples: pip, poetry, conda, pip-tools, pipenv, uv.

### Development Tools

Software and utilities that automate repetitive tasks, profile performance, and facilitate experimentation and prototyping.

- **Interactive Development Environments** — platforms combining code, visualizations, and explanatory text for experimentation and collaboration.
  - *Notebook Environments* — Jupyter Notebook, Google Colab, Deepnote.
  - *Remote Development Environments* — workspaces accessible via a network or abstracted from the primary local machine. Examples: GitHub Codespaces, Microsoft DevBox, Dev Containers.
  - *Interactive Shells* — advanced REPLs. Example: IPython.
- **Debugging Tools** — identifying and resolving code issues. Examples: pdb, ipdb, debugpy.
- **Build & Automation**
  - *Build Tools* — compile, package, and distribute projects into installable formats. Examples: setuptools, hatch, wheel.
  - *Task Runners* — automate repetitive development tasks for consistent workflows. Examples: invoke, nox.
- **Performance Profiling** — identify bottlenecks and optimize execution. Examples: cProfile, line_profiler, timeit, memory_profiler, py-spy, gprof2dot.

### Code Management Tools

Tools and utilities that streamline collaboration, improve code quality, and track changes throughout the software development lifecycle.

- **Version Control Systems** — track changes to source code over time, enabling collaboration, branching, merging, and reverting. Examples: Git, Mercurial.
- **Code Review Workflows** — processes for evaluating proposed changes (pull/merge requests) to ensure quality and share knowledge. Examples: GitHub, Azure DevOps, GitLab, Bitbucket.
- **Collaboration Tools** — planning, task coordination, and discussion. Examples: Azure DevOps Boards, GitHub Projects, GitLab Issues, Trello/Jira, Slack/Teams.

### IDEs & Editors

Applications providing a suite of development features — syntax highlighting, refactoring, debugging, version-control integration — to streamline coding workflows. Examples: PyCharm, Visual Studio Code, Spyder, Jupyter Notebook, Thonny.

### Code Quality Tools

Software that ensures Python code adheres to style guidelines, avoids errors, and remains maintainable.

- **Linters** — inspect code without running it to identify style issues, errors, or potential bugs. Examples: Flake8, Pylint, Ruff.
- **Code Formatters** — reformat source code to a consistent style. Examples: Black, YAPF, Ruff.
- **Type Checkers** — validate code against type annotations, catching errors early. Examples: mypy, Pyright.
- **Testing Frameworks** — create, organize, and execute automated tests.
  - *Core Frameworks* — pytest, unittest.
  - *Environment Management for tests* — tox, nox.
  - *Mocking* — unittest.mock, pytest-mock.
  - *Code Coverage* — coverage, pytest-cov.

### Deployment Tools

Technologies for packaging and deploying Python applications, automating processes and enhancing scalability.

- **Containerization** — *Containers* (Docker, Rancher Desktop) and *Container Orchestration* (Kubernetes, Rancher).
- **Serverless** — AWS Lambda, Azure Functions, Google Cloud Functions.
- **CI/CD** — continuous integration and deployment platforms. Examples: GitHub Actions, Azure Pipelines, Jenkins, TeamCity.
- **Infrastructure as Code** — Terraform, Ansible.
- **Platform as a Service** — Heroku, Google App Engine, Azure App Service.

### Security Tools

Tools that enhance the security and integrity of Python applications.

- **Static Analysis** — Bandit, Semgrep.
- **Dependency Scanning** — Safety, Dependabot, Snyk.
- **Secrets Management** — Doppler, HashiCorp Vault, Azure Key Vault.
- **Monitoring and Observability** — New Relic, Datadog, Sentry, Prometheus, Grafana.

### Documentation Tools

Tools and standards for creating and maintaining project documentation.

- **Docstring Standards** — reStructuredText, Google style, NumPy style.
- **Documentation Generators** — Sphinx, MkDocs.

### Data and Visualization Tools

Tools for manipulating, analyzing, and visualizing data.

- **Data Analysis** — pandas, numpy.
- **Visualization** — matplotlib, seaborn, Plotly.

### Learning and Experimentation

Interactive platforms and hosted environments for learning Python, prototyping, and experimenting. Examples: Jupyter Notebook, Google Colab.

## How Boilerplate maps onto the landscape

Each first-party template fills the slots its ecosystem's [dev loop](https://therealbillsiegler.github.io/boilerplate/0.4/design/01-overview/#term-dev-loop) uses — the roles a developer exercises on every pass through it — with one opinionated, preconfigured pick each, declared through the profile the template requires. The Python picks:

| Slot                                                   | Pick                                                                                                                                             |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Environment Management + Package/Dependency Management | uv                                                                                                                                               |
| Linters + Code Formatters                              | Ruff                                                                                                                                             |
| Type Checkers                                          | Pyright                                                                                                                                          |
| Testing Frameworks (core, mocking, coverage)           | pytest, pytest-mock, pytest-cov                                                                                                                  |
| Build Tools                                            | uv_build, with hatchling as the override ([ADR-017](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-017-build-backend/index.md)) |
| IDEs & Editors                                         | VS Code                                                                                                                                          |
| Version Control Systems                                | Git                                                                                                                                              |

Two rules give the mapping its shape:

- **Templates declare their slots and fill them.** A template's required profile names the tool per slot, including any secondary toolchain its kind of project needs (the `streamlit` template needs Docker and Bash; on Windows, WSL2); the environment installs and verifies what the profile declares; the template pre-wires each tool's per-project configuration — Ruff's rule set, Pyright's strictness, pytest's options, the `.vscode/` workspace settings — and scaffolds adjacent slots such as CI/CD and documentation generation as [gating scaffolding](https://therealbillsiegler.github.io/boilerplate/0.4/design/01-overview/#term-first-party-gating-scaffolding) the user opts into.
- **Slots no first-party template requires are out of scope by design.** The remaining landscape (profiling, serverless, IaC, PaaS, data tooling, …) is a scope boundary: "should Boilerplate also do X?" is answered by whether some first-party template's kind of project needs X on its golden path. Containerization enters through the `streamlit` template's required profile.

The development environment built from these picks is itself a first-class, managed surface — installation, verification, update, and drift detection across its lifecycle — per [01-overview.md §Environment lifecycle is managed](https://therealbillsiegler.github.io/boilerplate/0.4/design/01-overview/#environment-lifecycle-is-managed) and the provisioning design in [§08](https://therealbillsiegler.github.io/boilerplate/0.4/design/08-environment-provisioning/index.md) / [ADR-009](https://therealbillsiegler.github.io/boilerplate/0.4/design/adr-009-environment-provider-protocol/index.md).
