# Pushing container images

Push a local Docker image to a registry using the included script or manual `docker` commands. Authentication depends on which registry you push to.

## Requirements

Before pushing, ensure:

- You've already built a local Docker image (see [Building container images](building-container-images.md)).
- Docker is reachable, directly or via `sudo`.

## Push options

You can use the provided script to streamline the push process or push the image manually.

### Use the push script

Run the script from your project directory:

```bash
./scripts/push-container.sh
```

Options:

- `-i`/`--image-name` — local image (default `<project-name>:local`).
- `-r`/`--registry` — registry hostname (default the `container_registry` answer from generation time).
- `-n`/`--namespace` — owner or organization within the registry (default `$CONTAINER_NAMESPACE`, else empty).
- `-t`/`--tag` — remote tag (default `latest`).

The remote name is `<registry>/<namespace>/<repo>:<tag>` when a namespace is set, otherwise `<registry>/<repo>:<tag>`:

```bash
./scripts/push-container.sh \
  --image-name text-highlighter:local \
  --registry ghcr.io \
  --namespace my-org \
  --tag prod
```

Authentication is chosen from the registry hostname at push time, so the same script keeps working if you change registries later.

### GitHub Container Registry and Docker Hub

`--namespace` is required — it's the owner or organization the image belongs to; the script exits with an error if it's missing. If `REGISTRY_TOKEN` is set, the script signs in with it (`docker login ghcr.io --username <namespace> --password-stdin`); otherwise it assumes you already ran `docker login ghcr.io` and continues. New packages on GHCR are private until you make them public in the package's settings on GitHub — that switch can't be undone. Docker Hub (`docker.io`) follows the same rules: `--namespace` is required and `REGISTRY_TOKEN` signs you in.

### Azure Container Registry

No namespace needed. The script requires the Azure CLI, checks `az account show` and runs `az login` if you're signed out, then acquires a short-lived Microsoft Entra ID access token with `az acr login --expose-token` and logs Docker in with it.

### Any other registry

The script assumes you're already signed in (`docker login <registry>`) and continues.

### Push manually

**GitHub Container Registry:**

```bash
echo "$REGISTRY_TOKEN" | docker login ghcr.io \
  --username <owner> \
  --password-stdin   # skip if you already ran `docker login ghcr.io`

docker tag text-highlighter:local ghcr.io/<owner>/text-highlighter:latest
docker push ghcr.io/<owner>/text-highlighter:latest
```

**Azure Container Registry:**

```bash
az login

TOKEN=$(az acr login \
  --name <your-registry> \
  --expose-token \
  --query accessToken -o tsv)

echo "$TOKEN" | docker login <your-registry>.azurecr.io \
  --username 00000000-0000-0000-0000-000000000000 \
  --password-stdin

docker tag text-highlighter:local <your-registry>.azurecr.io/text-highlighter:latest
docker push <your-registry>.azurecr.io/text-highlighter:latest
```

**Any other registry:**

```bash
docker login <registry>   # once, if not already signed in
docker tag text-highlighter:local <registry>/text-highlighter:latest
docker push <registry>/text-highlighter:latest
```

Prefix any `docker` command above with `sudo` if your daemon needs it.

## Verifying the push

GitHub Container Registry lists the image under the owner's or organization's Packages tab. Azure Container Registry lists it with:

```bash
az acr repository show-tags \
  --name <your-registry> \
  --repository text-highlighter
```

For any other registry, check its own UI or API.

## Where next

Back to the [container deployment guide](index.md), or the [Streamlit template guide](../../index.md).
