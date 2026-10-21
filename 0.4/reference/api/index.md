# API reference

Auto-generated reference for the public API of the `boilerplate`, `boilerplate.cli`, `boilerplate.composition`, `boilerplate.repository`, and `boilerplate.models` packages.

Boilerplate: a Python development environment paired with layered templates.

Boilerplate pairs a Python development environment, one tool for each job, with templates that build on one another to stamp out projects. Built on Copier.

## Core modules

### CLI

Initializes the Boilerplate CLI package.

Exposes the single Typer application instance.

### Composition

Composition feature package.

Authoritative implementation for dependency resolution and composition.

## `Composer`

Layers and merges template configurations - domain operation.

### `compose(resolution, *, include_states=False, include_deltas=False)`

Compose resolved templates into an ordered, layered Composition.

Walks `resolution.execution_sequence`, extracts each template's complete copier config, and merges cumulatively: later layers override question values; coordination keys (`_tasks`, `_secret_questions`, `_jinja_extensions`, `_min_copier_version`) merge per `CopierConfigMerger`; layer-local underscore keys are dropped from `final` but kept in their own layer's `values`. Sequence entries missing from `resolution.templates` are skipped. Pure computation — no I/O, no rendering.

Parameters:

| Name             | Type         | Description                                                                                                                                                                  | Default    |
| ---------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| `resolution`     | `Resolution` | Resolved template set with a dependency-ordered execution_sequence.                                                                                                          | *required* |
| `include_states` | `bool`       | Populate CompositionLayer.state_after with the full merged state after each layer.                                                                                           | `False`    |
| `include_deltas` | `bool`       | Populate CompositionLayer.delta with changes versus the previous layer's state (always a dict, {} when unchanged; \_tasks never appears — it is excluded from layer values). | `False`    |

Returns:

