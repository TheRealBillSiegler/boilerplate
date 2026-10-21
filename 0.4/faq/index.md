# Frequently asked questions

## Before you start (prerequisites)

### What do I need before installing Boilerplate?

Nothing — see [Before you start](https://therealbillsiegler.github.io/boilerplate/0.4/install/#before-you-start) for what `uv` provisions for you and what the Windows installer adds.

### Do I need administrator rights?

Only for the `winget` (Windows Package Manager) installs on Windows — see [Before you start](https://therealbillsiegler.github.io/boilerplate/0.4/install/#before-you-start).

### Is `-ExecutionPolicy Bypass` in the install command safe?

Yes — it is scoped to that one process; see [Before you start](https://therealbillsiegler.github.io/boilerplate/0.4/install/#before-you-start).

## About Boilerplate

### What does Boilerplate do?

Boilerplate generates a ready-to-code Python project from one or more composed templates in a single command. See [Why Boilerplate?](https://therealbillsiegler.github.io/boilerplate/0.4/why/index.md) for the full picture.

### How is this different from applying multiple Copier templates to one project?

Copier can apply several independent templates to one project (one answers file each), which works when the templates touch disjoint files. Boilerplate adds author-declared composition (`extends`) on top of Copier: one command, one merged question set, and deterministic precedence when layers overlap the same files. See [Why Boilerplate?](https://therealbillsiegler.github.io/boilerplate/0.4/why/index.md) for the full comparison.

### How do I get accessible, color-free output?

Set `BOILERPLATE_ACCESSIBLE=1` (or the standard `NO_COLOR`) — see [Environment variables](https://therealbillsiegler.github.io/boilerplate/0.4/cli/#environment-variables).

## Security

### How do I report a security vulnerability?

Do **not** open a public GitHub issue. Report vulnerabilities privately by following the [Security policy](https://therealbillsiegler.github.io/boilerplate/0.4/governance/security/index.md). This keeps details confidential until a fix is available.

## Support

### How do I report a bug, request a feature, or contribute?

See the [Contributing guide](https://therealbillsiegler.github.io/boilerplate/0.4/governance/contributing/index.md) to get started, or [Reporting bugs and requesting features](https://therealbillsiegler.github.io/boilerplate/0.4/governance/contributing/#reporting-bugs-and-requesting-features) for issues.
