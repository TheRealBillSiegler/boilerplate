# Template composition

Composition lets one template build on another through an `extends` list in its `boilerplate.yml`. It reduces duplication and keeps shared conventions centralized.

## Extending a template

`boilerplate.yml` excerpt from the Streamlit template:

```yaml
name: streamlit
version: 0.1.1
description: Streamlit boilerplate for data applications
extends:
  - project
```

Rules:

1. A parent must be discoverable by name via `boilerplate list`.
2. Multiple parents are supported. Siblings are processed in `extends` declaration order, deterministically; later-declared siblings render later and take precedence on conflicts.

!!! warning "Before you extend"
    - Lists merge by union only — inherited entries can't be removed or reordered, so design list-type questions to be purely additive.
    - Dict questions overlay shallowly — a child overriding one key inside a nested structure replaces the whole structure at that level, not just that key — keep nested config shallow or split it into flat keys.
    - File conflicts aren't diagnosed — if a child writes a path the parent also writes, the child's version wins silently, with no warning — diff the output after generation.

!!! info "Planned"
    Version-pinned `extends` constraints (`parent@>=1.2`) and file-conflict reporting (`compose --conflicts`) are tracked on the [roadmap backlog](../roadmap.md#backlog).

## Concepts

| Term | Meaning |
|------|---------|
| Base template | A template that does not declare parents, e.g., `project`. |
| Derived template | A template that declares one or more parents via `extends`, e.g., `streamlit`. |
| Layer | A concrete node in the dependency graph representing one template's contribution: name@version + filesystem path. |
| Execution sequence | Deterministic order the layers apply (dependencies first, target last). |
| Dependency graph | Nodes, edges, and computed sequence describing template dependencies. |
| Merged configuration | The merged configuration after all layers; a questions-only view is also available. |
| Delta | Per-layer change set: subset of keys this layer adds or overrides relative to previous state. |

Concept → class: a layer is `CompositionLayer` and its changes are `CompositionLayer.delta`; the sequence and graph are `Composition.sequence` and `CompositionGraph`; the merged configuration is `Composition.final`, with `Composition.merged_questions_schema` as the questions-only view; templates are `TemplateInfo` with parents in `TemplateMeta.extends`. Field-level detail: [Data models § Composition Domain Models](../design/02-data-models.md#composition-domain-models).

## Execution order

Layering supports multiple parents (a dependency graph) and always executes linearized, dependencies first and the target template last; sibling ordering and conflict precedence follow the rules under [Extending a template](#extending-a-template) above.

Run:

```powershell
uv run boilerplate graph streamlit
```

Output (abridged):

```text
#   Layer       Version   Path
1   project     0.2.1     .../templates/project
2   streamlit   0.1.1     .../templates/streamlit
```

Layers apply in this order: each layer's question schema and internal directives (`_jinja_extensions`, `_tasks`) merge into the accumulated result. See [CLI examples § Inspect a template graph](../cli-examples.md#inspect-a-template-graph) for the full `--format json` payload.

Each layer's own `.copier-answers.<layer>.yml` records the full merged answer set visible at that layer's render, but a per-layer `copier update` reads only that layer's own `copier.yml` — Copier drops any answer key the layer doesn't declare on its first update. Every layer must therefore redeclare each answer its own files or paths use, inherited ones included (`streamlit` redeclares `project_name`, `project_slug`, `package_name`, and `package_index_url`). See the [Authoring guide](authoring.md#template-composition) for the `_answers_file` how-to.

## Merge & delta semantics

Query full composition:

```powershell
uv run boilerplate compose streamlit --all --format yaml
```

Merge strategies are a fixed set — per question type under [What gets merged](../reference/merging.md#what-gets-merged), per directive key under [Allowlisted directive keys](../reference/merging.md#allowlisted-directive-keys-and-strategies) — with no way to declare a per-field strategy. Incompatible types for the same question raise `BP_RESOLVE_MERGE_CONFLICT`; see [Determinism and conflict handling](../reference/merging.md#determinism-and-conflict-handling).

## Diagnostics toolkit

| Command | Purpose | Typical Use |
|---------|---------|--------------|
| `boilerplate list` | Discover available templates | Verify parent existence |
| `boilerplate graph streamlit` | View ordered layers | Confirm inheritance chain |
| `boilerplate compose streamlit --stats` | High-level metrics (layers, keys) | Sanity check complexity |
| `boilerplate compose streamlit --sections deltas` | Show per-layer differences | Author focus when extending |
| `boilerplate compose <tpl> --all --format yaml` | Full introspection | Deep troubleshooting |

## Worked example

Goal: Add a Streamlit UI to any standard project without duplicating base scaffolding.

What the streamlit layer contributes:

| Category | Added Value |
|----------|-------------|
| Runtime Dependencies | `streamlit`, `pydantic` |
| App Entry Point | `app.py` with service-driven greeting example |
| Domain Structure | `models/` & `services/` packages encouraging separation |
| Containerization | `Dockerfile`, container scripts (build/push) |
| Developer Experience | VS Code `launch.json` for F5 debugging |
| Tests | Integration smoke test (`tests/integration/{{ package_name }}/tests_app.py.jinja`) |

Because the schema changes are contained (a `dependencies` override plus the new `container_registry` prompt), all other prompts remain aligned with the base template—no redundant customization logic.

Observed example specifics for the Streamlit chain:

| Aspect | Observed | Explanation |
|--------|----------|-------------|
| `dependencies` list | Default replaced with two entries | Base declares `dependencies` with an empty default; the child question dict shallow-overrides it, so `default` becomes the child's list while `type` and `help` are inherited |
| Absent questions | Inherited unchanged | Values simply flow through cumulative state |
| `_tasks` | Single task from base only | Child adds none; accumulation == base list |
| `_jinja_extensions` | Three entries (all from base) | Child declares two, both duplicates of base entries, so union == base list |

Delta for `streamlit` layer (excerpt):

```yaml
dependencies:
  default:
    - streamlit
    - pydantic
```

Interpretation: the streamlit layer overrides the `dependencies` question and adds one new question, `container_registry` (type `str`, default `ghcr.io`). (`_tasks` never appears in deltas or per-layer values; inspect the accumulated task list in the merged configuration, e.g. `--sections final`.)

File system overlay (illustrative):

| Origin | Files (examples) |
|--------|------------------|
| project | `pyproject.toml.jinja`, `README.md.jinja`, `src/{{ package_name }}/__init__.py.jinja`, base test scaffold |
| streamlit | `src/{{ package_name }}/app.py.jinja`, `src/{{ package_name }}/models/greeter.py.jinja`, `src/{{ package_name }}/services/greeter.py.jinja`, `Dockerfile.jinja`, `.vscode/launch.json.jinja`, integration test |

File overlay follows [last-layer-wins semantics](../reference/merging.md#file-overlay); the streamlit layer only adds new paths here, so no overwrite occurs.

## Author checklist

Recommended workflow:

1. Start from base: design only the deltas you truly need.
2. After edits, run `compose --sections deltas` to ensure minimal surface area.
3. If you added conflicting files, explicitly note the rationale in your template README.

Before publishing:

```text
☐ Parent template listed by `boilerplate list`
☐ Only required deltas introduced (verify with --sections deltas)
☐ New files do not duplicate or fork base files without reason
☐ Dependencies kept minimal and scoped to added functionality
☐ Launch/debug assets only when necessary
```

Return to the [Templates Hub](index.md) · See the [Authoring guide](authoring.md)
