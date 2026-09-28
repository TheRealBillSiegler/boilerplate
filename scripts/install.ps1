#Requires -Version 7

# Runtime guard: '#Requires' is ignored when this script is piped to iex, and
# under Windows PowerShell 5.1 the native-command error trapping below is
# inert, so a failed install step would still report success. Self-heal:
# hop to an existing pwsh, installing PowerShell 7 first if needed; fail
# closed only when neither works. This block, and the whole file, must stay
# parseable by 5.1.
if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwshDefault = Join-Path $env:ProgramFiles 'PowerShell\7\pwsh.exe'

    $pwsh = $null
    $pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($pwshCmd) { $pwsh = $pwshCmd.Source }
    elseif (Test-Path $pwshDefault) { $pwsh = $pwshDefault }

    if (-not $pwsh -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host 'PowerShell 7 not found. Installing it via winget...' -ForegroundColor Yellow
        winget install --id Microsoft.PowerShell -e --source winget --accept-source-agreements
        # The new install is not on this session's PATH yet.
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
            [Environment]::GetEnvironmentVariable('Path', 'User')
        $pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
        if ($pwshCmd) { $pwsh = $pwshCmd.Source }
        elseif (Test-Path $pwshDefault) { $pwsh = $pwshDefault }
    }

    if (-not $pwsh) {
        Write-Host 'This installer requires PowerShell 7+ and could not install it automatically.' -ForegroundColor Red
        Write-Host 'Install it first:'
        Write-Host '  winget install --id Microsoft.PowerShell --accept-source-agreements'
        Write-Host "then re-run the install command in a new 'pwsh' window."
        exit 1
    }

    Write-Host "Relaunching under PowerShell 7 ($pwsh)..." -ForegroundColor Cyan
    if ($PSCommandPath) {
        & $pwsh -ExecutionPolicy Bypass -File $PSCommandPath
    }
    else {
        # Piped via iex: there is no script file on disk to relaunch, so
        # re-fetch from the canonical URL.
        & $pwsh -ExecutionPolicy Bypass -Command "irm 'https://raw.githubusercontent.com/TheRealBillSiegler/boilerplate/main/scripts/install.ps1' | iex"
    }
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'
# Make native commands that exit non-zero raise a terminating error, so the
# try/catch blocks below actually catch failed installs. Default-on in 7.4+;
# set explicitly so 7.3 behaves the same.
$PSNativeCommandUseErrorActionPreference = $true

<#
.SYNOPSIS
Sets up the canonical boilerplate Python development environment on a Windows
machine: Visual Studio Code (+ extensions), Git, uv, and the boilerplate CLI.