| Type          | Description                                                                                                                                                                       |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Composition` | Dependency graph, execution sequence, per-layer values (cumulative questions plus that layer's own directives, \_tasks excluded), and the final merged schema used for rendering. |

## `Resolver`

Resolves template dependencies from a catalog.

Methods in this class are pure with respect to inputs and the provided registry; no side effects beyond logging. Resolution walks the `meta.extends` chain, validates references exist in the registry, and returns a complete mapping of template specifiers to their direct dependency specifiers along with a map of specifier to TemplateInfo.

Contract:

- Input `template_ref` may be `name` or `name@version`.
- Registry must implement lookups for both latest and versioned resolution.
- No cycle detection is performed here (handled by the graph layer).
- Dependency lists preserve the order specified in `meta.extends`.

### `resolve(template_ref, registry)`

Resolve a template reference into a complete dependency map and templates.

Parameters:

| Name           | Type              | Description                                               | Default    |
| -------------- | ----------------- | --------------------------------------------------------- | ---------- |
| `template_ref` | `str`             | Template identifier (e.g., name or name@version).         | *required* |
| `registry`     | `TemplateCatalog` | Catalog used to resolve templates and their dependencies. | *required* |

Returns:

| Type         | Description                                                 |
| ------------ | ----------------------------------------------------------- |
| `Resolution` | Frozen model containing the dependency map (by specifier    |
| `Resolution` | string) and a templates map from specifier to TemplateInfo. |

Raises:

| Type                            | Description                                                                                                               |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `DependencyNotFoundError`       | If any referenced template cannot be found.                                                                               |
| `InvalidTemplateSpecifierError` | If any extends reference is a malformed name@version string.                                                              |
| `VersionConflictError`          | If the same template name resolves to two different versions in the graph (diamond dependency with version disagreement). |

### Repository

Template repository implementations for Boilerplate.

## `DirectoryTemplateRepository`

Bases: `TemplateRepository`

Directory-based template repository implementing TemplateRepository.

Scans the specified directory for templates, validates their metadata, and loads them for use by coordinators such as TemplateCatalog.

Limitations

- Only one version per template name is supported at a time.
- Overwriting a template directory replaces the previous version.

### `load_templates()`

Return the templates discovered when this repository was constructed.

Discovery runs once, in `__init__`; this method only hands back the result, so repeated calls cost nothing and see no filesystem changes.

Returns:

| Type                 | Description              |
| -------------------- | ------------------------ |
| `list[TemplateInfo]` | All available templates. |

## `TemplateRepository`

Bases: `ABC`

Defines the abstract interface for template repositories.

Template repositories discover templates from a source (e.g., a directory, a Git remote) and load them for use by coordinators such as TemplateCatalog.

### `load_templates()`

Load all available templates from this repository.

Returns:

| Type                 | Description              |
| -------------------- | ------------------------ |
| `list[TemplateInfo]` | All available templates. |

### Models

Template data models and metadata for Boilerplate.

## `LOCK_SCHEMA_MAJOR = 1`

The lock schema major this tool reads and writes.

## `LOCK_SCHEMA_VERSION = f'boilerplate/lock@{LOCK_SCHEMA_MAJOR}'`

The schema identifier this tool writes: `namespace/schema@major`.

## `BoilerplateLock`

Bases: `BaseModel`

The lock Boilerplate writes into a project root after each operation.

The lock records the last complete operation, so its layer versions match what each layer's files were last rendered against. Fields a later minor schema adds are ignored on read.

Attributes:

| Name                         | Type                    | Description                                                               |
| ---------------------------- | ----------------------- | ------------------------------------------------------------------------- |
| `schema_version`             | `str`                   | The namespaced schema identifier; any minor of the supported major.       |
| `boilerplate_version`        | `str`                   | The version of the tool that wrote the file.                              |
| `copier_version`             | `str`                   | The version of Copier used for rendering.                                 |
| `created_at`                 | `AwareDatetime`         | When the project was created (UTC).                                       |
| `updated_at`                 | `AwareDatetime`         | When the lock was last written (UTC).                                     |
| `root_template`              | `str`                   | The specifier of the template that created the project.                   |
| `copier_answers_file_hashes` | \`Mapping[str, str]     | None\`                                                                    |
| `layers`                     | `tuple[LockLayer, ...]` | One entry per template layer, in execution order; at least one, the root. |

### `root_name`

The name of the root template, which `add` never changes.

## `ChangeClassification`

Bases: `StrEnum`

The size of an update, the highest bump across its layers.

## `JoinedVia`

Bases: `StrEnum`

The way a layer entered the project the lock describes.

`EXTENDS` covers the root template and every layer its `extends` closure reaches. `ADD` is a layer `boilerplate add` introduced, which the root's target version does not govern.

## `LockLayer`

Bases: `BaseModel`

What the lock records about one template layer's last complete render.

Fields a later minor schema adds are ignored on read, because Boilerplate parses any lock of the supported major.

Attributes:

| Name              | Type                  | Description                                                                              |
| ----------------- | --------------------- | ---------------------------------------------------------------------------------------- |
| `name`            | `str`                 | The template name.                                                                       |
| `version`         | `SerializableVersion` | The exact version rendered.                                                              |
| `joined_via`      | `JoinedVia`           | How the layer joined the project; a lock that omits the field reads as extends.          |
| `source`          | `str`                 | The URI or filesystem path of the template.                                              |
| `commit`          | \`str                 | None\`                                                                                   |
| `checksum`        | `str`                 | The digest of the template source directory, prefixed with its algorithm (sha256:<hex>). |
| `subdirectory`    | \`str                 | None\`                                                                                   |
| `source_bundle`   | \`str                 | None\`                                                                                   |
| `trust_tier`      | \`str                 | None\`                                                                                   |
| `bundle_uri`      | \`str                 | None\`                                                                                   |
| `bundle_checksum` | \`str                 | None\`                                                                                   |

## `MigrationRecord`

Bases: `BaseModel`

One operation Boilerplate recorded: its versions, outcome and, if paused, plan.

A `conflict` record is what a paused update resumes from: `targets` names the version the walk was updating each layer to, and `finished` the layers whose steps the walk completed.

Attributes:

| Name             | Type                   | Description                                                                                      |
| ---------------- | ---------------------- | ------------------------------------------------------------------------------------------------ |
| `id`             | `str`                  | A positive integer, sequential from "1", stored as a string.                                     |
| `from_version`   | \`str                  | None\`                                                                                           |
| `to_version`     | `str`                  | The root template specifier after the operation; for an add record, the added layer's specifier. |
| `timestamp`      | `AwareDatetime`        | When the record was written (UTC).                                                               |
| `status`         | `MigrationStatus`      | How the operation stands.                                                                        |
| `error`          | \`str                  | None\`                                                                                           |
| `classification` | \`ChangeClassification | None\`                                                                                           |
| `targets`        | \`Mapping[str, str]    | None\`                                                                                           |
| `finished`       | \`tuple[str, ...]      | None\`                                                                                           |

## `MigrationStatus`

Bases: `StrEnum`

How an operation recorded in `.boilerplate/migrations.yml` stands.

Each record is appended once, when its operation ends; the state of a run cut off before then is kept in the restore marker, not in the log. Exit codes: `SUCCESS`, `ADOPTED` and `CREATED` are 0, `CONFLICT` is 4 and `FAILED` is 1.

## `RestoreKind`

Bases: `StrEnum`

What the copy back of a marked run brings into the checkout.

Attributes:

| Name       | Type | Description                                                    |
| ---------- | ---- | -------------------------------------------------------------- |
| `COMPLETE` |      | A walk that finished every layer.                              |
| `PAUSED`   |      | A walk a conflict paused; it runs no tasks and writes no lock. |

## `RestoreMarker`

Bases: `BaseModel`

What a run cut off between its copy back and its record needs to be finished.

The marker is written before the copy back changes a file and removed after the run appends its record, so a marker found when a command starts belongs to a run that was cut off in between. It lives in the git directory, apart from the staging folder that the stale cleanup removes.

Attributes:

| Name            | Type                | Description                                                                                                               |
| --------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `operation`     | `RestoreOperation`  | The command the run belongs to.                                                                                           |
| `kind`          | `RestoreKind`       | Whether the walk finished every layer or a conflict paused it.                                                            |
| `phase`         | `RestorePhase`      | How far the run got after its walk.                                                                                       |
| `start_commit`  | `str`               | The commit HEAD pointed at when the run began, a full object id.                                                          |
| `result_commit` | `str`               | The staging worktree's last per-layer commit, the start commit when no layer finished; a full object id.                  |
| `targets`       | `Mapping[str, str]` | Each layer of the walk, in walk order, with the version the walk was moving it to; never empty, and one layer for an add. |
| `finished`      | `tuple[str, ...]`   | The layers whose steps a paused walk finished, in walk order, the paused layer excluded; empty for a complete run.        |
| `paused_layer`  | \`str               | None\`                                                                                                                    |
| `started_at`    | `AwareDatetime`     | When the run began.                                                                                                       |

### `at_phase(phase)`

Return this marker moved on to `phase`.

Parameters:

| Name    | Type           | Description                   | Default    |
| ------- | -------------- | ----------------------------- | ---------- |
| `phase` | `RestorePhase` | The step the run has reached. | *required* |

Returns:

| Type   | Description                                    |
| ------ | ---------------------------------------------- |
| `Self` | A copy with phase, checked as a new marker is. |

Raises:

| Type              | Description                         |
| ----------------- | ----------------------------------- |
| `ValidationError` | If phase is tasks for a paused run. |

## `RestoreOperation`

Bases: `StrEnum`

The command whose copy back a restore marker brackets.

Each value is the command's name, so a stop can name the command to rerun.

## `RestorePhase`

Bases: `StrEnum`

The step a run that wrote a restore marker is in.

Attributes:

| Name        | Type | Description                                                     |
| ----------- | ---- | --------------------------------------------------------------- |
| `COPY_BACK` |      | From the moment the marker is written until the copy back ends. |
| `TASKS`     |      | While a complete update's or add's tasks run.                   |
| `RECORDING` |      | Until the record is appended; the lock and the record remain.   |

## `TemplateInfo`

Bases: `BaseModel`

Holds the resolved metadata, name, and location of a discovered template.

Attributes:

| Name              | Type                | Description                                                   |
| ----------------- | ------------------- | ------------------------------------------------------------- |
| `name`            | `str`               | The unique name of the template (usually the directory name). |
| `meta`            | `TemplateMeta`      | Parsed metadata from the template's config file.              |
| `location`        | `Path`              | Filesystem path to the root of the template.                  |
| `copier_template` | `Template`          | The Copier template instance for this template.               |
| `specifier`       | `TemplateSpecifier` | Computed template specifier combining name and version.       |

### `specifier`

Gets the template specifier for this template.

Returns:

| Type                | Description                                          |
| ------------------- | ---------------------------------------------------- |
| `TemplateSpecifier` | A specifier combining the template name and version. |

Examples:

```pycon
>>> # Assuming template_info is a TemplateInfo instance
>>> # template_info.specifier
>>> # TemplateSpecifier(name='mytemplate', version='1.2.3')
>>> from boilerplate.types.template_specifier import TemplateSpecifier
>>> specifier = TemplateSpecifier("example", "1.0.0")
>>> str(specifier)
'example@1.0.0'
```

## `TemplateMeta`

Bases: `BaseModel`

Metadata for a single Copier template.

Attributes:

| Name             | Type                  | Description                                          |
| ---------------- | --------------------- | ---------------------------------------------------- |
| `schema_version` | `SerializableVersion` | The version of the boilerplate.yml schema.           |
| `name`           | `str`                 | Logical name of the template (e.g., "project").      |
| `description`    | `str`                 | Short human-readable description of the template.    |
| `version`        | `Version`             | Semantic version of the template itself.             |
| `extends`        | `list[str]`           | Names of parent templates this template builds upon. |

### `serialize_version(value, _info)`

Serialize the version as a string for YAML output.

Parameters:

| Name    | Type      | Description                        | Default    |
| ------- | --------- | ---------------------------------- | ---------- |
| `value` | `Version` | The Version instance to serialize. | *required* |
| `_info` | `object`  | Additional context, not used here. | *required* |

Returns:

| Type  | Description              |
| ----- | ------------------------ |
| `str` | The version as a string. |

### `coerce_version(value)`

Coerce raw version-like input to a SerializableVersion.

Parameters:

| Name    | Type     | Description                 | Default    |
| ------- | -------- | --------------------------- | ---------- |
| `value` | `object` | The input value to convert. | *required* |

Returns:

| Type                  | Description                               |
| --------------------- | ----------------------------------------- |
| `SerializableVersion` | A validated SerializableVersion instance. |

Examples:

```pycon
>>> TemplateMeta.coerce_version("1.2.3")
SerializableVersion('1.2.3')
```

### `load(path)`

Load metadata from a boilerplate.yml file or directory containing one.

Parameters:

| Name   | Type   | Description                                                          | Default    |
| ------ | ------ | -------------------------------------------------------------------- | ---------- |
| `path` | `Path` | Path to either a boilerplate.yml file or a directory containing one. | *required* |

Returns:

| Type   | Description                             |
| ------ | --------------------------------------- |
| `Self` | Parsed and validated metadata instance. |

Raises:

| Type                | Description                                  |
| ------------------- | -------------------------------------------- |
| `FileNotFoundError` | If boilerplate.yml does not exist.           |
| `ValidationError`   | If required fields are missing or malformed. |

### `dump(path, *, overwrite=False)`

Serialize the model to a YAML file.

Parameters:

| Name        | Type   | Description                                                    | Default    |
| ----------- | ------ | -------------------------------------------------------------- | ---------- |
| `path`      | `Path` | Path to write the YAML file.                                   | *required* |
| `overwrite` | `bool` | Whether to overwrite the file if it exists. Defaults to False. | `False`    |

Raises:

| Type              | Description                                |
| ----------------- | ------------------------------------------ |
| `FileExistsError` | If the file exists and overwrite is False. |

## Where next

- [Merging and precedence rules](https://therealbillsiegler.github.io/boilerplate/0.4/reference/merging/index.md) — what the composition classes produce.
- [Commands](https://therealbillsiegler.github.io/boilerplate/0.4/cli/index.md) — the CLI built on them.
