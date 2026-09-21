---
paths:
  - "tests/**"
---

# Tests

A test states a claim about behaviour at a public seam and would fail if a line of this package changed that behaviour. Before writing one, answer three questions in its docstring or name: which seam, which source of truth gives the expected value, and which change would break it.

- **Expected values come from an independent source**: a sentence in `docs/design/`, a governance rule, a documented error code, a known literal. Never recomputed the way the code computes them, and never a constant compared with itself.
- **Patch only at boundaries.** `tests/test_patches_stay_at_boundaries.py` fails any patch of this package's own objects unless the seam is listed there with the reason the real thing cannot stand. Prefer a real fixture over a patch; the template fixtures already exist.
- **Name the claim; assert the claim.** A name that says more than the assertion checks is a defect.
- **One logical assertion.** Two claims are two tests, or one parametrized test.
- **A test guarding a library, not this package, is a tripwire**: one per dependency surface, kept minimal, and only where the code relies on something the library does not export.
- **Red first.** A test that never failed has not shown it can.

Design docs are target state: derive a test from a MUST only where the feature is shipped.
