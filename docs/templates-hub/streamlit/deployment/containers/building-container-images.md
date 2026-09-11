# Building container images

Build a Docker image from your Streamlit project using either the included script or manual `docker buildx` commands.

## Requirements

Before you begin:

- Docker, reachable directly or via `sudo` — [Environment setup](environment-setup.md) covers installing it, including on WSL2.
- Your project must include:
    - A `pyproject.toml` file with a `[project] name` field.
    - A `uv.lock` file for dependency resolution.

If your project's package index (the `package_index_url` answer from generation time) is empty, that's everything you need. If it points at a private index, see [Private package index](#private-package-index) below.

## Build options

You can use the provided script to streamline the build process or follow the manual steps below.

### Use the build script

Run the build script from your project directory:

```bash
./scripts/build-container.sh
```

This script will:

- Validate the presence of `uv.lock` (and read `pyproject.toml` to derive the default image name).
- Use `docker` directly if your session can reach the daemon, or `sudo docker` otherwise.
- Build the image with `docker buildx`. When your project has a private package index configured, it authenticates first — see [Private package index](#private-package-index).
- Tag the image using the project name with a default `:local` tag.

If your `pyproject.toml` includes:

```toml
[project]
name = "text-highlighter"
```

The resulting image will be:

```bash
text-highlighter:local
```

Upon successful completion, you'll see:

```bash
✅ Docker image built successfully: text-highlighter:local
ℹ️  To run your container locally:
   docker run -p 8501:8501 text-highlighter:local
📣  Note: If your app runs on a different port, update the -p flag accordingly.
```

### Build manually

With no private package index, the script's build step is one command:

```bash
docker buildx build --tag text-highlighter:local --load .
```

Prefix it with `sudo` if your Docker daemon needs that. Replace `text-highlighter:local` with your preferred image tag.

## Private package index

When your project's package index needs credentials, the build passes them to `uv sync` as a Docker secret (`id=index`) so they never land in an image layer — the Dockerfile's `RUN --mount=type=secret,id=index,env=INDEX uv sync --default-index "$INDEX" --keyring-provider subprocess` consumes it. Which credentials, and how the script gets them, depends on the index host.

### Azure DevOps index

When the index host is `dev.azure.com` or `pkgs.visualstudio.com`, the script requests a short-lived Azure DevOps token through the Azure CLI and passes it as the secret. You need `az` installed and available on `PATH`.

Manual steps:

1. Authenticate with Azure CLI

    ```bash
    az login
    ```

2. Retrieve a short-lived Azure DevOps token

    ```bash
    TOKEN=$(az account get-access-token \
      --resource 499b84ac-1321-427f-aa17-267ca6975798 \
      --query accessToken -o tsv)
    ```

3. Build the Docker image

    ```bash
    INDEX="https://AzureDevOps:${TOKEN}@<your-feed>/simple/" \
    docker buildx build \
      --secret id=index,env=INDEX \
      --tag text-highlighter:local \
      --load .
    ```

### Any other private index

Set `INDEX_URL` to the index URL with credentials embedded (for example `https://user:token@host/simple/`) before running the script; the script errors with this instruction if it's unset:

```bash
INDEX_URL="https://user:token@host/simple/" ./scripts/build-container.sh
```

Manually, pass the same value through as the build secret:

```bash
env INDEX="$INDEX_URL" docker buildx build \
  --secret id=index,env=INDEX \
  --tag text-highlighter:local \
  --load .
```

## Verifying the image

After building, confirm that your image exists:

```bash
docker images
```

To test it locally:

```bash
docker run -p 8501:8501 text-highlighter:local
```

Change the `-p` value if your application serves on a different port.

## Where next

[Continue to pushing container images](pushing-container-images.md), or return to the [container deployment overview](index.md).
