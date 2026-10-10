# Install

Set up the **Boilerplate** Python Development Environment on Windows, macOS, or Linux. Choose your operating system below and follow the steps appropriate to your platform.

!!! info "Overview"
    - **Windows 11:** Recommended path with a fully automated installer.  
    - **Windows 10:** Use the manual path (no `winget` by default).  
    - **macOS / Linux:** Manual setup.  
    - Python installation is handled by `uv`; no preinstallation is required.

!!! warning "Do not run bare `pip install boilerplate`"
    That name is already taken on PyPI by an unrelated, same-niche package — `pip install boilerplate` silently installs *that* package, not this one. Boilerplate is not published to PyPI; use one of the install commands below. See [adr-008](design/adr-008-distribution-name.md) for the full mis-install hazard.

## Before you start

- **Python**: nothing to preinstall — `uv` provisions Python for you.
- **Admin rights**: needed only for the `winget` installs — PowerShell 7 when missing, Git, and VS Code.
- **`-ExecutionPolicy Bypass`**: scoped to that one PowerShell process; it does not change your machine's execution policy.

## Setup options

=== "Windows"

    === "Automated Setup (Recommended)"

        **Run the installer (no repo clone required)** — it works from the stock Windows PowerShell 5.1: it installs PowerShell 7 via winget (if needed) and relaunches itself under it.

        ```powershell
        powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/TheRealBillSiegler/boilerplate/main/scripts/install.ps1 | iex"
        ```

        The script sets up the full Python development environment and installs the Boilerplate CLI. It:

        - Installs **Git** and **Visual Studio Code** using `winget`, skipping either one that is already installed.  
        - Installs [the recommended set](environment/vscode.md#recommended-extensions) of VS Code extensions.
        - Installs **uv**, which will install Python and manage the virtual environment.  
        - Installs the **boilerplate** CLI using `uv tool install git+https://github.com/TheRealBillSiegler/boilerplate.git`.

        !!! tip "No manual PATH edits needed"
            The script refreshes PATH for this terminal so you can use `uv` and `boilerplate` immediately.

        ??? info "Already have the repo cloned? Run the local script instead."
            ```powershell
            powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
            ```

    === "Manual Setup"

        0. Install **PowerShell 7+**

            !!! warning "PowerShell 7+ required"
                Boilerplate assumes you are using **PowerShell 7+**. The automated path above installs this for you — this step is only needed here, in Manual Setup.

                === "Verify Installation"
                    Verify your PowerShell installation:

                    ```powershell
                    $PSVersionTable.PSVersion
                    ```

                    The **Major** version should be **>= 7**.

                === "Install PowerShell 7"

                    [Follow the official PowerShell docs](https://learn.microsoft.com/powershell/scripting/install/installing-powershell), or install via winget:

                    ```powershell
                    winget install --id Microsoft.PowerShell -e --source winget --accept-source-agreements
                    ```

        1. Install **Git** — [download for Windows](https://git-scm.com/download/win) and accept the defaults, or install via winget:

            ```powershell
            winget install --id Git.Git -e --source winget --accept-source-agreements
            ```

        2. Install **Visual Studio Code** — [download](https://code.visualstudio.com/) and install, or install via winget:

            ```powershell
            winget install --id Microsoft.VisualStudioCode -e --source winget --accept-source-agreements --override '/VERYSILENT /NORESTART /MERGETASKS="!runcode,desktopicon,addcontextmenufiles,addcontextmenufolders,associatewithfiles,addtopath"'
            ```

        3. Install **VS Code extensions**
            Ensure the `code` CLI is on your PATH, then:

            ```powershell
            $exts = @(
                'ms-python.python',
                'ms-toolsai.jupyter',
                'charliermarsh.ruff',
                'esbenp.prettier-vscode',
                'tamasfe.even-better-toml'
            )
            foreach ($e in $exts) {
                code --install-extension $e
            }
            ```

        4. Install **uv**
            Install using the [Windows instructions](https://docs.astral.sh/uv/getting-started/installation/#__tabbed_1_2).

        5. Install the **Boilerplate CLI**
            ```powershell
            uv tool install git+https://github.com/TheRealBillSiegler/boilerplate.git
            ```

        Using a private package feed? See the [Customization guide](customization.md) for the org-adoption pattern.

=== "macOS / Linux"

    !!! note "Under active verification"
        These macOS/Linux steps are under active verification — please report any issues.

    === "Manual Setup"

        1. Install **Git**

            ```bash
            # macOS
            brew install git
            # Debian / Ubuntu
            sudo apt-get install -y git
            ```

        2. Install **Visual Studio Code**
            Download and install from [code.visualstudio.com](https://code.visualstudio.com/).

        3. Install **VS Code extensions**
            Ensure the `code` CLI is installed (via "Shell Command: Install 'code' command in PATH" in VS Code), then:

            ```bash
            for e in \
                ms-python.python \
                ms-toolsai.jupyter \
                charliermarsh.ruff \
                esbenp.prettier-vscode \
                tamasfe.even-better-toml; do
                code --install-extension "$e"
            done
            ```

        4. Install **uv**
            Install using the [macOS and Linux instructions](https://docs.astral.sh/uv/getting-started/installation/#__tabbed_1_1).

        5. Install the **Boilerplate CLI**

            ```bash
            uv tool install git+https://github.com/TheRealBillSiegler/boilerplate.git
            ```

        Using a private package feed? See the [Customization guide](customization.md) for the org-adoption pattern.

See [Troubleshooting](troubleshooting.md) if you hit errors during installation.

## Organization adoption

Boilerplate itself ships with public defaults. Organizations customize in two places, both after the canonical install: point **uv** at the org feed (machine configuration), and drop a **`profile.toml`** with the org's generation defaults. See the [Customization guide](customization.md) for the pattern and a reference script.

## Verify installation

Test your boilerplate installation by getting the version.

```powershell
boilerplate --version
```

Expected: prints a semantic version and exits 0.

Verify the PATH is correct.

=== "PowerShell"

    ```powershell
    Get-Command boilerplate
    ```

    Prints a path (often `%USERPROFILE%\.local\bin\boilerplate`) if PATH is correct.

=== "bash"

    ```bash
    command -v boilerplate
    ```

    Prints a path (often `~/.local/bin/boilerplate`) if PATH is correct.

Command not found? See [Troubleshooting](troubleshooting.md) or the [FAQ](faq.md).

---

!!! success "Next steps"
    - [Read the Quickstart Guide](quickstart.md) — Create your first project and run it.
    - [Explore Boilerplate CLI Usage](cli.md) — Learn commands and workflows.
    - [Review the Environment Overview](environment/index.md) — Understand the dev stack.
