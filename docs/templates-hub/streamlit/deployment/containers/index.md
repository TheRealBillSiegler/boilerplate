# Deploying Streamlit containers

Containerize a Streamlit application and deploy it to Azure Container Registry (ACR) using Docker and the Azure CLI. This guide provides scripts and manual steps for each part of the process.

## Overview

These pages cover deploying Streamlit apps in containers using WSL2 on Windows. Scripts automate the routine steps; every step also has a manual equivalent.

All steps assume your development environment is Ubuntu running inside WSL2.

## What you'll learn

- How to prepare your machine for containerized Streamlit deployment
- How to build Docker images from your Streamlit project
- How to publish those images to Azure Container Registry (ACR)
- How to stay aligned with security best practices

!!! warning "Don't add yourself to the `docker` group"
    Running Docker without `sudo` requires membership in the `docker` group, which grants root-level access via the Docker socket. Every example and script in this guide uses `sudo` for Docker commands instead, keeping a clear privilege boundary between your user session and the Docker daemon.

## Topics

- [Environment setup](environment-setup.md)
  Prepare your WSL2 Ubuntu environment by installing Docker, Azure CLI, and `uv`.

- [Building container images](building-container-images.md)
  Build Docker images using a convenience script or manual `docker buildx` commands.

- [Pushing container images](pushing-container-images.md)
  Publish your local image to ACR using an AAD-based token and optional script automation.
