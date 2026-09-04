# ADR-002: Depend on Copier's internal Template/Worker via a single audited shim

**Status**: Accepted (retroactively documented 2026-06-09) **Date**: 2026-06-07 (centralized into the shim); the underlying dependency on Copier internals predates it **Deciders**: Project team

## Context

Copier does not expose `Template` or `Worker` in its public API (`copier.__all__` is `load_settings, run_copy, run_recopy, run_update, Phase, Settings, VcsRef`). Boilerplate's composition engine is built on these internal classes: `MergedTemplate` subclasses `Template` to present the consolidated question schema, and `RenderEngine` drives a `Worker` directly (injecting the merged template via `object.__setattr__`) rather than calling Copier's public `run_copy`/`run_update`. These are private symbols Copier may relocate without a deprecation cycle.

## Decision

Funnel all coupling to Copier internals through one module, `src/boilerplate/integrations/copier_types.py`, importing from the modules where Copier actually defines them (`copier._main.Worker`, `copier._template.Template`), and pin Copier to a tested range (`copier>=9.15,<10` in `pyproject.toml`). A relocation of these symbols then breaks one file, loudly, via the guard test (`tests/boilerplate/integrations/test_copier_types.py`) during CI rather than at render time for a user.

## Options considered

- **Scattered `from copier import …` across the codebase** (the prior state) — every upgrade break surfaces in many files, and the top-level import path emits a deprecation warning.
- **Reimplement Copier's render/merge** — large, duplicates Copier, contradicts ADR-001.
- **Vendor/fork Copier** — maintenance burden out of proportion to the need.
- **Single audited import shim + version pin** (chosen) — one change point on upgrade; the deep `_main`/`_template` paths avoid the deprecation warning.

## Consequences

- One file changes when Copier relocates these symbols; the import stays warning-free; ruff + pyright-strict clean.
- Coupled to a private API: every Copier upgrade must be re-validated against the shim's guard test.
- The `>=9.15` floor is pragmatic, not a verification gap: 9.15 is the version in use and tested, and we deliberately do not support or look further back (possibly ever). The `<10` cap forces re-validation at Copier's next major.
- **Supersession:** this decision stands until the Copier integration is re-architected (e.g., adopting the evaluated file-based merged-template approach); a new ADR would record that.

## Verification (2026-06-09)

`copier_types.py` is the only site importing Copier internals (grep); `MergedTemplate` subclasses the shim's `Template` (`composition/rendering/models/merged_template.py:14`); `RenderEngine` injects it into `Worker` (`composition/rendering/engine.py:256-259`); the guard test is present.

## Relationship to ADR-001

[ADR-001](adr-001-build-vs-adopt.md) records the *decision to adopt Copier*. This ADR records the *mechanism* of that integration, and supersedes ADR-001's earlier (inaccurate) claim that a file-based merged-template approach had eliminated the internal dependency — it had not; the in-memory Worker-injection described here is the as-built path.

## Amendment (2026-07-28)

[ADR-015](adr-015-idiomatic-artifacts.md) narrows this shim's charter: it is sanctioned only for the compose-time merged question flow described above. The update path (`boilerplate update`) MUST stay on Copier's public API (`run_update` via per-layer `copier update` invocations) and MUST NOT touch `copier_types.py` or the internals it wraps — see [ADR-015 point 2](adr-015-idiomatic-artifacts.md).
