# Template authoring

Create custom templates for Boilerplate. Templates are directories with two config files: `boilerplate.yml` (metadata for Boilerplate) and `copier.yml` (questions and rendering for Copier).

## Template structure

```text
my-template/
├── boilerplate.yml        # Boilerplate metadata (name, version, extends)
├── copier.yml             # Copier questions, defaults, and tasks
├── README.md.jinja        # Jinja2 template files use .jinja suffix
├── pyproject.toml.jinja
├── _scripts/
│   └── post_generation.py # Referenced by _tasks below
└── src/
    └── {{package_name}}/
        └── __init__.py.jinja
```

## Boilerplate metadata — `boilerplate.yml`

This file tells Boilerplate how to discover, version, and compose your template.

```yaml
# boilerplate.yml
schema_version: "1"       # Metadata schema version

name: my-template          # Used in `boilerplate new my-template`
version: 1.0.0             # PEP 440 — bump when template content changes
description: Short description of what this template scaffolds.

# extends: []              # Optional — list parent templates to inherit from.
#                          # Example: extends: [project]
```

| Field            | Required | Description                                      |
|------------------|----------|--------------------------------------------------|
| `schema_version` | Yes      | Always `"1"` for now.                            |
| `name`           | Yes      | Template identifier, used in CLI commands.        |
| `version`        | Yes      | PEP 440 version string (`boilerplate validate` enforces this). |
| `description`    | No       | One-line description shown in `boilerplate list`. Defaults to `""`. |
| `extends`        | No       | Parent templates this template layers on top of.  |

## Copier configuration — `copier.yml`

This file defines user-facing questions and rendering settings. It follows [Copier's configuration format](https://copier.readthedocs.io/en/stable/configuring/).

```yaml
# copier.yml
_templates_suffix: .jinja

project_name:
  type: str
  help: "What is the name of the project?"
  default: "{{ _folder_name }}"

package_name:
  default: "{{ project_name | replace('-', '_') }}"
  when: false   # Computed, not prompted

description:
  type: str
  help: "Brief project description."
  default: "A new Python project."

_tasks:
  - ["{{ _copier_python }}", _scripts/post_generation.py]
```

### Key Copier directives

| Directive             | Purpose                                       |
|-----------------------|-----------------------------------------------|
| `_templates_suffix`   | File extension for Jinja2 templates (`.jinja`) |
| `_exclude`            | Glob patterns to exclude from output          |
| `_jinja_extensions`   | Custom Jinja2 extensions to load              |
| `_tasks`              | Post-generation commands                       |
| `when: false`         | Hide a question (computed value)               |

## Template composition

Templates can inherit from other templates using `extends` in `boilerplate.yml`. See the [Composition guide](composition.md) for merge rules, execution order, and diagnostics commands.

When authoring a child template, its `copier.yml` only needs to declare what it overrides or adds — not the full parent config:

```yaml
# streamlit/copier.yml
dependencies:
  default: ["streamlit", "pydantic"]
```

Declare `_answers_file: .copier-answers.<layer>.yml` in `copier.yml` and ship an answers-file stub — a template file literally named `{{ _copier_conf.answers_file }}.jinja` rendering `_copier_answers` (see `project`'s stub for the reference pattern). Copier writes an answers file only by rendering that stub; the directive alone is inert, and `boilerplate validate` warns when a composition-intended template (one declaring `_answers_file` or `extends`) ships without it. See the [Composition guide § Execution order](composition.md#execution-order) for why every layer must redeclare the inherited answers its own files or paths use.

## Template files

Use Jinja2 syntax with the `.jinja` suffix:

```python
# src/{{package_name}}/__init__.py.jinja
"""{{ project_name }} — {{ description }}."""

__version__ = "0.1.0"
```

Directory names can also use Jinja2 variables: `{{package_name}}/` expands to the value of the `package_name` question.

## Best practices

- **Two config files**: `boilerplate.yml` for Boilerplate, `copier.yml` for Copier. Keep them separate — don't mix concerns.
- **Restate Copier's defaults in `_exclude`.** A declared `_exclude` replaces Copier's built-in list (`.git`, `copier.yml`, `__pycache__`, …) instead of extending it. Copy the bundled templates' block, which also excludes `boilerplate.yml`; otherwise a `copier update` from a git clone copies the clone's `.git` over the project's.
- **Sensible defaults** for all questions so `--non-interactive` works.
- **Use `extends`** to layer on base templates rather than duplicating files.
- **Version your templates** with PEP 440 versions (plain `X.Y.Z` works). Bump on every content change.
- **Register your template for discovery**: custom templates live outside the bundled registry, so point the CLI at the directory *containing* `my-template/` with `--templates-dir` (works on `new`, `list`, `graph`, and `compose`; it adds to the search path, so bundled parents stay resolvable for `extends`) or set it persistently via [`BOILERPLATE_EXTRA_TEMPLATE_DIRS`](../customization.md#layers-structure).
- **Test rendering** with `boilerplate new my-template test-output --force --templates-dir <parent-dir>`.
- **Inspect composition** with `boilerplate compose` and `boilerplate graph` before publishing multi-layer templates.

## Bundled examples

The bundled templates serve as working examples:

- **`project`** — base Python template ([source](https://github.com/TheRealBillSiegler/boilerplate/tree/main/src/boilerplate/templates/project))
- **`streamlit`** — extends `project` with Streamlit defaults ([source](https://github.com/TheRealBillSiegler/boilerplate/tree/main/src/boilerplate/templates/streamlit))

Run `boilerplate list` to see all available templates.

## Where next

See the [Composition guide](composition.md) for merge semantics, or the [Templates Hub](index.md) to browse bundled templates.
