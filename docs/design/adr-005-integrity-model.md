# ADR-005: Integrity model — filesystem-permission-based; cryptographic signing deferred

**Status**: Accepted

## Context

In Boilerplate's current operational model, **one file** carries security-relevant content that could be tampered with to alter behavior:

1. **The lock file** (`boilerplate.lock`) — records the committed state of every template layer in a composition, the per-layer Copier-answers hashes, and the resolved layer ordering. `lock verify` uses it as the source of truth for supply-chain drift detection.

An attacker who can write to this file can neutralise a key control: corrupting or substituting the lock file silences drift detection. Its integrity therefore matters.

It is a local file on the operator's machine. The immediate threat the current control addresses is an unprivileged local process with write access to it — not remote substitution. The current release addresses this with filesystem permissions and defers cryptographic signing, which the spec names as "planned for a future release."

## Decision

The current release relies on **filesystem-permission-based integrity** for the lock file (`boilerplate.lock`) — the sole filesystem-permission-protected artifact — and performs **no cryptographic signature verification**.

For the lock file, the spec states ([10-security §lock verify](10-security.md)):

> Lock file integrity (no cryptographic signature; the file is trusted as-is)

and:

> `lock verify` is a supply chain drift detector, not a full integrity guarantee. For stronger assurance, combine with content signing (planned for a future release).

## Options considered

### (a) Cryptographic content signing — DEFERRED to a future release

Sign the lock file (e.g., with a project-scoped key, Sigstore, or a similar content-signing scheme) so that tampering is detectable regardless of filesystem ACLs. The spec explicitly names this as "planned for a future release." It is the stronger long-term control. It is deferred for now: the signing infrastructure is not yet built, and at the current scope filesystem permissions are the proportionate control for a file that lives on the operator's own machine.

### (b) Filesystem-permission-based integrity — CHOSEN (current)

Rely on OS-level access controls (POSIX permissions / Windows ACLs) to prevent unauthorised writes. Warn at runtime on overly permissive configurations. No implementation cost beyond the warning check; consistent with the current posture of treating the lock file as a local file guarded by filesystem permissions.

### (c) No integrity control at all — REJECTED

Treating the lock file as fully trusted without any check or guidance would silently degrade the security posture below what the spec intends and provide no operational signal when ACLs are mis-set. The warning-on-permissive-ACL requirement distinguishes option (b) from this rejected baseline.

## Consequences

- `lock verify` is a **drift detector**, not an integrity guarantee. A local adversary with write access to the lock file can substitute values undetected.
- This limitation is **acknowledged in-spec** and is acceptable today, where the lock file lives on the operator's machine and cryptographic content signing is not yet available.
- This decision **SHOULD be revisited** when cryptographic content signing — the spec's "planned for a future release" — is implemented, which strengthens integrity beyond filesystem ACLs; a new ADR will record that change.

## Authoritative spec references

- [10-security §lock verify](10-security.md) — lock-file integrity scope and the deferred content-signing note

## Relationship to other ADRs

[ADR-003](adr-003-permissive-execution.md) records a related gap: permissive `unsafe` rendering with no consent gate, ahead of the trust model. Like this ADR, it is a conscious, bounded current posture that expires when the target control is implemented — there, the trust model; here, cryptographic content signing.
