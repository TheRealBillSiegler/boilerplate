# Customization

Every template — current and future — can be customized three ways, ordered by power. Reach for the least powerful mechanism that works:

| You want to… | Use | Grain |
| --- | --- | --- |
| Set a value stamped into output (an index URL, a registry, your name) | **Profile** (`profile.toml`) | a value |
| Add or replace whole files, shareably | a **layer** — a template that `extends` another | structure |
| Anything else (edit files a template never anticipated) | **your own script** after `boilerplate new` | behavior |

## Profile (`profile.toml`)

Create `profile.toml` in the boilerplate config directory (`%APPDATA%\boilerplate\` on Windows; `$XDG_CONFIG_HOME/boilerplate/` or `~/.config/boilerplate/` elsewhere):

```toml
[defaults]                      # fills a matching question in ANY template
author_name = "Jane Dev"
package_index_url = "https://pkgs.example.com/org/_packaging/feed/pypi/simple/"

[templates.streamlit]           # only for this template; overrides [defaults]
container_registry = "myregistry.azurecr.io"
```

- Keys are **template question names** (see each template's `copier.yml`). The only reserved names are the two table headers; a key matching no question is ignored.
- Precedence, high to low: your interactive answer › `[templates.<name>]` › `[defaults]` › the template's own default. Defaults pre-fill prompts — you can still override at the prompt; `--yes` takes them as-is.

### Questions the first-party templates share

| Question | Templates | Effect |
| --- | --- | --- |
| `package_index_url` | `project` and everything extending it | emits a default `[[tool.uv.index]]` block in the generated `pyproject.toml` (empty = public PyPI, no block) |
| `container_registry` | `streamlit` | registry used by the generated `push-container.sh`, which authenticates via Azure CLI (ACR) today regardless of this value — pushing to a different registry (including the `ghcr.io` default) needs your own login step |
| `author_name` / `author_email` | `project` and everything extending it | project metadata |

## Layers (structure)

Need files a template doesn't ship? Author a template that `extends` it and add them — composition merges files, questions, and tasks:

```yaml
# my-org-project/boilerplate.yml
schema_version: "1"
name: org-project
version: 0.1.0
description: Org house style on top of the base project template.
extends: [project]
```

Point boilerplate at its parent directory with `--templates-dir` (or set the `BOILERPLATE_EXTRA_TEMPLATE_DIRS` environment variable — a JSON list of paths, e.g. `BOILERPLATE_EXTRA_TEMPLATE_DIRS='["C:/my/templates"]'`, in the environment or a `.env` file in the working directory; a bare path string is rejected) and run `boilerplate new org-project`. The option adds to the search path rather than replacing it, so bundled templates like `project` stay resolvable for `extends`.

## Your own script (behavior)

For anything neither values nor layers cover — appending to a generated file, registering the project somewhere — run your own script after generation:

```powershell
boilerplate new project my-app
./my-post-gen.ps1 my-app
```

Boilerplate deliberately does not manage these scripts.

## The org pattern

An organization's customization is **two plain files delivered by one org-owned script**, run once per developer machine after the canonical installer:

1. `uv.toml` — points the *machine's* package resolution at the org feed (plus credential tooling such as `keyring`). This is uv configuration, not boilerplate's.
2. `profile.toml` — the org's generation defaults (above).

A reference script an org can adapt (fictional `acme` names):

```powershell
#Requires -Version 7
# acme-setup.ps1 — run AFTER the public boilerplate installer.
$ErrorActionPreference = 'Stop'

# 1. Machine package resolution: authenticated org feed for uv.
uv tool install keyring --with artifacts-keyring
$UvDir = Join-Path $env:APPDATA 'uv'
New-Item -ItemType Directory -Force $UvDir | Out-Null
@'
keyring-provider = "subprocess"
publish-url = "https://pkgs.example.com/acme/_packaging/feed/pypi/upload/"
check-url = "https://VssSessionToken@pkgs.example.com/acme/_packaging/feed/pypi/simple/"

[[index]]
name = "acme"
url = "https://VssSessionToken@pkgs.example.com/acme/_packaging/feed/pypi/simple/"
default = true
'@ | Set-Content (Join-Path $UvDir 'uv.toml') -Encoding utf8

# 2. Generation defaults: stamped into every project the developer creates.
$BpDir = Join-Path $env:APPDATA 'boilerplate'
New-Item -ItemType Directory -Force $BpDir | Out-Null
@'
[defaults]
package_index_url = "https://pkgs.example.com/acme/_packaging/feed/pypi/simple/"

[templates.streamlit]
container_registry = "acme.azurecr.io"
'@ | Set-Content (Join-Path $BpDir 'profile.toml') -Encoding utf8

Write-Host "Acme configuration applied."
```

Hosting, verifying, and updating that script is the org's business — the same trust boundary as the rest of its machine setup. Note the script overwrites any personal `profile.toml`; on org machines that is usually what you want.

## Where next

- [Environment](environment/index.md) — the toolchain your customized projects land in.
- [Commands](cli.md) — the full CLI reference.
