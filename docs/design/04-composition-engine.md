# Composition Engine

## Purpose

The composition engine takes a template reference, resolves its dependency graph, merges configuration from all layers, and produces a `CompositionArtifact` ready for rendering. The engine orchestrates Copier without replacing it — it resolves dependencies and merges configuration, then delegates actual file rendering to Copier.

The engine is composed of four sequentially-invoked stages:

```text
Stage 1: Resolver
Stage 2: Dependency Graph & Topological Sort
Stage 3: Composer (uses CopierConfigMerger)
Stage 4: RenderEngine
```

*The four-stage decomposition and the worker interfaces below are a reference implementation structure; a conforming implementation MAY organize this differently. The normative requirements are the MUST/MUST NOT statements.*

---

## Stage 1 — Resolver

### Responsibility

The Resolver takes a template reference and a populated catalog, performs a depth-first traversal of the `extends` chain, and returns a `Resolution` containing:
- `deps`: a DependencyMap (specifier → list of direct dependency specifiers)
- `templates`: a map from specifier string → `TemplateInfo`

The Resolver does not detect or report cycles — that is the graph layer's responsibility. The `visited` set in the resolution algorithm prevents redundant traversal of diamond dependencies (e.g., `A → B, A → C, B → C` visits `C` only once) but preserves all dependency edges so the graph layer can detect cycles. The Resolver MUST NOT mutate any catalog state. It MUST be pure with respect to its inputs.

### Template Reference Syntax

