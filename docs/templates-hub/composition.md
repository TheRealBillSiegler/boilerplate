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
3. Version pinning (future) will allow `parent@>=1.2` style constraints.

!!! warning "Before you extend"
    - Lists merge by union only — inherited entries can't be removed or reordered, so design list-type questions to be purely additive.
    - Dict questions overlay shallowly — a child overriding one key inside a nested structure replaces the whole structure at that level, not just that key.
    - File conflicts aren't diagnosed — if a child writes a path the parent also writes, the child's version wins silently, with no warning.

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

Layering supports multiple parents (a dependency graph); execution is always linearized, with dependencies applied first and the target template last. Sibling ordering and conflict precedence are covered under **Extending a template** above.

Model mapping: templates are `TemplateInfo` with parents in `TemplateMeta.extends`; a layer is a `CompositionLayer`; the sequence and graph are `Composition.sequence` / `CompositionGraph`; the merged result is `Composition.final` (`Composition.merged_questions_schema` for the questions-only view); a layer's changes are `CompositionLayer.delta`.

## Execution order

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

Layers apply in this order: each layer's question schema and internal directives (`_jinja_extensions`, `_tasks`) merge into the accumulated result.

JSON graph payload (shape used by tools when `--format json`):

```json
{
  "sequence": [
    "project@0.2.1",
    "streamlit@0.1.1"
  ],
  "layers": [
    {
      "specifier": "project@0.2.1",
      "name": "project",
      "version": "0.2.1",
      "path": ".../templates/project",
      "deps": []
    },
    {
      "specifier": "streamlit@0.1.1",
      "name": "streamlit",
      "version": "0.1.1",
      "path": ".../templates/streamlit",
      "deps": ["project@0.2.1"]
    }
  ]
}
```

## Merge & delta semantics

Query full composition:

```powershell
uv run boilerplate compose streamlit --all --format yaml
```

Composition applies explicit strategies:

| Category | Strategy | Notes |
|----------|----------|-------|
| Question (scalar) | Override | Later layer value replaces earlier |
| Question (dict) | Shallow override | Key-level override; no deep merge beyond 1 level |
| Question (list) | Union (dedupe, preserve first-seen order) | Acts like append then de-duplicate; cannot remove or reorder prior entries |
| `_tasks` | Accumulate (ordered concat) | All tasks preserved in the merged result; `_tasks` never appears in per-layer deltas |
| `_jinja_extensions` | Union (dedupe) | First occurrence order retained |
| `_secret_questions` | Accumulate | Rare; concatenated if present |
| Other underscore keys | Layer-local (not merged) | Ignored in the merged configuration |

Conflict handling:

- Incompatible question types for the same key (e.g., list vs dict) raise a merge error.
- `_min_copier_version` resolves to the highest version across layers.

Observed example specifics for the Streamlit chain:

| Aspect | Observed | Explanation |
|--------|----------|-------------|
| `dependencies` list | Default replaced with two entries | Base declares `dependencies` with an empty default; the child question dict shallow-overrides it, so `default` becomes the child's list while `type` and `help` are inherited |
| Absent questions | Inherited unchanged | Values simply flow through cumulative state |
| `_tasks` | Single task from base only | Child adds none; accumulation == base list |
| `_jinja_extensions` | Three entries (all from base) | Child declares one, a duplicate of a base entry, so union == base list |

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

Current merge rule for files: *last layer wins* on path conflicts (no three‑way diff yet). The streamlit layer only adds new paths, so no overwrite occurs.

## Diagnostics toolkit

| Command | Purpose | Typical Use |
|---------|---------|-------------|
| `boilerplate list` | Discover available templates | Verify parent existence |
| `boilerplate graph streamlit` | View ordered layers | Confirm inheritance chain |
| `boilerplate compose streamlit --stats` | High-level metrics (layers, keys) | Sanity check complexity |
| `boilerplate compose streamlit --sections deltas` | Show per-layer differences | Author focus when extending |
| `boilerplate compose <tpl> --all --format yaml` | Full introspection | Deep troubleshooting |

Recommended author workflow:

1. Start from base: design only the deltas you truly need.
2. After edits, run `compose --sections deltas` to ensure minimal surface area.
3. If you added conflicting files, explicitly note rationale in your template README (future enhancement).

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
| Tests | Integration smoke test (`tests/integration/{{ package_name }}/test_app.py.jinja`) |

Because the schema changes are contained (a `dependencies` override plus the new `container_registry` prompt), all other prompts remain aligned with the base template—no redundant customization logic.

## Limitations (current state)

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| List union only (no removal / reordering) | Cannot drop or reorder inherited list items | Keep lists minimal; future strategies will allow subtract/append |
| Shallow dict overlay | Nested structures entirely overridden at first differing key | Design nested config sparingly; split into flat keys |
| No conflict diagnostics for files | Accidental overwrites could go unnoticed | Manual diff after generation (planned tooling) |
| No version constraints on parents | Risk of silent drift when base updates | Future `extends: parent@~1.2` pinning |
| Limited merge strategies (fixed set) | Cannot declare per-field behavior | Await future strategy annotations |

## Future scope (planned)

- Merge strategy annotations (e.g. `append`, `unique`, `deep-merge`)
- Conflict reporting (`compose --conflicts`)
- Version specifiers in `extends` (PEP 440 constraints)
- File overlay preview (`graph --files`)
- Author lint: fail if delta unnecessarily repeats base defaults

## Author checklist (interim)

```text
☐ Parent template listed by `boilerplate list`
☐ Only required deltas introduced (verify with --sections deltas)
☐ New files do not duplicate or fork base files without reason
☐ Dependencies kept minimal and scoped to added functionality
☐ Launch/debug assets only when necessary
```

## Quick reference

```powershell
# Inspect layers
uv run boilerplate graph streamlit

# Stats overview
uv run boilerplate compose streamlit --stats

# Just the deltas
uv run boilerplate compose streamlit --sections deltas

# Everything (YAML)
uv run boilerplate compose streamlit --all --format yaml
```

Return to the [Templates Hub](index.md) · See the [Authoring guide](authoring.md)
