# boilerplate

@AGENTS.md

## Agent skills

Configuration the engineering skills (`to-issues`, `triage`, `to-prd`, `qa`, `improve-codebase-architecture`, `diagnose`, `tdd`) read. Edit `docs/agents/*.md` to change.

### Issue tracker

Issues and PRDs are tracked as GitHub issues on `TheRealBillSiegler/boilerplate` via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Five flat triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context; ADRs live in `docs/design/` as `adr-NNN-*.md`. See `docs/agents/domain.md`.

### Docs rules

Edits under `docs/` and to `mkdocs.yml` are governed by the golden-path tenets in `.claude/rules/docs.md`. When delegating docs edits to a subagent, name that file in the prompt — path-scoped rules may not auto-load in subagents.

## Instruction hierarchy

When instructions conflict, apply in this order:

1. Security and privacy guardrails
2. Repository-wide instructions
3. Folder-specific instructions
4. File-specific instructions
5. Task-specific requirements
