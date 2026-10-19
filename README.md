# <img src="docs/assets/boilerplate.svg" width="40" alt=""> Boilerplate

[![CI](https://github.com/TheRealBillSiegler/boilerplate/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/TheRealBillSiegler/boilerplate/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Composable project scaffolding, built on [Copier](https://copier.readthedocs.io/) — template authors declare composition with `extends`; consumers get one command, one merged question set, and deterministic precedence when layers overlap.

**Less yak. More stack.**

![Terminal recording: the Boilerplate banner, then boilerplate new project walks through a few prompts, scaffolds a project, and uv run pytest passes.](docs/assets/demo/boilerplate-new.gif)

Copier applies multiple independent templates [by hand, one answers file each](https://copier.readthedocs.io/en/stable/configuring/#applying-multiple-templates-to-the-same-subproject) — a pattern its maintainers note works easiest when templates stay disjoint; declared template hierarchies have [upstream design approval but are left to community contribution](https://github.com/copier-org/copier/issues/934). Boilerplate is that missing layer. Templates stay standard Copier templates — composition metadata lives in a separate `boilerplate.yml`, and your `copier.yml` is never modified. See [Why Boilerplate?](docs/why.md).

## Install

Boilerplate is distributed via GitHub — it is **not yet published to PyPI**.

<!-- x-release-please-start-version -->

```bash
# Install the CLI from source (recommended)
uv tool install git+https://github.com/TheRealBillSiegler/boilerplate.git@v0.3.0

# or with pip
pip install git+https://github.com/TheRealBillSiegler/boilerplate.git@v0.3.0
```

<!-- x-release-please-end -->

## Quick Start

```bash
boilerplate list
boilerplate new project my-app
boilerplate new streamlit my-dashboard
```

## Customizing for your organization

Boilerplate ships with PyPI / GHCR defaults. To stamp your own values (a private package index, a container registry) into generated projects, drop a `profile.toml` in the boilerplate config directory — no forking required. See the [Customization guide](docs/customization.md) for profiles, layers, and the org-adoption pattern.

## Features

Available now:

- **Layered templates** — compose multiple templates via `extends` inheritance
- **Configuration & question merging** — combine layers into one coherent scaffold
- **Dependency graphs** — visualize template relationships with `boilerplate graph`
- **Profile** — pre-fill any template's questions (e.g. your org's feed and registry) from a `profile.toml`, without forking
- **Lock file** — `boilerplate new` writes `boilerplate.lock`, recording each layer's template provenance; nothing reads it yet

Planned (designed, not yet implemented):

- **Lock verification** — check a project against its lock for reproducible scaffolding
- **Three-way-merge updates** — update projects non-destructively when templates evolve
- **Trust model** — control task execution by template source

See [Implementation Status](docs/status.md) for the full design-vs-code map.

## Documentation

Full documentation is available at the [docs site](docs/index.md):

- [Installation](docs/install.md)
- [CLI Reference](docs/cli.md)
- [Template Authoring](docs/templates-hub/authoring.md)
- [Design Specifications](docs/design/01-overview.md) — authoritative design and requirements for the Boilerplate system

## Shell Completion

```bash
boilerplate --install-completion  # bash, zsh, fish, PowerShell
```

## Development

Boilerplate is managed with [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/TheRealBillSiegler/boilerplate.git
cd boilerplate
uv sync
```

### Run checks

```bash
uv run ruff check --no-fix .  # lint
uv run pytest                 # test
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full contribution guidelines.

## License

[Apache License 2.0](LICENSE)
