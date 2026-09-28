---
paths:
  - "scripts/**"
---

# Script tenets

Every script under here is contributor-facing tool output: what it prints, what its `--help` says, and what its docstring claims. Hold each against these before calling a script "done":

- **One narration idiom.** Plain text with color, no emoji — every script under here reads the same way for the same step, and a new script joins that idiom rather than inventing its own.
- **Portable paths in text.** A path shown to a user — an argparse default, a `--help` string, a printed path — uses forward slashes, never a hardcoded OS-specific separator.
- **Point at the doc, don't restate it.** A docstring or `--help` string names the doc that owns contributor instructions (e.g. `docs/governance/contributing.md`) instead of repeating them, so the two can't drift apart.
