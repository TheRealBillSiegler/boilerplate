# Intentions

Intentions decompose a Product into testable outcomes. Each Intention is defined in its own `INT-XXX.yaml` file in this directory.

## Schema

The Intent-Driven Development (IDD) plugin (`grillergeek-plugins/idd-framework`) prescribes a thin Intention schema. See `intention-template.md` in the plugin's references for the canonical definition.

### IDD-prescribed core (required)

| Field | Notes |
|---|---|
| `id` | Unique identifier scoped to Product (e.g., INT-001) |
| `product` | Parent Product ID (e.g., PROD-001) |
| `statement` | What the product should accomplish — outcome-oriented |
| `rationale` | Why this Intention matters to the Product |
| `priority` | `critical \| high \| medium \| low` |
| `owner` | Accountable individual |
| `status` | `draft \| defined \| in-progress \| fulfilled \| deferred` |

Optional IDD-prescribed:

| Field | Notes |
|---|---|
| `dependencies` | Other Intention IDs that must be fulfilled first |
| `expectations` | Expectation IDs that belong to this Intention (populated as Expectations are created) |

### Project extensions

INT files in this repository carry the following non-prescribed extensions:

| Field | Purpose |
|---|---|
| `outcome` | Prose description of the user-visible end state — bridges `statement` (terse outcome) to `acceptance_criteria` (measurable). |
| `acceptance_criteria` | Inline pass/fail or measurable criteria that substitute for separate Expectation files. Functionally equivalent to `Expectation.validation_criteria` from IDD. |
| `not_included` | Explicit scope boundaries — what this Intention does NOT cover. |
| `delivery_phases` | (INT-009 only) Phased rollout where the Intention can be partially delivered. |

These extensions are intentional. They're consistent across all 13 INTs in this directory and provide more concrete acceptance signal than IDD's stock schema does on its own. When IDD's `expectations` workflow is adopted formally, `acceptance_criteria` will migrate to per-Expectation files.

## Status convention

| Status | Meaning |
|---|---|
| `draft` | In flux; statement may change |
| `defined` | Articulated; ready to enter delivery |
| `in-progress` | Implementation underway |
| `fulfilled` | Acceptance criteria met; integrated |
| `deferred` | Acknowledged but intentionally out of scope for the current cycle |

Release timing — *when* an Intention transitions from `defined` to `in-progress` to `fulfilled` — is tracked in GitHub issues, not in these files. The Intention's `status` field reflects the latest known state of the work, not a release-phase label.

## How this register is used

This directory is a requirements register, not a lifecycle. The design docs in `docs/design/` came first and remain the target-state spine; the Product and Intention files were layered on in IDD's schema to state the outcomes and acceptance signal that spine serves. Execution runs through GitHub issues (see `docs/agents/issue-tracker.md`), each citing the Intention it serves; planning for efforts too large for one session runs as decision-ticket maps on the same tracker (the `wayfinder:*` labels). IDD's Expectation and Spec layers are not used: an issue's acceptance criteria and the design docs' MUST clauses carry what a Spec would, and adversarial review runs before any multi-file implementation slice. The tripwire that reopens this choice: agent-implemented slices shipping scope drift that issue-level criteria plus review fail to catch. That is the evidence the Spec layer would earn its cost.

## Source of truth

These files are the source of truth for what each Intention covers. The `intentions_index` block in [PROD-001.yaml](../products/PROD-001.yaml) is a snapshot for at-a-glance scope and may drift; this directory wins.

## Where next

Back to the [design specifications](../design/README.md), which these Intentions gate.
