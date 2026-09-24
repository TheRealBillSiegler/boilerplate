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
| `_tasks`              | Post-generation commands, run from the generated project root; scripts they call must ship in the template |
| `when: false`         | Hide a question (computed value)               |

## Template composition

Templates can inherit from other templates using `extends` in `boilerplate.yml`. See the [Composition guide](composition.md) for merge rules, layer order, and diagnostics commands.

When authoring a child template, its `copier.yml` only needs to declare what it overrides or adds — not the full parent config:

```yaml
# streamlit/copier.yml
dependencies:
  default: ["streamlit", "pydantic>=2"]
```

Declare `_answers_file: .copier-answers.<layer>.yml` in `copier.yml` and ship an answers-file stub — a template file literally named `{{ _copier_conf.answers_file }}.jinja` rendering `_copier_answers` (see `project`'s stub for the reference pattern). Copier writes an answers file only by rendering that stub; the directive alone is inert, and `boilerplate validate` warns when a composition-intended template (one declaring `_answers_file` or `extends`) ships without it. See the [Composition guide § Layer order](composition.md#layer-order) for why every layer must redeclare the inherited answers its own files or paths use.

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
- **Version your templates** with PEP 440 versions (plain `X.Y.Z` works). The version moves once per release, not once per change — see [when to bump](versioning.md#when-to-bump).
- **Point the CLI at your template**: custom templates live outside the bundled templates directory, so point the CLI at the directory *containing* `my-template/` with `--templates-dir` (works on `new`, `list`, `graph`, and `compose`; it adds to the search path, so bundled parents stay resolvable for `extends`) or set it persistently via [`BOILERPLATE_EXTRA_TEMPLATE_DIRS`](../customization.md#layers-structure).
- **Test rendering** with `boilerplate new my-template test-output --force --templates-dir <parent-dir>`.
- **Inspect composition** with `boilerplate compose` and `boilerplate graph` before publishing multi-layer templates.

## Keeping a project's work

A project generated from your template is a git repository, and `copier update` reads it as one: it refuses a dirty tree, diffs against the index, and merges through it. Anything outside that index is invisible to the merge. Three habits follow; the rules themselves are in [Template versioning](versioning.md#authoring-rules).

### Rename through a staged move

Copier deletes every path your new version stops rendering, by name, without comparing content — so a project that edited the old file loses the edit, at exit 0, with nothing in the working tree to show it. A `before`-stage migration that moves *and stages* the file turns that deletion into a conflict carrying both versions:

```yaml
# copier.yml
_migrations:
  - when: "{{ _stage == 'before' }}"
    command:
      - "{{ _copier_python }}"
      - -c
      - |
        import pathlib
        import subprocess

        old = pathlib.Path("tests/smoke_test.py")
        new = old.with_name("test_smoke.py")
        if old.exists() and not new.exists():
            subprocess.run(["git", "mv", str(old), str(new)], check=True)
```

The entry declares no `version`, so Copier runs it on every update; the state check makes it a no-op once the old name is gone. Ship it in the same change as the rename, with a test that drives a real `copier update` from the previous tag — `tests/boilerplate/templates/test_streamlit_update_migration.py` in this repository is the worked example.

### Render nothing your `.gitignore` matches

An ignored file never enters the index, so the merge cannot see it: no conflict marker, no `.rej` file, nothing in history to recover. The reverse holds too — do not ignore a file your README tells the user to commit.

### Say who owns each file

A file your template keeps changing is template-owned: a project that edits it risks a conflict whenever a release touches the same lines, and on a file small enough that one diff hunk spans it, any release at all. A file the project should own after the first render belongs in `_skip_if_exists`: the template writes it once and never touches it again. Choose per file and say which; silence means template-owned. The choice matters most for the files users are expected to rewrite — the README, the entry point, a sample module.

## Bundled examples

The bundled templates serve as working examples:

- **`project`** — base Python template ([source](https://github.com/TheRealBillSiegler/boilerplate/tree/main/src/boilerplate/templates/project))
- **`streamlit`** — extends `project` with Streamlit defaults ([source](https://github.com/TheRealBillSiegler/boilerplate/tree/main/src/boilerplate/templates/streamlit))

Run `boilerplate list` to see all available templates.

## Where next

See the [Composition guide](composition.md) for merge semantics, or the [Templates Hub](index.md) to browse bundled templates.
