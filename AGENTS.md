# boilerplate

## Project

- Tech stack and dependencies: see `pyproject.toml`
- Tooling: ruff, pyright, pytest, uv. Code must pass ruff and pyright (strict mode) cleanly.
- This project's CI runs on GitHub Actions.
- Do not circumvent the linter. Do not change linting rules.
- Dependencies are managed via `uv`. See `pyproject.toml` for index configuration.
- Run tests: `uv run pytest` (from repo root; `testpaths = ["tests"]` resolves relative to root)
- Run lint: `uv run ruff check --fix .`
- Before every push, run the local gate: `uv run python scripts/check.py`. It mirrors the CI gate; a failure caught locally saves a billed CI run.

## Python

### Imports

- No relative imports (enforced by ruff `ban-relative-imports = "all"`).

### Module organization

- Keep modules focused on a single responsibility. Avoid mixing unrelated concerns in the same module.
- One class per file, even if the class is small.
- Group related domain objects in subdirectories (models, exceptions).
- Tests mirror `src/` structure under `tests/`.

### Design

- Prefer modern, state-of-the-art approaches. Use current language features, libraries, and patterns over legacy alternatives.
- Keep domain logic pure and side-effect free. Orchestration in services; I/O in adapters.
- Prefer composition over inheritance. Use `Protocol` or ABCs for contracts.
- Expose interfaces using `collections.abc` types (`Mapping`, `Sequence`, `Iterable`).
- Use Pydantic `BaseModel` for request, response, and config models at boundaries. Keep the algorithmic core lean with dataclasses or plain classes.
- Design operations to be idempotent when possible.
- Reuse existing libraries and proven code. Avoid reinventing the wheel.
- Orchestrate, don't reimplement: delegate to established tools (Copier for rendering/answers/merge; proto for toolchains). Build only what doesn't exist (composition, catalog, profiles). See `docs/design/adr-001-build-vs-adopt.md`.
- Use all underlying technologies idiomatically, as each technology's own documentation describes, and set the example of doing so. Where a design departs from a technology's idiom, name the departure and the reason. See `docs/design/01-overview.md`.
- Prefer immutable data structures.
- Use context managers for resource cleanup.
- Prioritize DX and UX.
- Consider algorithmic complexity in design decisions.

### Validation and error handling

- Fail fast with early validation.
- Handle errors at the appropriate abstraction level.

### Types and docs

