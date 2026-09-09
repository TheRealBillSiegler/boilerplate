# Pushing container images

Push a local Docker image to Azure Container Registry (ACR) using Azure CLI and short-lived AAD tokens. Use the provided script or follow the manual steps.

## Requirements

Before pushing, ensure:

- You've already built a local Docker image (see [Building container images](building-container-images.md)).
- You're logged into Azure CLI (`az login`) with permission to `AcrPush` for the target registry.
- You have `sudo` privileges in WSL2 to interact with Docker.

## Push options

You can use the provided script to streamline the push process or push the image manually.

### Use the push script

Run the script from your project directory:

```bash
./scripts/push-container.sh
```

This script will:

- Determine the default image name from your `pyproject.toml` (e.g. `text-highlighter:local`).
- Authenticate to Azure Container Registry via `az acr login`, acquiring a short-lived AAD token. This is the only registry the script supports today — it doesn't work against Docker Hub, GHCR, or any other non-ACR registry, even though the `container_registry` question you're asked at generation time defaults to `ghcr.io`.
- Re-tag the image and push it to the registry host you pass via `--acr-name`, or the `container_registry` answer from generation time if you omit it:

  ```text
  <your-registry>.azurecr.io/<image-name>:latest
  ```

You can override defaults with:

```bash
./scripts/push-container.sh \
  --image-name text-highlighter:local \
  --acr-name myregistry.azurecr.io \
  --tag prod
```

### Push manually

Follow these steps to push the image manually:

1. Authenticate to Azure CLI

    ```bash
    az login
    ```

2. Acquire an ACR token

    ```bash
    TOKEN=$(az acr login \
      --name <your-registry> \
      --expose-token \
      --query accessToken -o tsv)
    ```

3. Log in to Docker using the token

    ```bash
    echo "$TOKEN" | sudo docker login <your-registry>.azurecr.io \
      --username 00000000-0000-0000-0000-000000000000 \
      --password-stdin
    ```

4. Tag and push the image

    ```bash
    sudo docker tag text-highlighter:local \
      <your-registry>.azurecr.io/text-highlighter:latest

    sudo docker push <your-registry>.azurecr.io/text-highlighter:latest
    ```

Replace the image name, registry, and tag as needed.

## Verifying the push

After pushing, you can confirm the image exists in Azure via the portal or CLI:

```bash
az acr repository show-tags \
  --name <your-registry> \
  --repository text-highlighter
```

## Where next

Back to the [container deployment guide](index.md), or the [Streamlit template guide](../../index.md).
