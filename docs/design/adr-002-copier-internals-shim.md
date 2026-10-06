# ADR-002: Depend on Copier's internal Template/Worker via a single audited shim

**Status**: Accepted (retroactively documented 2026-06-09) **Date**: 2026-06-07 (centralized into the shim; the underlying dependency on Copier internals predates it); revised 2026-09-30 **Deciders**: Project team

## Context

Copier does not expose `Template` or `Worker` in its public API (`copier.__all__` is `load_settings, run_copy, run_recopy, run_update, Phase, Settings, VcsRef`). Boilerplate's composition engine is built on these internal classes: `MergedTemplate` subclasses `Template` to present the consolidated question schema, and `RenderEngine` drives a `Worker` directly (injecting the merged template via `object.__setattr__`) rather than calling Copier's public `run_copy`/`run_update`. These are private symbols Copier may relocate without a deprecation cycle.

## Decision

Funnel all coupling to Copier internals through one module, `src/boilerplate/integrations/copier_types.py`, importing from the modules where Copier actually defines them (`copier._main.Worker`, `copier._template.Template`), and pin Copier to a tested range (`copier>=9.15,<10` in `pyproject.toml`). A relocation of these symbols then breaks one file, loudly, via the guard test (`tests/boilerplate/integrations/test_copier_types.py`) during CI rather than at render time for a user.

**The shim serves compose and update.** The update path imports `Worker` from `copier_types.py`, subclasses it, and hands each layer's instance the merged schema, the same view compose hands each layer. `boilerplate update` runs Copier's update once per layer, and every use of Copier internals on that path MUST go through the shim.

**The merged view lives in fields of a `Worker` subclass**, and the subclass's `template` property builds the merged template from those fields. Copier's update builds its three renders (the old copy, the in-place render and the new copy) with `dataclasses.replace`, which constructs each new worker from dataclass fields. A template primed on a worker instance with `object.__setattr__` reaches none of the three renders; `replace` copies a view held in fields into all of them.

A relocation of `Worker` or `Template` inside Copier breaks compose and update in `copier_types.py` alone, where the guard test reports it, and the `copier>=9.15,<10` pin bounds the Copier versions both paths run on. A test MUST drive one per-layer update through the subclass, since a symbol check does not see the `dataclasses.replace` contract the update walk depends on.

## Options considered

- **Scattered `from copier import …` across the codebase** — every upgrade break surfaces in many files, and the top-level import path emits a deprecation warning.
- **Reimplement Copier's render/merge** — large, duplicates Copier, contradicts ADR-001.
- **Vendor/fork Copier** — maintenance burden out of proportion to the need.
- **Single audited import shim + version pin** (chosen) — one change point on upgrade; the deep `_main`/`_template` paths avoid the deprecation warning.
- **A merged template primed on the worker instance** — rejected for the update path: `dataclasses.replace` rebuilds the update renders without it ([Verification (2026-09-30)](#verification-2026-09-30)).

## Consequences

- One file changes when Copier relocates these symbols; the import stays warning-free; ruff + pyright-strict clean.
- Coupled to a private API: every Copier upgrade must be re-validated against the shim's guard test and the per-layer update test.
- The `>=9.15` floor is pragmatic, not a verification gap: 9.15 is the version in use and tested, and we deliberately do not support or look further back (possibly ever). The `<10` cap forces re-validation at Copier's next major.
- **Re-architecture:** this decision stands until the Copier integration is re-architected (e.g., adopting the evaluated file-based merged-template approach); this ADR is then rewritten in place.

## Verification (2026-06-09)

`copier_types.py` is the only site importing Copier internals (grep); `MergedTemplate` subclasses the shim's `Template` (`composition/rendering/models/merged_template.py:14`); `RenderEngine` injects it into `Worker` (`composition/rendering/engine.py:256-259`); the guard test is present.

## Verification (2026-09-30)

Empirical run against the bundled `project` and `streamlit` templates (Copier 9.18.1, Windows, local git clones, `--defaults`, `skip_tasks`): both layers cloned into tagged git repositories, a project composed by `boilerplate new` and rehomed to the clones. Each new tag edited the README line that renders `project_name` and appended a file rendering seven inherited answers; a user line appended to the README before the first update had to survive.

| Mechanism | Orders | Result |
|---|---|---|
| A `Worker` subclass holding the merged questions and the extension union in fields, `template` built from them; `Worker.run_update()` called on the subclass instance per layer with the union of the per-layer answers files as `data` | `project` then `streamlit`, and `streamlit` then `project`; v2 then v3 | All 8 updates exit 0, with no conflict markers, no `.rej` files and no unmerged paths; the five inherited answers that Copier records persist in `streamlit`'s answers file after every update; the two derived values render (`widget_co`, `widget-co`); the package directory and the user line survive |
| `worker.template` primed with the merged template on the instance | Both orders | The first `streamlit` update exits 0 but its answers file loses the five inherited answers and the derived values render empty; the second update pauses with conflict markers in `README.md` and the probe file |

## Relationship to other ADRs

- [ADR-001](adr-001-build-vs-adopt.md) records the *decision to adopt Copier*. This ADR records the *mechanism* of that integration: Boilerplate depends on Copier's internal `Worker` and `Template` through the shim. A file-based merged-template approach that would avoid the internal dependency was evaluated and not adopted.
- [ADR-015](adr-015-idiomatic-artifacts.md) — the update walk this shim serves: every render of every layer's update sees the merged schema.