- Full type hints on public APIs.
- Google-style docstrings per the official [Google Python Style Guide §3.8](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings), rendered by mkdocstrings: summary line, then `Args:`, `Returns:`, `Raises:`, `Attributes:`, and `Examples:` sections as applicable. Classes document `Attributes:`; modules open with a summary of purpose and key classes.
- Types live in annotations, not docstrings: per §3.8, an `Args:` description carries a type only where the signature is unannotated. mkdocstrings renders parameter and return types from the annotations.
- House choices on top of §3.8: imperative summaries repo-wide ("Calculate…", not "Calculates…" — the guide allows either style but requires consistency), and `Examples:` sections are runnable doctests (CI runs `pytest --doctest-modules src`).
- The canonical worked example for the full section vocabulary (module docstrings, `Yields:` for generators, properties documented in their getters, `*args`/`**kwargs` notation) is [napoleon's Google-style example](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html), read with the types rule above. Standard section names only — mkdocstrings renders unrecognized sections as admonitions.
- Docstrings must not contain conversation leakage.

Worked format:

```python
def calculate_line_totals(order_items: list[OrderItem]) -> list[float]:
    """Calculate the total price for each order line item.

    Args:
        order_items: Items with unit price and quantity.

    Returns:
        Totals in the same order as the input items.

    Raises:
        ValueError: If any item has a negative price or quantity.

    Examples:
        >>> calculate_line_totals([OrderItem(unit_price=10.0, quantity=2)])
        [20.0]
    """
```

### Observability

- Use stdlib `logging.getLogger(__name__)` for logging.
- Include correlation IDs when available.
- No direct printing. Design for observability from the start.

## Testing

### Structure

- One test module per source module. Mirror the `src/` path: `src/api/auth/claims.py` → `tests/api/auth/test_claims.py`.
- Use test classes within a file to segment scenarios (happy path, sad path, boundary cases).
- Do not split test classes for one source module across multiple files.
- The one exception to mirroring `src/` is `tests/integration/boilerplate/composition/scenarios/`, whose tests span modules; see `tests/AGENTS.md`.

### Markers

Registered in `pyproject.toml`:

| Marker        | Usage                                                                    |
| ------------- | ------------------------------------------------------------------------ |
| `integration` | Auto-applied to tests under `tests/integration/` (conftest hook)         |
| `slow`        | Marks slow tests; deselect with `-m "not slow"`                          |
| `scenario`    | Auto-applied to composition scenarios; deselect with `-m "not scenario"` |
| `snapshot`    | Syrupy snapshot tests; grouped onto one xdist worker                     |

### Quality

- Tests document behavior, not implementation details.
- Prefer parametrized tests and fixtures; avoid global state.
- Add a regression test for every fixed bug in code.
- Control time, randomness, and external I/O (deterministic seeds, freeze time, stub network/disk).

## Security

Architecture is zero-trust-aligned. All security decisions must respect the OWASP Top 10.

### Defaults

- No secrets in code, config, or logs. Use environment variables or Key Vault.
- Validate and sanitize all external inputs. Document trust boundaries.
- Redact sensitive data in logs. Classify data explicitly.
- Use parameterized DB access or ORM. No string-constructed SQL.
- Use modern crypto libraries. Never implement your own encryption.
- Fail closed. Emit actionable errors without leaking sensitive details.
- Apply least privilege to all service accounts, tokens, and permissions.

### Encryption and identity

- TLS 1.3+ for all services.
- AES-256-GCM or stronger for storage encryption.
- Envelope encryption for multi-tenant data.
- Secrets in a secrets manager (e.g., Azure Key Vault, HashiCorp Vault). Rotate keys automatically.
- Use a federated identity provider (e.g., Microsoft Entra, Okta) for identity.

### Data classification

- Tag data by sensitivity level: Public, Internal, Confidential, Restricted.
- Apply retention and access policies accordingly.

## Markdown

- Sentence case for headings.
- No hard line-wraps; keep each paragraph or bullet on one logical line.
- Use RFC 2119 language (MUST, SHOULD, MAY) in governance and specification documents.

## Versioning

- Template versions in `boilerplate.yml` move once per release, measured from the last released version of that template. Take the smallest step the whole unreleased change set requires and land it once; never bump per change or per pull request. If an unreleased bump already exists, raise its size when a later change needs a bigger step instead of adding another.
- The CLI version in `pyproject.toml` is written by release-please from conventional commits (`RELEASING.md`); never edit it by hand.
- Pre-1.0 templates: a breaking change is a MINOR bump, everything else is PATCH. Policy: `docs/templates-hub/versioning.md`.

## Commits

Use conventional commits:

```text
<type>[optional scope]: <description>
```

| Type       | Purpose                   | In the changelog |
| ---------- | ------------------------- | ---------------- |
| `feat`     | New feature               | Yes              |
| `fix`      | Bug fix                   | Yes              |
| `perf`     | Performance improvement   | Yes              |
| `revert`   | Revert a previous commit  | No               |
| `docs`     | Documentation only        | No               |
| `style`    | Formatting (no logic)     | No               |
| `refactor` | Refactor (no feature/fix) | No               |
| `test`     | Add/update tests          | No               |
| `build`    | Build system/dependencies | No               |
| `ci`       | CI/config changes         | No               |
| `chore`    | Maintenance/misc          | No               |

- Present tense, imperative mood: "add feature" not "added feature".
- First line at most 72 characters (type, scope and description together).
- Include issue references in commit messages when applicable.
- A commit-range lint (`scripts/commit_lint.py`, run by CI's required `check` job and by `scripts/check.py`) enforces the type set and the 72-character limit on every commit in a pull request.
- Reword the subject `git revert` generates to `revert: <description>`; the lint rejects `Revert "..."`, merge commits and `fixup!`/`squash!`/`amend!` commits.
- The "In the changelog" column above is `release-please-config.json`'s `changelog-sections`; that file decides visibility, this table mirrors it.
- Mark a commit `!` (or add a `BREAKING CHANGE:` footer) when it is breaking per [Versioning § What qualifies as breaking](docs/governance/versioning.md#what-qualifies-as-breaking). Breaking is measured against the last release tag, not the parent commit. A `!`/`BREAKING CHANGE:` commit surfaces in the changelog regardless of type.
