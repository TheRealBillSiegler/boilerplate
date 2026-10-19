# Release Checklist

The source of truth for "is this safe and complete to release / go public."

To verify: run every gate's command against the current tree — never assert a gate passes without running its check. Report each gate PASS/FAIL with its evidence, and a verdict: **NO-GO** if any Blocker fails; **GO with caveats** if only Quality/Advisory items remain; **GO** if all clear.

Gates are tiered. A **Blocker** failing is a hard no-go (legal / exposure /
irreversible-once-public). A **Quality** failure blocks a *credible* release. An
**Advisory** item is logged, not gating.

## Blockers — legal & no-leak (irreversible once public)

- [ ] `LICENSE` contains the full Apache-2.0 text — `grep -c "Apache License" LICENSE` ≥ 1
- [ ] `NOTICE` present and current
- [ ] No non-public identifier (hosts, feeds, registries, people) in the tree or in any tracked **filename** — run the maintainer's identifier scan (its pattern list is kept outside this repository) → zero hits after eyeballing false positives
- [ ] Zip-container assets scanned with the same list — `git grep -I` skips binaries, and formats like `.xmind` are zip archives whose entries (titles, rendered thumbnails) can carry names the text grep never sees. Unzip and grep each one.
- [ ] No secrets committed (tree + history); `uv.lock` resolves only against public PyPI
- [ ] Open-source permission on file for any content seeded from elsewhere

## Quality

- [ ] CI green on the OS matrix (ubuntu / macos / windows × 3.12 / 3.13)
- [ ] `uv run pytest` passes from the repo root; `uv run ruff check --no-fix .` clean; pyright strict clean

## Packaging metadata (before the first PyPI publish/tag)

- [ ] `pyproject.toml` `name` is the intended PyPI distribution name — see
      [adr-008](docs/design/adr-008-distribution-name.md): `boilerplate-cli` unless the
      `boilerplate` name is acquired
- [ ] When the dist name changes, update `get_version("...")` in
      `src/boilerplate/__init__.py` to match the new dist name — otherwise `__version__`
      reports `Unknown`
- [ ] `description`, `license`, `classifiers` (incl. a License + Development Status), and a
      `[project.urls]` table are complete
- [ ] OIDC trusted publisher configured against the **final** PyPI project name (do not
      configure until the name is final)

## Versioning & changelog (automated by release-please)

- [ ] The release-please PR is open with the right next version — under SemVer `0.x`,
      breaking → minor and feat → patch (per `release-please-config.json`)
- [ ] The release-please PR moves every install pin to the new tag: the `extra-files` in `release-please-config.json` (the installer and the install commands in the versioned docs; the README names `main`, which holds the latest release)
- [ ] The generated `CHANGELOG.md` entry is accurate (edit the prose if needed)
- [ ] Every release-notes entry is true at the new tag and describes a change since the previous release. Drop an entry about something no release shipped, such as a feature added and changed again between the same two tags.
- [ ] `.release-please-manifest.json` baseline version is correct

## Release mechanics

Releases are cut from `main`: release-please only watches `main`, so merging
`develop` into `main` **is** the release step.

`0.3.0`'s tag and GitHub release were both created by hand at the public cutover, before release-please started watching this repository. Everything below describes the automated flow starting with the next release.

- [ ] Merging the release-please PR cuts the tag + GitHub release
- [ ] The offline-docs bundle is attached to the release. Caveat: releases created by the
      default `GITHUB_TOKEN` do not trigger downstream `release:`-event workflows, so
      `docs-offline-bundle.yml` never fires on its own — run it via `workflow_dispatch`
      against the tag (or re-publish the release with a user token)
- [ ] (Once a PyPI publish workflow exists — deferred until the distribution name is
      final, see [adr-008](docs/design/adr-008-distribution-name.md)) the same
      `GITHUB_TOKEN` caveat applies to it
