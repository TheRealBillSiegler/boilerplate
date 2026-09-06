# ADR-008: Distribution name — publish as `boilerplate-cli`, keep `boilerplate` as the command and brand

**Status**: Pending — the default decision below stands *unless* the current PyPI `boilerplate` owner agrees to surrender the name. A voluntary-transfer request to the incumbent is outstanding; [PEP 541](https://peps.python.org/pep-0541/) is the fallback escalation. This ADR **must** resolve to Accepted before the **first PyPI publish**, because a PyPI distribution name is effectively immutable once published. It does **not** gate the git-URL-first launch (`uv tool install git+https://github.com/TheRealBillSiegler/boilerplate.git`) or the first public tag, which publish no wheel.

**Date**: 2026-06-22 **Deciders**: Project team (Bill Siegler)

> **Scope note.** This is a packaging / go-public decision, not an architecture one. It gates INT-007 (PyPI installability) and INT-010 (publish pipeline), both in the [intentions register](../intentions/README.md) — the PyPI path only; it does **not** gate the git-URL-first launch, which consumes no PyPI distribution name. It does not touch the import package, the CLI surface, or any persisted schema.

## Context

The PyPI distribution name `boilerplate` is **already taken** by an unrelated package — Kuba Janoszek's *"Easy to use tool for painless project layout templating"* (latest `1.2.4`, 6 releases). That is not a bare name collision: it is the **same niche** (project templating) and it is already at `1.x` while this project is at `0.2.0`. A `pip install`-ed wheel needs a unique PyPI name, so the project cannot publish under `boilerplate`.

Everything else in the project — the import package (`src/boilerplate/`), the CLI command (`boilerplate new`), the repository, the docs, and the brand — uses `boilerplate`, and the maintainer values the name: it is *self-referential* (a tool that emits boilerplate, named Boilerplate), a wink that fires on contact with no jargon. An exploration of replacement names (four rounds, ~220 candidate-evaluations) found **no free standalone name that reproduces that wink**: the wink-firing words (`plate`, `boil`, `boiler`, `chase`, `forme`, `stamp`) are all taken precisely because they are common, and the free survivors are either footnote-jokes (`potboiler`, `stetlock`) or flat descriptions (`roughcut`). Verified free as of 2026-06-20: `boilerplate-cli` on both PyPI and GitHub.

**Mis-install hazard (the load-bearing risk).** `pip install boilerplate` does not fail — it silently installs the *other, same-niche* package. A user who guesses the obvious command gets someone else's project. This is worse than a dead name; it is an active mis-install trap, and it is the primary reason to pursue acquiring the bare name.

## Decision

Conditional on the outstanding name-acquisition request:

- **Default (name not acquired):** the PyPI **distribution name is `boilerplate-cli`**. The import package, the `[project.scripts]` console command, the repository, and the brand **stay `boilerplate`**. In `pyproject.toml`: `name = "boilerplate-cli"`, with `[project.scripts] boilerplate = "..."` unchanged. This rename lands at/before the first PyPI publish, **not** for launch: `pyproject.toml` `name` currently remains `boilerplate` (with `get_version("boilerplate")` in `__init__.py`), and the git-URL install consumes no distribution name, so no rename is required to go public.
- **Contingency (name acquired):** if the current owner transfers `boilerplate` (voluntary surrender, or failing that a granted PEP 541 request), the distribution publishes as **`boilerplate`** and the `-cli` suffix is dropped. The distribution name lives in pyproject / wheel metadata and install docs, not in any persisted user file (the lock and the `EnvironmentProvisionRecord` store no distribution name), so a switch is a packaging change, not a user-data migration — but it **must** land before the first PyPI publish.

The primary install path is the bootstrap installer (`scripts/install.ps1` on Windows; see [install.md](../install.md)), which provides uv and installs boilerplate **from git** (`uv tool install git+https://github.com/TheRealBillSiegler/boilerplate.git`) — consuming no PyPI distribution name. *If/when published to PyPI*, the PyPI-specific install instructions MUST lead with the exact `pip install` line for the chosen distribution name and carry a one-line disambiguation note ("not the unrelated `boilerplate` package"). The OIDC trusted publisher binds to the chosen PyPI project name plus the release repo and workflow; if the name changes after acquisition, that binding changes with it.

## Options considered

- **`boilerplate-cli` distribution, `boilerplate` everything-else (chosen default)** — keeps the brand the maintainer values; cost is a permanent install-name ≠ command-name asymmetry and the mis-install trap, both mitigated only by documentation.
- **Acquire `boilerplate` (pursued in parallel)** — the best outcome: no papercut, no trap, brand intact. Rejected *as the plan of record* because it depends on a third party (and, as fallback, PyPI's discretion under PEP 541, where the incumbent's same-niche `1.x` package makes a forced claim weak). The launch cannot be gated on it; it is upside, not the baseline.
- **Real rename (e.g. `boilerkit`)** — a clean single-token brand with no papercut and no trap. Rejected because it discards the literal `boilerplate` brand and its printing-plate heritage, which the maintainer explicitly wanted to keep.
- **Fully-clean alternate token (e.g. `plateworks`)** — PyPI and GitHub both free, but the self-referential wink is weak (most developers do not bridge "plate" → boilerplate). Rejected.

## Consequences

- The default path ships an install-name/command-name asymmetry that surfaces only on PyPI. The primary install surfaces (README, quickstart, install docs) lead with the bootstrap installer / git-URL install and are unaffected by the distribution name; *if/when* published, the PyPI-specific instructions use `pip install boilerplate-cli` (or `uvx --from boilerplate-cli boilerplate`).
- This decision must be resolved (Accepted, under one branch or the other) **before the first PyPI publish** — not merely before the first public tag, since a git-URL-first public tag publishes no wheel. After the first PyPI publish the distribution name is fixed. See the release gate in [roadmap.md](../roadmap.md).
- The OIDC trusted-publisher configuration is downstream of the final name and of the decision to publish to PyPI at all; it is **not** required for the git-URL-first launch. Do not configure it until this ADR is Accepted and a PyPI publish is imminent.

## Relationship to other ADRs and intentions

See the [intentions register](../intentions/README.md) for the full definitions of both:

- INT-007 — org-independence / PyPI-installability gate; this decision is a prerequisite of "installable from PyPI."
- INT-010 — publish pipeline / OIDC trusted publisher; binds to the name chosen here.