.DESCRIPTION
- Installs VS Code (if needed) and the boilerplate-certified extensions.
- Installs Git (if needed).
- Installs uv (Astral's installer).
- Installs the boilerplate CLI from its public Git repository.

This is the public, open-source installer: one path, no organization- or
feed-specific configuration. Organizations that resolve packages from a private
index run this script first, then layer their own uv configuration on top.

winget is invoked with --accept-source-agreements, which accepts winget's source
(feed) terms on your behalf so the install runs unattended. No third-party package
license agreements (EULAs) are auto-accepted.

Requires PowerShell 7+.

.EXAMPLE
pwsh -ExecutionPolicy Bypass -File .\install.ps1
#>

################################################################################
# Function: Test-ToolInstalled
################################################################################
function Test-ToolInstalled {
    <#
    .SYNOPSIS
    Reports whether winget lists a tool as installed, judged by presence in the
    output rather than the exit code.

    .DESCRIPTION
    `winget list` exits non-zero when its filter matches nothing, which is the
    normal "not installed" signal. Under $PSNativeCommandUseErrorActionPreference
    that non-zero exit would raise a terminating error, so it is suppressed
    within this function's scope; the decision is made purely on whether $ToolId
    appears in the listing.

    .PARAMETER ToolId
    The winget identifier to check (e.g., "Microsoft.VisualStudioCode").

    .EXAMPLE
    if (Test-ToolInstalled -ToolId "Git.Git") { "already here" }
    #>
    [CmdletBinding()]
    param (
        [Parameter(Mandatory)]
        [string]$ToolId
    )

    # Local to this scope: a "no packages found" exit is expected, not a failure.
    $PSNativeCommandUseErrorActionPreference = $false
    $listing = winget list --id $ToolId -e --source winget --accept-source-agreements 2>$null
    return [bool]($listing -match $ToolId)
}

################################################################################
# Function: Install-Tool
################################################################################
function Install-Tool {
    <#
    .SYNOPSIS
    Installs a tool via winget if it's not already installed.

    .PARAMETER ToolId
    The winget identifier of the tool (e.g., "Microsoft.VisualStudioCode").

    .PARAMETER Override
    Optional command-line arguments for the winget installer.

    .EXAMPLE
    Install-Tool -ToolId "Microsoft.VisualStudioCode" -Override '/VERYSILENT /NORESTART /MERGETASKS="!runcode,desktopicon,addcontextmenufiles,addcontextmenufolders,associatewithfiles,addtopath"'
    #>
    [CmdletBinding()]
    param (
        [Parameter(Mandatory)]
        [string]$ToolId,

        [Parameter()]
        [string]$Override = ""
    )

    Write-Host "Checking if $ToolId is installed..." -ForegroundColor Cyan

    # Check if winget is available
    if (-not (Get-Command "winget" -ErrorAction SilentlyContinue)) {
        Write-Host "winget is not available on this system. Assuming $ToolId is already installed." -ForegroundColor Yellow
        return
    }

    # Check if the tool is already installed.
    if (Test-ToolInstalled -ToolId $ToolId) {
        Write-Host "$ToolId is already installed." -ForegroundColor Green
    }
    else {
        Write-Host "$ToolId not found. Installing..." -ForegroundColor Yellow
        try {
            # Build arguments array. Accept the winget *source* (feed) terms so the
            # first winget call doesn't prompt on a fresh machine. Package EULAs are
            # deliberately NOT auto-accepted (--accept-package-agreements omitted).
            $wingetArgs = @("install", "--id", $ToolId, "-e", "--source", "winget",
                "--accept-source-agreements")
            if ($Override) {
                $wingetArgs += "--override", $Override
            }

            # winget exits non-zero on benign outcomes (reboot required, etc.);
            # let the presence check below judge success, not the exit code. Local
            # to this scope, same as Test-ToolInstalled.
            $PSNativeCommandUseErrorActionPreference = $false
            Write-Host "Executing: winget $($wingetArgs -join ' ')" -ForegroundColor Cyan
            winget @wingetArgs

            Update-Path

            # Verify by presence, not exit code: winget can report quirky codes.
            if (Test-ToolInstalled -ToolId $ToolId) {
                Write-Host "$ToolId has been successfully installed." -ForegroundColor Green
            }
            else {
                throw "$ToolId installation did not complete (not found after install)."
            }
        }
        catch {
            Write-Host "Failed to install $ToolId. Error: $_" -ForegroundColor Red
            throw
        }
    }
}

################################################################################
# Function: Install-VSCodeExtensions
################################################################################
function Install-VSCodeExtensions {
    <#
    .SYNOPSIS
    Installs specified Visual Studio Code extensions if they're not already installed.

    .PARAMETER Extensions
    An array of VS Code extension IDs.

    .EXAMPLE
    Install-VSCodeExtensions -Extensions @("ms-python.python", "ms-toolsai.jupyter")
    #>
    [CmdletBinding()]
    param (
        [Parameter(Mandatory)]
        [array]$Extensions
    )

    Write-Host "Checking VS Code installation..." -ForegroundColor Cyan

    # Check if the `code` command is available. -ErrorAction SilentlyContinue so a
    # missing `code` falls through to the warning instead of throwing under Stop.
    if (-not (Get-Command "code" -ErrorAction SilentlyContinue)) {
        Write-Host "Visual Studio Code CLI (code) is not available on PATH; skipping extensions." -ForegroundColor Yellow
        return
    }

    Write-Host "Checking already installed extensions..." -ForegroundColor Cyan

    # Get the list of currently installed extensions
    $installedExtensions = code --list-extensions 2>&1
    $toInstall = $Extensions | Where-Object { $_ -notin $installedExtensions }

    if ($toInstall.Count -eq 0) {
        Write-Host "All specified extensions are already installed. No action needed." -ForegroundColor Green
        return
    }

    Write-Host "Installing missing extensions..." -ForegroundColor Cyan

    try {
        # Create a list of arguments for the `code` command
        $codeArgs = @()
        foreach ($extension in $toInstall) {
            $codeArgs += "--install-extension", $extension
        }

        # Execute the command with all extensions
        code @codeArgs
        Write-Host "VS Code extension installation completed." -ForegroundColor Green
    }
    catch {
        Write-Host "An error occurred while installing extensions. Error: $_" -ForegroundColor Red
        throw
    }
}

################################################################################
# Function: Update-Path
################################################################################
function Update-Path {
    <#
    .SYNOPSIS
    Updates the current session PATH to include newly installed tools.

    .EXAMPLE
    Update-Path
    #>
    [CmdletBinding()]
    param ()

    [System.Environment]::SetEnvironmentVariable(
        "Path",
        [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
        [System.Environment]::GetEnvironmentVariable("Path", "User"),
        "Process"
    )
    Write-Host "PATH has been updated for this session." -ForegroundColor Cyan
}

################################################################################
# Script Execution
################################################################################

Write-Host "Starting Boilerplate environment setup..." -ForegroundColor Magenta

try {
    # 1. Install VS Code
    Install-Tool -ToolId "Microsoft.VisualStudioCode" -Override '/VERYSILENT /NORESTART /MERGETASKS="!runcode,desktopicon,addcontextmenufiles,addcontextmenufolders,associatewithfiles,addtopath"'

    # 2. Install VS Code extensions
    $VSCodeExtensions = @(
        "ms-python.python",
        "ms-toolsai.jupyter",
        "charliermarsh.ruff",
        "esbenp.prettier-vscode",
        "tamasfe.even-better-toml"
    )
    Install-VSCodeExtensions -Extensions $VSCodeExtensions

    # 3. Install Git
    Install-Tool -ToolId "Git.Git"

    # 4. Install uv
    Write-Host "Installing uv (via Astral's official install script)..." -ForegroundColor Cyan
    try {
        $ScriptUrl = "https://astral.sh/uv/install.ps1"
        $ScriptContent = Invoke-RestMethod -Uri $ScriptUrl
        Invoke-Expression $ScriptContent
        Write-Host "uv installed successfully." -ForegroundColor Green
        Write-Host "Ignore the message about adding to PATH. It is not needed." -ForegroundColor Yellow
        Update-Path
    }
    catch {
        Write-Host "Failed to install uv. Error: $_" -ForegroundColor Red
        throw
    }

    # 5. Install boilerplate from the public Git repo. The bare PyPI name
    #    `boilerplate` is an unrelated project (see adr-008), so install by URL.
    Write-Host "Installing boilerplate..." -ForegroundColor Cyan
    try {
        uv tool install git+https://github.com/TheRealBillSiegler/boilerplate.git
        Write-Host "Boilerplate installed." -ForegroundColor Green
    }
    catch {
        Write-Host "Failed to install boilerplate. Error: $_" -ForegroundColor Red
        throw
    }

    Write-Host "Boilerplate environment setup completed successfully." -ForegroundColor Magenta
}
catch {
    Write-Host "Script encountered a critical error and will exit. Error: $_" -ForegroundColor Red
    exit 1
}