- [ ] Versioned docs deployed from the release tag:
      `uv run mike deploy --push --update-aliases X.Y latest`. One docs version per
      MAJOR.MINOR; patch releases redeploy the same `X.Y`
- [ ] First release only: `uv run mike set-default --push latest` creates the root redirect (`mike deploy` alone does not); skip this step on every later release. Once set, the version selector and root redirect are driven by the `gh-pages` branch mike maintains
- [ ] Every release (the copy is idempotent; the root page links assets under the version it was copied from, so it goes stale when that version redeploys): publish the built 404 page to the `gh-pages` branch root — GitHub Pages serves exactly one site-wide 404.html there, and `mike deploy` never writes to the branch root (only version and alias directories): `git worktree add ../gh-pages-404 gh-pages && cp ../gh-pages-404/X.Y/404.html ../gh-pages-404/404.html && git -C ../gh-pages-404 add 404.html && git -C ../gh-pages-404 commit -m "chore: sync root 404 page" && git -C ../gh-pages-404 push origin gh-pages; git worktree remove ../gh-pages-404` (replace `X.Y` with the version just deployed)

Milestone versions (`0.3.0`, `1.0.0`) are never chosen mechanically — the pre-major flags map `feat:` to patch and nothing reaches `1.0.0` on its own. Force one with an empty commit on `main`: `git commit --allow-empty -m "chore: release 0.3.0" -m "Release-As: 0.3.0"`.

At 1.0, delete `bump-minor-pre-major` and `bump-patch-for-minor-pre-major` from `release-please-config.json` (dead config above 1.0). From then on a single `feat!:` cuts a major with **no deprecation window** — ship the deprecating minor first.

Dependency licenses: all **direct** dependencies are permissive, so distributing boilerplate's own code under Apache-2.0 is fine. The vendored third-party works are the Mermaid bundle (MIT) with the libraries it embeds, the asciinema player (Apache-2.0), the IBM Plex Sans and JetBrains Mono fonts (OFL-1.1) and the logos of the tools the docs describe, all credited in `NOTICE`. The docs site and the offline docs bundle serve them — self-hosted deliberately, so using them triggers no third-party fetch — and nothing ships inside the Python package. (Raw Unicode emoji in docs prose still render via Material's twemoji CDN images; icon shortcodes don't. The docs tenets already prefer shortcodes.) The compliance posture is **unmodified redistribution**: the vendored file is byte-for-byte what the Mermaid project publishes (enforced by a `.gitattributes` `binary` entry — line-ending conversion would silently break the claim), upstream's LICENSE is copied verbatim from the pinned tag to `docs/assets/mermaid.LICENSE`, and the license banners inside the file stay intact — never re-minify or post-process it, since those banners are part of the embedded components' attribution (the other embedded components' license texts ship in `docs/assets/licenses/`, listed in `NOTICE`). The bundle does embed an EPL-2.0 component (elkjs); redistributing it unmodified with upstream's source pointer is the same posture Mermaid itself and every CDN takes, and the EPL does not reach boilerplate's own code. Upgrading Mermaid means replacing the vendored file byte-for-byte with upstream's published build and re-copying the LICENSE from the new tag, then re-deriving the embedded libraries and license texts that `NOTICE` credits from the new tag's `pnpm-lock.yaml` and the banners in the new file. There is no recurring automated license-scan gate, by design. The **transitive** tree is not all-permissive — `jinja2-ansible-filters` (GPL-3.0, via copier) and `text-unidecode` (Artistic, via python-slugify) — which is acceptable while dependencies are installed separately from PyPI, but must be revisited before ever shipping a bundled/frozen artifact (PyInstaller and similar). Re-check (`uvx pip-licenses`) when the dependency tree changes.

---

During `0.x`, only the distribution name is a stable commitment (see
[Versioning & Compatibility Policy](docs/governance/versioning.md)); other CLI/exit-code/output surfaces may change.