A template reference is either `"name"` (resolves to latest) or `"name@version"` (exact). See [02-data-models.md §TemplateSpecifier](02-data-models.md#templatespecifier).

### Resolution Behavior

The Resolver performs a depth-first traversal of the `extends` chain starting from the root template. For each template encountered, it records the template's information and its direct dependencies (as declared in `meta.extends`), then recurses into each dependency. A visited set prevents redundant traversal of shared dependencies (diamond patterns), but dependency edges are always recorded — even when the target has already been visited — so that the full edge set is available for cycle detection in the graph layer. After traversal completes, the Resolver checks for version conflicts: if the same template name appears at different versions anywhere in the graph, it raises `BP_RESOLVE_VERSION_CONFLICT`.

**Key invariants**:

- Each specifier is visited at most once, but all dependency edges are preserved.
- Direct dependencies preserve the declaration order from `meta.extends`.
- All referenced templates MUST exist in the catalog; if any are missing, raise `DependencyNotFoundError`.
- Template references are resolved via the catalog: unversioned references (`name`) resolve to the latest version; versioned references (`name@version`) resolve to the exact version.

### Version conflict resolution

When the same template name is encountered at different versions during dependency traversal (diamond dependency with version disagreement), the Resolver MUST reject the composition with `BP_RESOLVE_VERSION_CONFLICT`:

```text
BP_RESOLVE_VERSION_CONFLICT
What: Template 'base' required at version 1.0.0 (by 'layer-a') and 2.0.0 (by 'layer-b')
Why: Diamond dependency with incompatible version constraints
Remediation: Align all references to 'base' to a single version, or use version ranges that resolve to a common version
Attribution: Template Author
```

The Resolver MUST NOT silently pick one version over another; version conflicts are always an error, because silent resolution could yield different results for different traversal orders.

> **Future**: Version range specifiers (e.g., `name@>=1.0,<2.0`) are reserved for a future release. The current `extends` syntax accepts exact version pins and unversioned references only.

### Graph size limits

To prevent pathological compositions and protect against accidental infinite recursion:

- Maximum dependency chain depth: **20 templates**. Exceeded → `BP_GRAPH_DEPTH_EXCEEDED`.
- Maximum total nodes in the resolved graph: **50 templates**. Exceeded → `BP_GRAPH_SIZE_EXCEEDED`.

The defaults MUST be enforced.

### Errors

| Error | Condition |
|-------|-----------|
| `DependencyNotFoundError` | A template reference cannot be resolved in the catalog |
| `InvalidTemplateSpecifierError` | A versioned reference fails specifier parsing |

---

## Stage 2 — Dependency Graph and Topological Sort

Between the Resolver output and the Composer, the dependency map is normalized and sorted.

### Normalization

Normalization prepares the raw dependency map for topological sorting. It deduplicates each node's dependency list while preserving declaration order from `extends`, ensures every referenced node appears as a key (with an empty list if it has no dependencies of its own), and detects self-cycles immediately (raising `DependencyCycleError`).

### Topological Sort

After normalization, the dependency map is sorted into a dependency-first ordered list. Any topological sort that produces a deterministic, dependency-first sequence satisfies the contract — the invariant is the ordering guarantee, not the specific algorithm. If a cycle is detected, `DependencyCycleError` is raised.

**Invariant**: Given `A extends [B, C]`, `B` and `C` MUST appear before `A` in the sequence.

**Tie-breaking rule**: When multiple nodes have zero in-degree simultaneously (independent subgraphs or branches), the sort MUST break ties by lexicographic ordering of the normalized template specifier string (name@version). This ensures deterministic output regardless of hash-map iteration order or platform differences. Lexicographic tie-breaking applies only across independent roots (nodes no other node depends on); within a root's reachable subgraph, `extends` declaration order governs (per the diamond dependencies rule below), and a dependency shared across roots is emitted at its first occurrence.

**Example** (linear chain):

```text
Input:  { "A": ["B"], "B": ["C"], "C": [] }
Output: ["C", "B", "A"]
```

**Diamond dependencies**: When a diamond dependency is detected, Boilerplate resolves file precedence by declaration order in the `extends` list. Dependencies declared later in `extends` are rendered later and their files take precedence. For example, given `extends: [base-lib, utility-lib]`, `utility-lib` is rendered after `base-lib` and its files win on conflict. This rule applies recursively: if both `base-lib` and `utility-lib` themselves extend a shared dependency, the shared dependency is rendered once, and the extending template that appears later in the original `extends` declaration takes precedence. Determinism is guaranteed by the normalization step, which preserves declaration order from `extends`.

```text
// Diamond: C extends [A, B], A extends [Base], B extends [Base]
Input:  { "C": ["A", "B"], "A": ["Base"], "B": ["Base"], "Base": [] }
Output: ["Base", "A", "B", "C"]  // B declared after A in extends; B's files override A's at same paths
```

File precedence follows the topological render order: templates rendered later overwrite files from templates rendered earlier at the same path. For direct children listed in `extends`, this means later-declared entries take precedence. For deeper dependency graphs, the topological sort determines the authoritative order — use `boilerplate graph` to verify the actual render sequence.

**CLI visibility**: When `boilerplate graph` detects a diamond dependency pattern (a node reachable via two or more paths), the output MUST annotate affected nodes with a `[diamond]` indicator and note which parent's files take precedence. Example:

```text
#   Layer          Version   Path                      Notes
1   base           1.0.0     /path/to/base
2   parent-a       1.0.0     /path/to/parent-a
3   parent-b       1.0.0     /path/to/parent-b         [diamond: files override parent-a]
4   my-template    1.0.0     /path/to/my-template
```

**Errors**:

| Error | Condition |
|-------|-----------|
| `DependencyCycleError` | A cycle exists in the dependency graph (e.g., `A → B → A`) |

---

## Stage 3 — Composer

### Responsibility

The Composer takes a `Resolution` and produces an immutable `CompositionArtifact`. It:
1. Extracts and merges Copier configuration from all template layers
2. Builds the `CompositionGraph`
3. Produces a `CompositionLayer` for each template in topological order
4. Optionally computes per-layer states and deltas (for debugging and introspection)

### Composition Behavior

The Composer processes templates in topological order. For each template in the sequence, it reads the template's `copier.yml` configuration and builds a `CompositionLayer` containing the template's name, version, path, and user-facing question values (non-underscore keys). All layer configurations are then merged using the `CopierConfigMerger` to produce the final merged schema.

When introspection is requested (`include_states` or `include_deltas`), the Composer additionally tracks the cumulative configuration state after each layer and/or the delta each layer contributes. These are attached to the corresponding `CompositionLayer` for use by inspection commands.

The Composer also builds a `CompositionGraph` from the resolution data, recording each template as a graph node (with name, version, and path) and preserving the dependency edges in declaration order.

The final output is a `CompositionArtifact` containing the graph (with its topological sequence), the per-layer details, and the fully merged configuration schema.

---

## Configuration Merger

### Responsibility

The `CopierConfigMerger` merges a list of `copier.yml` configuration dictionaries (one per layer, in topological order) into a single unified configuration.

### Merge Rules

The strategy applied to each key is determined by the following lookup, in priority order:

| Key pattern | Strategy | Notes |
|-------------|----------|-------|
| `_min_copier_version` | `intersect_versions` | Highest declared minimum version wins |
| `_tasks` | `accumulate` | All tasks from all layers concatenated |
| `_secret_questions` | `accumulate` | All secret question names concatenated |
| `_jinja_extensions` | `union` | Extensions deduplicated, first-seen order |
| Any key not starting with `_` | `merge_questions` | All user question keys |
| Any other `_`-prefixed key | **layer-local** (excluded from merge) | Last layer's value is used; not propagated. Examples: `_exclude`, `_templates_suffix`, `_subdirectory` |

**Fallback rule**: any `_`-prefixed key not explicitly listed above is treated as layer-local and excluded from the merged output. This is a closed-world assumption: only the keys listed above participate in merging.

### Merge Strategies

The four merge strategies used by the configuration merger are defined below. Each strategy corresponds to one or more key patterns in the key-to-strategy mapping table above.

#### `accumulate`

Concatenates lists in order; wraps scalars in a single-element list.

```text
accumulate([["task_a"], ["task_b", "task_c"]]) → ["task_a", "task_b", "task_c"]
```

Used for: `_tasks`, `_secret_questions`.

#### `union`

Concatenates lists preserving first-seen order, removing duplicates.

```text
union([["ext_a", "ext_b"], ["ext_b", "ext_c"]]) → ["ext_a", "ext_b", "ext_c"]
```

Used for: `_jinja_extensions`.

#### `intersect_versions` (highest wins)

Given a list of PEP 440 version strings, returns the maximum.

```text
intersect_versions(["1.0", "2.0", "1.5"]) → "2.0"
```

Used for: `_min_copier_version`.

#### `merge_questions`

Merges user question values:
- **Dict + Dict** → shallow merge (later layer's keys override earlier; only the top level is merged, nested dicts are replaced wholesale)
- **List + List** → deduplicated concatenation (items from earlier layers first, then later layers; items compared by value equality; insertion order of first appearance is preserved)
- **Scalar + Scalar (same type)** → override (later value wins)
- **Type mismatch** → raise `MergeConflictError`

> **Detection timing**: Type mismatches MUST be detected during the `compose` stage (when configurations are merged), not during the `render` stage (when the end user runs the template). This ensures template authors catch conflicts during `boilerplate compose` or `boilerplate validate`, not end users during `boilerplate new`. Implementations MUST invoke the merger during validation when `extends` dependencies are resolvable.

```text
merge_questions([{"type": "str", "default": "a"}, {"default": "b"}])
→ {"type": "str", "default": "b"}
```

**Nested structure behavior**:

```text
// Base layer:  {db: {host: "localhost", port: 5432}}
// Derived layer: {db: {host: "prod.example.com"}}
// Result:      {db: {host: "prod.example.com"}}
// Note: 'port' is GONE — the entire nested dict was replaced, not merged.
```

Template authors who need to preserve base keys in nested structures should use flat question keys (`db_host`, `db_port`) instead of nested defaults.

Used for: all user questions (non-`_` keys).

**Template authoring note**: Because `merge_questions` uses shallow merge (nested dicts are replaced wholesale by the later layer), a derived template that needs to add one key to a base template's nested default must redeclare the entire nested structure. To minimize maintenance burden when base templates evolve:

- Prefer flat question keys over deeply nested defaults (e.g., `db_host`, `db_port` instead of `db: {host: ..., port: ...}`)
- When nesting is necessary, keep nested structures small and document them as extension points in the base template
- Use Jinja2 defaults in template files rather than question defaults for values that derived templates commonly override

### Key ordering

The merged output preserves the order keys were first encountered across all configurations (left-to-right across layers).

---

## Stage 4 — RenderEngine

### Responsibility

The RenderEngine takes a `CompositionArtifact` and an `ExecutionContext` and orchestrates the actual file generation for each layer using Copier.

### Copier Worker Interface

The RenderEngine delegates actual file generation to Copier via the `run_worker` call. This interface abstracts Copier's internal API behind a stable contract owned by Boilerplate. Implementations MUST isolate all Copier API usage behind this interface so that Copier version upgrades require changes only in the worker implementation, not in the composition engine. The supported Copier version range MUST be declared in Boilerplate's package metadata and validated at startup; incompatible versions MUST fail with `BP_COPIER_COMPAT_FAILED` before any rendering begins.

**One `Worker` subclass serves compose and update.** The worker implementation MUST hand Copier the merged view through a `Worker` subclass that holds the merged questions and the merged `_jinja_extensions` union in its dataclass fields and builds `template` from those fields together with the `src_path` and `vcs_ref` Copier sets on each worker it constructs, so the old copy renders the layer's recorded source at its recorded `_commit` under the merged schema. Compose renders every layer through that subclass, and the update walk ([Safe Update](#safe-update)) runs Copier's update for every layer through it, so every worker Copier builds from it with `dataclasses.replace` — the old copy, the in-place render and the new copy of an update included — exposes the merged view ([ADR-002](adr-002-copier-internals-shim.md#decision)).

**`run_worker(source_path, destination_path, merged_config, answers, overwrite, interactive, unsafe, run_tasks)` → `WorkerResult`**

| Parameter | Type | Description |
|-----------|------|-------------|
| `source_path` | path | Path to the template directory being rendered |
| `destination_path` | path | Path to the destination project directory |
| `merged_config` | map[string, JSON] | The merged question schema for this layer |
| `answers` | map[string, JSON] | Pre-seeded answers; these override defaults and suppress prompts for matched keys |
| `overwrite` | boolean | Whether to overwrite existing files in the destination |
| `interactive` | boolean | Whether to prompt the user for unanswered questions |
| `unsafe` | boolean | Whether to allow Jinja2 extensions and task execution (required when the composition's merged `_jinja_extensions` union is non-empty, or when the layer executes tasks this invocation) |
| `run_tasks` | boolean | Whether to execute `_tasks` after rendering |

**`WorkerResult`** contains:

| Field | Type | Description |
|-------|------|-------------|
| `user_answers` | map[string, JSON] | Answers explicitly provided by the user or resolved from defaults |
| `metadata_answers` | map[string, JSON] | Copier-internal values (e.g., tool version, internal counters) |

**Behavioral contracts**:

- When `interactive=false`, the worker MUST NOT prompt; it MUST use `answers` or question defaults for all values.
- When `run_tasks=false`, the worker MUST skip task execution.
- When `unsafe=true`, Copier permits Jinja2 extensions and task execution. Because every layer's Worker holds the merged `_jinja_extensions` union (see [merge strategies](#merge-strategies)), Boilerplate MUST set `unsafe=true` on every layer's Worker whenever the composition's merged `_jinja_extensions` union is non-empty, and additionally on a layer that executes tasks this invocation ([ADR-003](adr-003-permissive-execution.md) records this permissive posture). Extension-free compositions keep `unsafe=false` on layers contributing no tasks.
- The worker MUST NOT modify `source_path` in any way.

**Assumed Copier behavior**: The `run_worker` contract assumes Copier operates synchronously and single-threaded — it blocks until rendering is complete and does not spawn background processes. If Copier's concurrency model changes in a future version, the worker interface MUST serialize invocations to preserve the sequential layer-rendering guarantee. Copier is also assumed to be non-interactive when `interactive=false` — it MUST NOT prompt on stdin.

### ExecutionContext

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `destination` | path | — | Target directory for the rendered project (required) |
| `context_data` | map[string, any] | `{}` | Pre-seeded answers passed to the first worker |
| `overwrite` | boolean | `false` | Whether to overwrite existing files in the destination |
| `interactive` | boolean | `true` | Whether to prompt the user for answers |

### Render Behavior

The RenderEngine takes the merged questions schema (no underscore-prefixed keys) and renders each layer via its own Copier `Worker` invocation against the same destination directory. The merged questionnaire is computed once across all layers' configurations so the user is prompted only once; per-layer rendering then consumes the resolved answers without re-prompting.

**Why per-layer rendering**: A single Copier invocation for a multi-template composition breaks `copier update`, which assumes "1 template = 1 Git repository". Boilerplate invokes Copier once per layer and lets each layer own its own answers file, preserving Copier's three-way update flow per layer.

**Per-layer rendering and file overlay**:

- Each layer is rendered via its own Copier `Worker` invocation against the same destination directory; the RenderEngine loops in topological order.
- Each layer produces its own `.copier-answers.<layer>.yml` — Copier renders the template's answers-file stub at the path its `_answers_file:` directive names, and both halves are required (the contract is specified at [Per-Layer Render Loop](#per-layer-render-loop) below). The per-layer answers files record the answers that per-template `copier update` operations use later, with the other layers' recorded answers passed as data (see [06-project-lifecycle.md §Step 4: Three-Way Merge](06-project-lifecycle.md#step-4-three-way-merge)).
- Layer N+1 overwrites Layer N's file collisions at the same path (file-level composition; see [Composition is file-level, not content-level](#managing-shared-files-across-layers)).
- Layer-local directives (e.g., `_exclude`, `_skip_if_exists`, `_subdirectory`) are applied per-layer from each layer's own `copier.yml`; they do not propagate across layers. One exception: `_jinja_extensions` merges by union across layers (see [merge strategies](#merge-strategies) above), so a layer's declared extensions are available to every layer's Worker. A composed render ignores every layer's `_skip_if_exists`; each layer's list governs only that layer's own `copier update` — see [Per-Layer Render Loop](#per-layer-render-loop) below.
- The `unsafe=true` flag is passed to every layer's worker whenever the composition's merged `_jinja_extensions` union is non-empty, and additionally to a layer that executes tasks this invocation (see [Copier Worker Interface](#copier-worker-interface)).
- The render operation MUST be aborted with `BP_RENDER_TIMEOUT` if the wall-clock time exceeds the configured `render_timeout` setting (default: 300 seconds). See [09-settings-and-configuration.md §Settings](09-settings-and-configuration.md#settings) for the `BOILERPLATE_RENDER_TIMEOUT` environment variable.

**Single-prompt answer reuse**:

- The merged questions schema is computed **once** from all layers' configurations before rendering begins. All questions from all layers are collected into a single questionnaire, ordered by first appearance in topological order.
- If interactive mode is enabled, the user is prompted for all questions from the merged schema in a single interactive session. Conditional visibility (`when` expressions) is evaluated during prompting. If non-interactive, defaults and pre-seeded answers are used.
- The resolved answer set is then passed to each layer's Copier `Worker` invocation as pre-seeded answers; subsequent layers do NOT re-prompt for previously-answered questions.
- **Tasks** are executed in topological order; tasks within a layer run when that layer's Copier invocation completes (Copier's per-template `_tasks` semantics).
- **Overwrite**: The `overwrite` flag is passed from the `ExecutionContext`. When rendering into an empty staging directory (the standard creation path), `overwrite` does not trigger conflicts because no files pre-exist. When `--force` is active, files are overwritten freely, including any a layer lists in its own `_skip_if_exists`. The "full-file replacement" overlay semantics described in [06-project-lifecycle.md](06-project-lifecycle.md) are achieved naturally by per-layer rendering in topological order: later layers' files replace earlier layers' files at the same path.

**Composition is file-level, not content-level.** When two layers contribute a file at the same path, the later layer's file completely replaces the earlier layer's. There is no line-by-line or AST-level merge of file contents across layers. Template authors building layered compositions should structure templates to avoid file conflicts — for example, by organizing layer-specific content into separate files, by designating a single layer as the owner of a shared file, or by using post-render `_tasks` to merge content programmatically when the format supports it.

### Managing Shared Files Across Layers

When multiple layers need to contribute to the same file (e.g., `pyproject.toml`), full-file replacement means only the last layer's version survives. Template authors SHOULD use one of these patterns:

1. **Single-owner pattern** (recommended): Designate one layer as the owner of the shared file. That layer's template renders the complete file from the merged schema, so the file MAY use any question its own layer or a parent layer declares, a parent layer being any layer its `extends` chain reaches, directly or transitively; other layers contribute their values via questions with `merge_questions` but do not include the shared file in their own template content. The owning layer MUST come, in topological order, at or after every layer that declares a question the shared file uses; the last layer of the composition always qualifies.

2. **Post-render task**: Use a `_tasks` entry in the final layer to programmatically merge content (e.g., merge TOML sections). This approach is flexible but couples the template to specific tooling. The task runs once against the finished project with the merged answers in scope ([ADR-014](adr-014-deferred-task-execution.md)).

Boilerplate does not perform content-level merging of individual files. This is a deliberate design choice: content merge semantics are format-dependent and would introduce significant complexity.

> **Note on Jinja2 cross-layer inheritance**: Because each layer is rendered by its own Copier invocation (see [Render Behavior](#render-behavior)), `{% extends %}` directives within a derived layer's templates cannot reach into a different layer's template directory. Cross-layer template inheritance via Jinja2 is NOT supported by the per-layer rendering shape; use the single-owner or post-render-task pattern instead.

### Per-Layer Render Loop

The RenderEngine iterates layers in topological order. For each layer:

1. Resolve the layer's source path (filesystem directory, or a Git working tree — the published first-party repository, an org-local clone or mirror, or, once the deferred seed cache exists, a wheel-bundle cache directory). A cache path MUST NEVER be recorded as `_src_path` in the answers file: Copier records the source it actually used, and masking a local cache path behind a canonical URL would mean rewriting Copier's own answers file, which [ADR-015](adr-015-idiomatic-artifacts.md) forbids ([ADR-006](adr-006-template-distribution.md)).
2. Invoke `run_worker` against the destination directory through the `Worker` subclass of the [Copier Worker Interface](#copier-worker-interface), with the merged schema as the questionnaire, the resolved answers as pre-seeded answers, and the layer's own `copier.yml` as the source of its layer-local directives.
3. Copier writes the rendered files into the destination directory and produces the layer's `.copier-answers.<layer>.yml` (by rendering the layer's answers-file stub at the path named by its `_answers_file:` directive).

The source template directories on disk are never modified. The destination directory is the same across all layer invocations — file collisions are resolved by overwrite (later layers win), implementing file-level composition.

**Layer-local Copier directives** — `_exclude`, `_skip_if_exists`, `_subdirectory`, `_templates_suffix`, `_envops` — are scoped to the layer that declares them in its own `copier.yml`. They do NOT propagate across layers; each layer's invocation reads them only from its own `copier.yml`. `_jinja_extensions` is merged instead — see the [merge strategies table](#merge-strategies) — so every layer's Worker receives the union of all layers' declared extensions. In a composed render no layer's `_skip_if_exists` applies: `new` writes every layer's files, and a later layer overlays this render's own output regardless of what it declares ([Composition is file-level, not content-level](#managing-shared-files-across-layers)). Each layer's declared list governs only that layer's own `copier update`.

**`_answers_file:` directive and answers-file stub (both mandatory for first-party layers)**: Each first-party template's `copier.yml` MUST declare `_answers_file: .copier-answers.<layer>.yml`, **and** the template MUST ship an answers-file stub — a template file literally named `{{ _copier_conf.answers_file }}.jinja` rendering `_copier_answers` (the `project` template's stub is the reference pattern). The directive alone is inert: Copier writes an answers file only by rendering the stub; a template lacking one composes cleanly but silently produces no answers file, exit 0, no warning — verified against Copier 9.15.0 ([ADR-015 §Verification](adr-015-idiomatic-artifacts.md#verification-2026-07-28)). Together they are the contract that makes per-layer `copier update -a .copier-answers.<layer>.yml` work at update time (see [06-project-lifecycle.md §Step 4: Three-Way Merge](06-project-lifecycle.md#step-4-three-way-merge)). `validate` SHOULD warn when a template declares `extends` or is offered for composition without a stub, since such a layer is copy-only.

Implementations MUST:

1. Isolate all Copier API usage behind the `CopierWorker` interface (see [Copier Worker Interface](#copier-worker-interface)).
2. Include integration tests that verify the per-layer render loop produces the correct destination tree against the declared Copier version.
3. Treat Copier version upgrades as requiring explicit validation, not automatic adoption.

### Error Handling

If staging directory creation fails, Boilerplate MUST emit `BP_RENDER_STAGING_FAILED` with the specific error. If a per-layer Copier invocation fails, Boilerplate MUST emit `BP_RENDER_TEMPLATE_FAILURE` with the specific error and the layer name. The `doctor` command SHOULD verify that the process has write access to the system temp directory before rendering is attempted.

The supported Copier version range MUST be declared in Boilerplate's package metadata and documented in the CLI `--version` output.

### Task Execution Order

> **See also**: [03-template-system.md §Task Execution Safety](03-template-system.md#task-execution-safety) for trust-level controls and confirmation behavior.

Task execution is deferred: every layer renders with task execution suppressed, and the full accumulated task list runs exactly once, as part of the final layer's `Worker` invocation, after the composed project's files are complete ([ADR-014](adr-014-deferred-task-execution.md)). Deferral preserves Copier's contract — tasks run against a generated project — when the project is the composed whole; running a base layer's tasks mid-composition would execute them against files later layers have not finished writing. The accumulated list preserves **topological order** across layers (dependencies first, root template last) and declaration order within each layer, so the effective order is the same one per-layer execution would produce. Entries keep Copier's native shapes end-to-end (string = shell, argv list = no shell, mapping = `command` with optional `when`/`working_directory`); conditions evaluate against the merged answers in the final layer's context.

**Example**: Given `app` extends `[base, middleware]`:

```text
base/copier.yml:        _tasks: ["echo base-setup"]
middleware/copier.yml:   _tasks: ["echo middleware-init", "echo middleware-check"]
app/copier.yml:          _tasks: ["echo app-finalize"]

Execution order:
1. echo base-setup          (from base)
2. echo middleware-init      (from middleware)
3. echo middleware-check     (from middleware)
4. echo app-finalize         (from app)
```

This ordering guarantees that infrastructure tasks (base) run before application tasks (derived), which is the natural dependency order.

### Return value

After all layers complete, return a `TemplateInfo` describing the final layer (the root template). If the final layer's metadata cannot be loaded, Boilerplate MUST fail with `BP_RENDER_METADATA_FAILED` — a synthetic `"0.0.0"` version MUST NOT be silently coined.

---

## Safe Update

The `boilerplate update` pipeline does not re-render the old composition itself. Three-way merge for each layer is performed by Copier's per-template `update` mechanism, which reconstructs that layer's base internally from the template's Git history. Boilerplate's role is to orchestrate Copier's `update` per layer in topological order and to manage the cross-layer rollback envelope. `copier update -a .copier-answers.<layer>.yml` names that per-layer operation throughout the design docs; the walk performs it through the same `Worker` subclass compose uses ([Copier Worker Interface](#copier-worker-interface); [ADR-002](adr-002-copier-internals-shim.md#decision)) so the merged schema reaches every render, and a hand-run invocation of that command is the escape hatch ([ADR-015](adr-015-idiomatic-artifacts.md#decision)).

The walk MUST build the merged schema once, before the first layer's update, from the target versions of all layers' `copier.yml` files, and MUST hand that one schema to every render Copier makes for every layer during the update: the old copy, rendered at the `_commit` the layer's answers file records and `boilerplate.lock` mirrors; the in-place render that writes the layer's files and its answers file; and the new copy, rendered at the target version. Copier renders the old copy from the layer's own answers file, never from data the walk passes. A question the target version removes therefore still renders in the old copy from the answer the file recorded while the question existed, so the old copy renders the same as it did when the answer was recorded. The walk passes the other layers' recorded answers as data for the in-place render and the new copy only. Copier ranks passed data above the layer's own answers file, so which value wins when two answers files disagree, and whether a passed value may override the layer's own recorded answer, is an open decision this design does not make. A renamed question is a removal plus an addition; carrying the recorded value to the new name is the template's own job, through Copier `_migrations`.

A layer's answers file therefore records the full merged answer set after every update, and a layer's files MAY use any question its own layer or a parent layer declares.

See [06-project-lifecycle.md](06-project-lifecycle.md) for the full update workflow, including Copier version management and non-git source fallback.

---

## Composition Inspection

The `CompositionArtifact` supports several inspection operations for the CLI `compose` command.

### Sections

| Section | Content |
|---------|---------|
| `final` | The fully merged Copier configuration (questions + directives) |
| `layers` | Per-layer question values (contributions only, not cumulative) |
| `states` | Per-layer cumulative state (requires `include_states=true` at compose time) |
| `deltas` | Per-layer delta from previous state (requires `include_deltas=true`) |
| `stats` | Aggregate statistics (see `CompositionStats` in [02-data-models.md](02-data-models.md)) |

**Question provenance**: When `--questions` mode is active, each question in the output SHOULD include a `source` field indicating which template layer originally declared it and whether it was overridden by a later layer. This enables template authors to trace question origins and identify unintentional overrides.

Example (`--questions --format json`):

```json
{
  "questions": [
    {
      "name": "project_name",
      "type": "str",
      "default": null,
      "source": "project@2.1.0",
      "overridden_by": null
    },
    {
      "name": "dependencies",
      "type": "json",
      "default": ["streamlit", "pydantic>=2"],
      "source": "project@2.1.0",
      "overridden_by": "streamlit@1.0.0"
    }
  ]
}
```

**Question ordering in `--questions` mode**: The question table MUST be output in the same order as the interactive prompting sequence — topological order (base templates first, root template last), preserving declaration order within each template. This ensures that an answer preset file built from `--questions` output maps directly to the prompting experience.

Both YAML and JSON export formats are supported. When `--output <dir>` is specified, sections are written to the directory; otherwise they are rendered to stdout. File naming within the output directory is implementation-defined.

---

## Error Reference

Composition-related errors use the `BP_RESOLVE_*`, `BP_GRAPH_*`, `BP_RENDER_*`, and `BP_LOCK_*` code families. See [07-operational-quality.md](07-operational-quality.md) for the authoritative error code registry and [02-data-models.md §Error Hierarchy](02-data-models.md#error-hierarchy) for the exception class hierarchy.

---

## Invariants

1. Every specifier in `sequence` MUST appear in `nodes`, `edges`, and `layers`.
2. `sequence` MUST be in dependency-first order: for any edge `A → B`, `B` MUST appear before `A`.
3. `final` MUST be the result of merging ALL layer configurations; no layer is skipped.
4. `merged_questions_schema` MUST contain no underscore-prefixed keys.
5. The accumulated `_tasks` list MUST run exactly once, as part of the final layer's Copier invocation, after all layers' files are rendered; non-final layers MUST render with task execution suppressed. The list preserves topological order across layers and declaration order within each layer (see [ADR-014](adr-014-deferred-task-execution.md)).
6. All questions from all layers MUST be collected into a single questionnaire and prompted once; no re-prompting occurs across per-layer Copier invocations.
7. Version resolution MUST be deterministic: identical inputs (catalog state, version constraints, source `priority` ordering) MUST produce identical resolved versions. The resolver MUST NOT consult the system clock, random number generators, or environment variables that vary between invocations.
8. Once `DependencyGraphBuilder` returns a graph, its `nodes`, `edges`, and `sequence` MUST NOT be mutated. Stages downstream of the resolver consume the graph as a read-only structure; this guarantees the resolution space is reproducible.
