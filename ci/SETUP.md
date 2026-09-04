# CI pipeline setup

One-time Azure DevOps configuration required before the multi-stage pipeline
(`ci/azure-pipelines.yml`) operates correctly.

> **Role.** This folder is this project's own Azure DevOps pipeline definition (`settings.yml` ships placeholders; real values are supplied where the pipeline runs). Today new projects adopt it by copying, per the quick start below; parts of it are expected to become shipped template substrate (a future CI template variant). That future role is why nothing here is dead configuration — relocate when the substrate takes shape, don't delete.

## Quick start for new projects

1. Copy the `ci/` folder into your repository.
2. Edit `ci/settings.yml` — set the five variables to match your project:
   `feedName`, `serviceConnection`, `publishUrl`, `checkUrl`,
   `pythonVersion`.
3. If `pyproject.toml` declares a `[[tool.uv.index]]`, its `name` must equal `feedName`.
4. Complete the portal configuration described below.

## Pipeline architecture

The pipeline triggers on `main` and `develop` and runs four stages:

| Stage | Display name | Condition | Template |
| ----- | ------------ | --------- | -------- |
| `BuildTest` | Build & Test | always | `templates/jobs/build-test.yml` |
| `PublishDev` | Publish (develop) | `develop` + succeeded | `templates/jobs/publish.yml` |
| `PublishRelease` | Publish (release) | `main` + succeeded | `templates/jobs/publish.yml` |
| `TagRelease` | Tag Release | `main` + `PublishRelease` succeeded | `templates/jobs/tag-release.yml` |

The `BuildTest` stage runs quality gates (`ruff check`, `ruff format --check`,
`pyright`) before `pytest`. All four tools are installed as dev dependencies
via `uv sync --locked`.

Feed authentication is handled by dynamically constructed uv named-index
credentials (`UV_INDEX_<FEED_NAME>_USERNAME` / `UV_INDEX_<FEED_NAME>_PASSWORD`)
set in `templates/steps/install-uv.yml`. The feed name is derived from the
`feedName` variable in `ci/settings.yml`.

## Pipeline definition

### PR validation (branch policy)

Azure Repos Git does not support YAML `pr:` triggers. PR validation must be
configured as a **Build Validation** branch policy on each protected branch.

1. Navigate to **Repos → Branches**.
2. Open the branch menu for `develop` → **Branch policies**.
3. Under **Build Validation**, click **+** (Add build policy).
4. Select the pipeline, set **Trigger** to **Automatic**, and **Policy
   requirement** to **Required**.
5. Repeat for `main`.

### Scope job authorization to project

By default a new pipeline uses collection-scoped authorization, granting every
job access to all projects in the organization.

1. Open **Project Settings → Pipelines → Settings**.
2. Enable **Limit job authorization scope to current project for non-release
   pipelines**.

This is a project-level toggle (not per-pipeline). If already enabled at the
organization level, no action is needed. The toggle restricts
`$(System.AccessToken)` to the current project.

### Set the YAML path

1. Edit the pipeline definition.
2. Set the **YAML file path** to `ci/azure-pipelines.yml`.

## Environments

Both environments are referenced as `deployment` job targets in
`templates/jobs/publish.yml`. The deployment job type is what makes approval
gates effective.

### Create `develop` environment

1. Navigate to **Pipelines → Environments**.
2. Create an environment named `develop`.
3. No approval checks needed — dev publishes run automatically.

### Create `production` environment

1. Navigate to **Pipelines → Environments**.
2. Create an environment named `production`.
3. Add an **Approvals** check with at least one required approver.
4. Add a **Branch control** check restricted to `refs/heads/main`.

The approval gate prevents accidental release publishes. Branch control ensures
only `main` can target this environment.

## Azure Artifacts feed

### Personal access token

The service connection requires a PAT scoped to Packaging. Create one before
proceeding.

1. Open **User settings** (gear icon, top-right) → **Personal access tokens**.
2. Select **New Token**.
3. Set **Name** to `<YOUR_FEED>-publish` (or any descriptive label).
4. Set **Organization** to `<YOUR_ORG>`.
5. Set **Expiration** to match your org's rotation policy (max 1 year).
6. Under **Scopes**, select **Custom defined**.
7. Click **Show all scopes** at the bottom of the scopes list.
8. Under **Packaging**, check **Read & write**. Leave all other scopes
   unchecked.
9. Click **Create**.
10. Copy the token immediately. It is shown only once.

### Service connection

Create a service connection for publishing packages to your feed.
The publish job uses `TwineAuthenticate@1` with this connection to obtain a
scoped token, which is then passed to `uv publish`.

1. Navigate to **Project Settings → Service connections → New service
   connection**.
2. Select **Python package upload (twine)**.
3. Choose **Authentication Token** as the authentication method.
4. Paste the PAT created in the previous section.
5. Name it `<YOUR_FEED>-publish` (must match `serviceConnection` in
   `ci/settings.yml`).
6. Set the feed URL to the value of `publishUrl` in `ci/settings.yml`.
7. Set **EndpointName** to `<YOUR_FEED>` (required; no spaces or special
   characters).
8. Under **Security**, do not select "Grant access permission to all
   pipelines."
9. After creation, open the service connection → **Security** tab →
   **Pipeline permissions** → click **+** → select your pipeline.
   Alternatively, skip this step; the first pipeline run
   will pause with a "permit access" prompt that an admin can approve.

