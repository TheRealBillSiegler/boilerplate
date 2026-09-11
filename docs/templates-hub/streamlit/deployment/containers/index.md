# Deploying Streamlit containers

Every render ships a Dockerfile and two scripts — `scripts/build-container.sh` and `scripts/push-container.sh` — that build and publish a container image. This section covers each part of the process; every script step also has a manual equivalent.

## Overview

The scripts run on any Docker host: Linux, macOS or Windows with Docker Desktop, or WSL2 on Windows. [Environment setup](environment-setup.md) covers the WSL2 case.

Once an image is built, running it locally always looks the same:

```bash
docker run -p 8501:8501 text-highlighter:local
```

## What you'll learn

- How to prepare your machine for containerized Streamlit deployment.
- How to build Docker images from your Streamlit project.
- How to push those images to GitHub Container Registry, Azure Container Registry, or any other registry you're already logged into.

!!! warning "Don't add yourself to the `docker` group"
    Running Docker without `sudo` requires membership in the `docker` group, which grants root-level access via the Docker socket. The build and push scripts detect whether your session can already reach Docker and fall back to `sudo` otherwise, so you never need that group membership just to run them.

## Topics

- [Environment setup](environment-setup.md)
  Install Docker and `uv`, plus the Azure CLI if you push to Azure Container Registry or build against an Azure DevOps package index.

- [Building container images](building-container-images.md)
  Build an image with the script or manual `docker buildx` commands; authenticate to a private package index when your project uses one.

- [Pushing container images](pushing-container-images.md)
  Publish the image to GitHub Container Registry, Azure Container Registry, or another registry, using the script or manual `docker` commands.
