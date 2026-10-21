# Environment setup

Install the tools needed to build and deploy containerized applications from your WSL2 Ubuntu environment. Choose between a fully automated setup script or manual installation.

## Platform setup (one-time)

If you're setting up WSL2 for the first time, open PowerShell as Administrator and run:

```powershell
wsl --install
```

This installs:

- Windows Subsystem for Linux (WSL2)
- Ubuntu (default distribution)
- Required virtualization components

After installation, restart your machine and launch Ubuntu from the Start Menu to complete setup.

## Setup options

The build and push scripts use `docker` directly when your session can already reach the daemon, and fall back to `sudo docker` otherwise — see the [Docker security note](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/streamlit/deployment/containers/index.md) for why staying out of the `docker` group is worth it.

Choose one of the following methods to install the required tools inside your WSL2 Ubuntu environment.

### Automated setup (recommended)

The setup script ships in the [boilerplate repository](https://github.com/TheRealBillSiegler/boilerplate/blob/main/scripts/setup-wsl-env.sh), not in your generated project — download it first, then run it in your Ubuntu terminal:

```bash
curl -O \
  https://raw.githubusercontent.com/TheRealBillSiegler/boilerplate/main/scripts/setup-wsl-env.sh
chmod +x setup-wsl-env.sh
./setup-wsl-env.sh
```

This installs:

- Docker CE (from Docker's official APT repository)
- Azure CLI (from Microsoft's APT repository). The script always installs it; you only need it for Azure Container Registry pushes or an Azure DevOps package index. If neither applies, use the manual setup below and skip the Azure CLI section.
- uv (from Astral's installer)

Example usage:

```bash
sudo docker run hello-world
```

### Manual setup

If you prefer to install dependencies manually, use the commands below.

#### Docker CE

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg lsb-release apt-transport-https

sudo mkdir -m 0755 -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg |
sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) \
signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable" |
sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin \
  docker-compose-plugin
```

#### Azure CLI

Only needed for pushing to Azure Container Registry or building against an Azure DevOps package index — skip this section otherwise.

```bash
curl -sL https://packages.microsoft.com/keys/microsoft.asc |
gpg --dearmor |
sudo tee /usr/share/keyrings/microsoft.gpg > /dev/null

AZ_REPO=$(lsb_release -cs)
echo "deb [arch=$(dpkg --print-architecture) \
signed-by=/usr/share/keyrings/microsoft.gpg] \
https://packages.microsoft.com/repos/azure-cli/ $AZ_REPO main" |
sudo tee /etc/apt/sources.list.d/azure-cli.list

sudo apt update
sudo apt install -y azure-cli
```

#### uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify the installation:

```bash
uv --version
```

## Where next

[Continue to building container images](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/streamlit/deployment/containers/building-container-images/index.md), or return to the [container deployment overview](https://therealbillsiegler.github.io/boilerplate/0.4/templates-hub/streamlit/deployment/containers/index.md).