This gives the publish stage a dedicated, independently revocable credential
scoped to feed write only. The pipeline's `System.AccessToken` is not used for
publishing.

### Feed permissions

The service connection authenticates with the PAT owner's identity. That user
must have **Contributor** on the feed.

1. Navigate to **Artifacts → `<YOUR_FEED>` → Feed settings → Permissions**.
2. Confirm the PAT owner's account appears with **Contributor** role. If not,
   add the account and grant **Contributor**.

The publish job also sets `UV_PUBLISH_CHECK_URL` to the feed's simple index
URL (the `checkUrl` variable in `ci/settings.yml`), enabling duplicate package
detection (skip-if-exists behavior).

### Verify upstream sources

Upstream sources on the feed can introduce dependency confusion risks.

1. Navigate to **Artifacts → `<YOUR_FEED>` → Feed settings → Upstream sources**.
2. If upstream sources are enabled, verify they point only to trusted
   registries (e.g., `pypi.org`).
3. If the feed is intended for internal packages only, disable upstream sources
   or use `@local` scope when resolving packages.

## Build artifacts and integrity

The `BuildTest` stage produces a `dist` pipeline artifact containing the wheel,
sdist, and a `SHA256SUMS` manifest. The publish job verifies hashes before
uploading:

```text
sha256sum -c SHA256SUMS
```

This prevents tampered or corrupted artifacts from reaching the feed.

## Version scheme

Version is extracted from `pyproject.toml` by `templates/steps/extract-version.yml`.

- **`develop` branch:** patched to `X.Y.Z.dev<BuildId>` before building.
- **`main` branch:** uses the base version as-is (e.g., `0.2.0`).

If the package must never reach public PyPI, add the `Private :: Do Not Upload`
classifier to `pyproject.toml`.

## Tag release

The `TagRelease` stage runs only on `main`, after `PublishRelease` succeeds.

- **Tag-exists guard:** if `v<version>` already exists the stage emits a
  warning and skips. No failure.
- **Annotated tag:** `git tag -a "v<version>" -m "Release v<version>"` is
  pushed to origin.
- **Credential cleanup:** runs unconditionally (`condition: always()`) to
  clear persisted git credentials.

The job uses `persistCredentials: true` and `fetchDepth: 1` (shallow clone).

## Security notes

- **Credential isolation:** each stage uses only the credentials it needs.
  Build & Test uses dynamically constructed named-index credentials
  (`UV_INDEX_<FEED_NAME>_USERNAME` / `UV_INDEX_<FEED_NAME>_PASSWORD`) backed
  by `$(System.AccessToken)` for read-only index access. Publish uses the
  service connection defined in `ci/settings.yml` (feed write only). Tag
  Release uses `$(System.AccessToken)` with `persistCredentials` (git push
  only).
- **Service connection over System.AccessToken for publish:** the service
  connection is independently revocable and auditable without affecting other
  pipeline capabilities.
- `$(System.AccessToken)` is an ADO-managed runtime secret scoped per the
  job-authorization setting above. It is used in Build & Test (feed read via
  `install-uv.yml`) and Tag Release (git push).
- `uv` is installed via `templates/steps/install-uv.yml`, which pins to a
  specific version (`uvVersion` parameter). Both Build & Test and Publish
  call this template. The Publish stage installs uv independently (with
  `sync: false`) and does not reuse the Build & Test installation.

## Verification after setup

After completing the portal configuration and pushing the pipeline YAML:

1. Push to `develop` and confirm:
   - `BuildTest` stage passes.
   - Test results and code coverage appear in the ADO build summary.
   - A `X.Y.Z.dev<BuildId>` package appears in the feed.
2. Merge to `main` and confirm:
   - `BuildTest` stage passes.
   - The `production` environment approval gate triggers on `PublishRelease`.
   - After approval, the release package publishes to the feed.
   - `TagRelease` creates and pushes an annotated `v<version>` tag.

## Per-environment overrides

When dev and release publish to different feeds or orgs, add
environment-specific variables to `ci/settings.yml` and override at the stage
level. Only the stages that differ need explicit values.

```yaml
# ci/settings.yml — per-environment example
variables:
  # Shared
  pythonVersion:       "3.13"

  # Production (default)
  feedName:            prod-feed
  serviceConnection:   prod-feed-publish
  publishUrl:          https://<YOUR_ORG>.pkgs.visualstudio.com/_packaging/prod-feed/pypi/upload/
  checkUrl:            https://<YOUR_ORG>.pkgs.visualstudio.com/_packaging/prod-feed/pypi/simple/

  # Development overrides (used only by PublishDev stage)
  devFeedName:         dev-feed
  devServiceConnection: dev-feed-publish
  devPublishUrl:       https://<YOUR_ORG>.pkgs.visualstudio.com/_packaging/dev-feed/pypi/upload/
  devCheckUrl:         https://<YOUR_ORG>.pkgs.visualstudio.com/_packaging/dev-feed/pypi/simple/
```

Then override the `PublishDev` stage parameters in `ci/azure-pipelines.yml`:

```yaml
  - stage: PublishDev
    jobs:
      - template: templates/jobs/publish.yml
        parameters:
          environment:       develop
          serviceConnection: ${{ variables.devServiceConnection }}
          publishUrl:        ${{ variables.devPublishUrl }}
          checkUrl:          ${{ variables.devCheckUrl }}
          feedName:          ${{ variables.devFeedName }}
```

