# ADR-003: Render with Copier `unsafe` — no task/extension consent gate

**Status**: Accepted (current posture; deliberately diverges from the target security model) **Date**: 2026-06-09, reworked 2026-08-15 **Deciders**: Project team

## Context

The security design ([10-security](10-security.md), [03-template-system](03-template-system.md)) specifies a default-deny posture: template tasks and Jinja2 extensions run only behind user consent (`--allow-tasks`/`--allow-extensions`), a package allowlist, an import blocklist, a `SandboxedEnvironment`, and a binary trust model. **None of that is implemented** — see [status.md](../status.md) (trust / sandbox / consent: "no code exists").

## Decision

Composition layers render through Copier's `Worker` with `unsafe` granted per invocation, exactly where the layer needs it: when the `_jinja_extensions` union of the layer's scoped view is non-empty ([04 §Copier Worker Interface](04-composition-engine.md#copier-worker-interface)) or when the layer's tasks will actually run (`composition/rendering/engine.py`, `layer_needs_unsafe`). Extension-free, task-free invocations keep Copier's own consent gate. There is no prompt, sandbox, trust level, or blocklist anywhere — whatever a template declares, executes.

Public exposure is sanctioned under this posture: strangers installing the CLI and rendering templates is in scope and does not wait for the trust model.

## Rationale

- The trust / consent / sandbox infrastructure is not built; gating on a non-existent system would block all rendering.
- Template sources are **local-only** — the bundled first-party templates, plus local directories the user supplies deliberately (`--templates-dir`), which are user-chosen rather than first-party: `build_template_catalog` (`cli/utils.py`) constructs a `DirectoryTemplateRepository` directly, and a Git-backed repository remains unimplemented. The code an `unsafe` render executes is code the user already has on disk and chose to render — the same trust act as running any downloaded script.
- Publication changes who runs boilerplate, not where template code comes from, so going public leaves that boundary intact.
- Recording the gap explicitly so it is a conscious posture, not silent drift.

## Consequences

- Rendering a template that declares tasks or extensions executes them as arbitrary local code with no gate. Acceptable **only while sources are local and deliberately chosen** — bundled first-party templates or user-supplied directories.
- **This MUST be tightened before** remote/Git sources, a catalog with third-party entries, or community templates ship. That work is the trust model in [10-security](10-security.md) and will get its own ADR when built.
- The design docs describe the *target* (default-deny); this ADR is the honest record of the *current* posture and the divergence.

## Expiry

This ADR records a **temporary** posture, not the target. It expires when the trust / consent / sandbox model ([10-security](10-security.md)) is implemented — which MUST happen before any remote, catalog, or community template source ships. A new ADR will then record default-deny as the current posture and supersede this one.

## Verification (2026-08-15)

`composition/rendering/engine.py` computes `layer_needs_unsafe` from the merged extension union and the layer's runnable tasks, and passes `"unsafe": layer_needs_unsafe` per `Worker` invocation. Grep across `src/` for `trust|sandbox|consent|blocklist` → no implementation.
