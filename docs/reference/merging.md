# Merging and precedence rules

!!! note "Authoritative specification"
    The authoritative design specification for merge strategies and composition is [04-composition-engine.md](../design/04-composition-engine.md). This page provides supplementary implementation-level reference. For the file-level three-way merge, conflict-pause, and safe-orphan semantics designed for the future `update` command, see [ADR-007](../design/adr-007-update-model.md).

How configuration values are combined across template layers, with clear rules and deterministic outcomes.

## A two-layer merge

A base template and an app template that extends it, each with its own `copier.yml`:

```yaml
# base template — copier.yml
python_version:
    default: "3.12"
license:
    default: "Apache-2.0"
_tasks:
    - "uv sync"
```

```yaml
# app template — copier.yml (its boilerplate.yml declares extends: [base])
python_version:
    default: "3.13"
_tasks:
    - "git init"
```

Composing the app template produces a single questionnaire: `python_version` defaults to `3.13` (the later layer overrides), `license` survives from the base, and `_tasks` accumulates to `["uv sync", "git init"]`. The rules below generalize this.

## What gets merged

`boilerplate new` asks the merged questionnaire once, over every layer's questions, and a question default can use a filter from any layer's `_jinja_extensions`. Each layer then renders through its own Copier `Worker` invocation, applied in composition order, under its scoped view: the questions and importable `_jinja_extensions` of that layer and its ancestors, answered from that one pass. A layer's files and questions can use only what its own layer or an ancestor declares; a sibling's or a descendant's questions, filters and hooks are not visible to it. A file-path extension an ancestor declares (`_extensions/file.py:Class`) loads from that ancestor for each descendant that renders, and a layer's `.copier-answers.<layer>.yml` records its scoped view's answers only.

- Non-underscore keys (questions): merged across layers to form a single questionnaire.
    - dicts: later layer keys override earlier ones (shallow override).
    - lists: de-duplicated concat in order (first-seen wins).
    - scalars: later value overrides earlier value.

- Underscore-prefixed keys (directives): not merged, except a small allowlist below. All other underscore keys are treated as layer-local and skipped.

## File overlay

Each layer renders into the same destination through its own Copier `Worker` invocation, in composition order. Only the first layer's write respects `--force`; every later layer always overwrites, so a file that two layers both ship at the same path ends up with the last layer's content — there is no three-way diff or per-line merge. A layer that adds files at new paths never touches an earlier layer's files. `boilerplate new` ignores every template's `_skip_if_exists` list, so `new --force` overwrites every file; the lists protect project-owned files only during `copier update`.

## Allowlisted directive keys and strategies

- `_min_copier_version`: highest PEP 440 version (intersection by max).
- `_tasks`: accumulate in order (lists concatenate, scalars append).
- `_secret_questions`: accumulate in order.
- `_jinja_extensions`: union with original order preserved (dedupe).

Everything else starting with `_` is layer-local. These are discovered dynamically from `copier.Template` attributes at runtime and excluded from merging.

## Determinism and conflict handling

- Key order: keys are processed in first-seen order across layers.
- Type safety: incompatible types for the same question raise a merge conflict.

## Debugging merges

Run `boilerplate compose <template> --sections layers,deltas` to see each layer's contribution and what changed between them.
