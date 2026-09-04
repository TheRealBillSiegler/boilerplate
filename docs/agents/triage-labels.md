# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Canonical triage role      | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use. These flat strings match GitHub's own practice: `cli/cli` uses `needs-triage` verbatim, and `wontfix` is a GitHub default.

## Unlabeled means parked

An issue carrying none of the five labels is parked: blocked on other work, with a `Blocked by:` line in its body naming the blocker. Apply a readiness label (`ready-for-agent` / `ready-for-human`) only once the blocker clears — an unlabeled issue is not un-triaged, it is deliberately on hold.

## Note on label creation

`gh` does not auto-create labels — `gh issue edit --add-label "needs-triage"` fails if the label doesn't exist. Of the five, only `wontfix` ships as a GitHub default; the other four must be created once:

```sh
gh label create needs-triage    --description "Maintainer needs to evaluate this issue"
gh label create needs-info      --description "Waiting on reporter for more information"
gh label create ready-for-agent --description "Fully specified, ready for an AFK agent"
gh label create ready-for-human --description "Requires human implementation"
```
