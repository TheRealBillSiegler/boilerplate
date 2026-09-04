# Building container images

Build a Docker image from your Streamlit project using either the included script or manual `docker buildx` commands.

## Requirements

Before you begin:

- You should be inside a WSL2 Ubuntu environment — [Environment setup](environment-setup.md) gets you there.
- Your project must include:
    - A `pyproject.toml` file with a `[project] name` field.
    - A `uv.lock` file for dependency resolution.
- You must be logged into Azure via the Azure CLI. This is required for every build, not only for pushes to ACR — the build script always requests a short-lived Azure DevOps token to authenticate package installation during the build.

## Build options

You can use the provided script to streamline the build process or follow the manual steps below.

### Use the build script

Run the build script from your project directory:

```bash
./scripts/build-container.sh
```

This script will:

- Validate the presence of `uv.lock` (and read `pyproject.toml` to derive the default image name).
- Use your Azure CLI session to retrieve an Azure DevOps access token.
- Build the image with `docker buildx`, supplying the token to the build as a BuildKit secret (`id=index`) that the Dockerfile's `uv sync --default-index` consumes — the token is never baked into a layer.
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
   sudo docker run -p 8501:8501 text-highlighter:local
📣  Note: If your app runs on a different port, update the -p flag accordingly.
```

### Build manually

To build the container manually, follow these steps:

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
    sudo -E docker buildx build \
      --secret id=index,env=INDEX \
      --tag text-highlighter:local \
      --load .
    ```

Replace `text-highlighter:local` with your preferred image tag if needed.

## Verifying the image

After building, confirm that your image exists:

```bash
sudo docker images
```

To test it locally:

```bash
sudo docker run -p 8501:8501 text-highlighter:local
```

Change the `-p` value if your application serves on a different port.

## Where next

[Continue to pushing container images](pushing-container-images.md), or return to the [container deployment overview](index.md).
