#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# setup-wsl-env.sh
#
# Description:
#   Prepares a WSL2/Ubuntu environment for Streamlit container deployment.
#   This script installs:
#
#     - Docker CE (via Docker's APT repository)
#     - Azure CLI (via Microsoft's APT repository)
#     - uv (via Astral's official install script)
#
#   This script avoids Docker Desktop and does NOT modify group memberships.
#
#   NOTE: This is the container-deployment prep, not the boilerplate CLI
#   installer. To install the boilerplate CLI on Windows use scripts/install.ps1;
#   see docs/install.md for manual macOS/Linux steps.
# ==============================================================================

# ------------------------------------------------------------------------------
# Terminal colors
# ------------------------------------------------------------------------------
RESET="\033[0m"
BOLD="\033[1m"
BLUE="\033[1;34m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"

# ------------------------------------------------------------------------------
# Pre-checks
# ------------------------------------------------------------------------------
echo -e "${BLUE}${BOLD}Starting WSL environment setup...${RESET}"

if ! sudo -v >/dev/null 2>&1; then
    echo -e "${RED}This script requires sudo privileges.${RESET}"
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo -e "${RED}'curl' is required but not installed.${RESET}"
    echo -e "${YELLOW}Run: sudo apt install -y curl${RESET}"
    exit 1
fi

# ------------------------------------------------------------------------------
# Docker CE Installation
# ------------------------------------------------------------------------------
install_docker() {
    if command -v docker >/dev/null 2>&1; then
        echo -e "${GREEN}Docker is already installed.${RESET}"
        return
    fi

    echo -e "${BLUE}${BOLD}Installing Docker...${RESET}"

    sudo apt update
    sudo apt install -y ca-certificates gnupg lsb-release apt-transport-https

    sudo mkdir -m 0755 -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg |
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

    # /etc/os-release is a runtime system file, not resolvable at lint time.
    # shellcheck source=/dev/null
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |
        sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

    sudo apt update
    if sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; then
        echo -e "${GREEN}Docker installed successfully.${RESET}"
    else
        echo -e "${RED}Docker installation failed.${RESET}"
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# Azure CLI Installation
# ------------------------------------------------------------------------------
install_azure_cli() {
    if command -v az >/dev/null 2>&1; then
        echo -e "${GREEN}Azure CLI is already installed.${RESET}"
        return
    fi

    echo -e "${BLUE}${BOLD}Installing Azure CLI...${RESET}"

    curl -sL https://packages.microsoft.com/keys/microsoft.asc |
        gpg --dearmor |
        sudo tee /usr/share/keyrings/microsoft.gpg >/dev/null

    AZ_REPO=$(lsb_release -cs)
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/microsoft.gpg] \
https://packages.microsoft.com/repos/azure-cli/ $AZ_REPO main" |
        sudo tee /etc/apt/sources.list.d/azure-cli.list

    sudo apt update
    if sudo apt install -y azure-cli; then
        echo -e "${GREEN}Azure CLI installed successfully.${RESET}"
    else
        echo -e "${RED}Azure CLI installation failed.${RESET}"
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# uv Installation
# ------------------------------------------------------------------------------
install_uv() {
    if command -v uv >/dev/null 2>&1; then
        echo -e "${GREEN}uv is already installed.${RESET}"
        return
    fi

    echo -e "${BLUE}${BOLD}Installing uv (via Astral's official install script)...${RESET}"

    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        echo -e "${GREEN}uv installed successfully.${RESET}"
    else
        echo -e "${RED}Failed to install uv.${RESET}"
        exit 1
    fi

    # Confirm uv is now in PATH
    if ! command -v uv >/dev/null 2>&1; then
        echo -e "${RED}uv installed but not found in PATH.${RESET}"
        echo -e "${YELLOW}Try restarting your shell or running: source ~/.profile${RESET}"
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------------------
install_docker
install_azure_cli
install_uv

# ------------------------------------------------------------------------------
# Post-installation Security Notes
# ------------------------------------------------------------------------------
echo -e "${YELLOW}Do NOT add your user to the 'docker' group — it grants root-level access.${RESET}"
echo -e "${YELLOW}Always use 'sudo' with Docker commands in WSL2.${RESET}"
echo -e "${GREEN}${BOLD}Environment setup completed successfully.${RESET}"
