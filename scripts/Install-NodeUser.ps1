<#
.SYNOPSIS
    Installs or uninstalls Node.js for the current user on Windows, with no admin rights required.

.DESCRIPTION
    This script automates downloading, verifying, installing, and uninstalling Node.js for the current user
    (no elevation required). It securely fetches the requested version from nodejs.org, verifies its SHA256 checksum,
    extracts the files to a user-local directory, and updates PATH and NODEJS_HOME in the user environment.
    Global npm installs are configured to use a user-local directory.

    Uninstallation removes all files and user environment changes for the chosen version/architecture.

.PARAMETER Version
    Node.js version to install (e.g., 'lts', 'current', or '22.7.0'). Default is 'lts' (latest LTS).

.PARAMETER Architecture
    CPU architecture: 'x64' (default) or 'arm64'. If not specified, the script detects the OS architecture.

.PARAMETER InstallRoot
    Directory in which to install Node.js. Default: $env:LOCALAPPDATA\Programs\nodejs

.PARAMETER NpmPrefix
    User-global npm prefix directory. Default: $env:LOCALAPPDATA\npm

.PARAMETER Uninstall
    If set, removes Node.js and all related user environment changes for the specified version and architecture.

.PARAMETER Force
    If set, forces overwrite of an existing installation.

.EXAMPLE
    .\Install-NodeUser.ps1
    Installs the latest LTS version of Node.js for the current user.

.EXAMPLE
    .\Install-NodeUser.ps1 -Version 22.7.0 -Uninstall
    Uninstalls Node.js version 22.7.0 for the current user.

.NOTES
    - Requires PowerShell 7.0 or later.
    - Designed for Windows only (x64 or ARM64).
    - All changes are local to the user profile and reversible.
    - Exits with code 0 on success, 1 on error.
#>

[CmdletBinding()]
param(
    [Parameter()] [string]$Version = 'lts',
    [Parameter()] [ValidateSet('x64','arm64')] [string]$Architecture,
    [Parameter()] [string]$InstallRoot = "$env:LOCALAPPDATA\Programs\nodejs",
    [Parameter()] [string]$NpmPrefix = "$env:LOCALAPPDATA\npm",
    [Parameter()] [switch]$Uninstall,
    [Parameter()] [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

#-----------------------------------------------------------
function Resolve-NodeVersion {
<#
.SYNOPSIS
    Resolves a Node.js version specifier to a concrete version string.

.DESCRIPTION
    Given 'lts', 'current', 'lts/<codename>', or a version string,
    fetches the nodejs.org version index and determines the precise version number.

.PARAMETER Requested
    The requested version specifier (e.g., 'lts', 'current', '20.10.0', 'lts/iron').

.OUTPUTS
    [string] Version number (e.g., '22.7.0').

.EXAMPLE
    Resolve-NodeVersion -Requested 'lts'
#>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Requested)

    $index = Invoke-RestMethod -Uri 'https://nodejs.org/dist/index.json' -TimeoutSec 30
    switch ($Requested) {
        'current' { return $index[0].version.TrimStart('v') }
        'lts'     { return ($index | Where-Object { $_.lts } | Select-Object -First 1).version.TrimStart('v') }
        { $_ -like 'lts/*' } {
            $codename = $Requested.Split('/')[1]
            $match = $index | Where-Object { $_.lts -eq $codename } | Select-Object -First 1
            if (-not $match) { throw "LTS '$codename' not found." }
            return $match.version.TrimStart('v')
        }
        Default { return ($Requested -replace '^v','') }
    }
}
#-----------------------------------------------------------
function Get-NodeDownloadUrl {
<#
.SYNOPSIS
    Returns the official download URL for the specified Node.js version and architecture.

.PARAMETER Version
    Node.js version string (e.g., '22.7.0').

.PARAMETER Arch
    CPU architecture: 'x64' or 'arm64'.

.OUTPUTS
    [string] Download URL.

.EXAMPLE
    Get-NodeDownloadUrl -Version '22.7.0' -Arch 'x64'
#>
    param([string]$Version, [string]$Arch)
    "https://nodejs.org/dist/v$Version/node-v$Version-win-$Arch.zip"
}
#-----------------------------------------------------------
function Invoke-NodeDownload {
<#
.SYNOPSIS
    Downloads a file from the given URL to a specified output path.

.PARAMETER Url
    The URL to download.

.PARAMETER OutFile
    The file path to save the download.

.EXAMPLE
    Invoke-NodeDownload -Url $url -OutFile $zipPath
#>
    param([string]$Url, [string]$OutFile)
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -TimeoutSec 600
}
#-----------------------------------------------------------
function Test-NodeChecksum {
<#
.SYNOPSIS
    Validates the SHA256 checksum of the downloaded Node.js ZIP.

.DESCRIPTION
    Downloads SHASUMS256.txt from nodejs.org for the specified version,
    finds the expected checksum for the ZIP, and compares it with the actual file.

.PARAMETER FilePath
    Path to the downloaded ZIP.

.PARAMETER Version
    Node.js version (e.g., '22.7.0').

.PARAMETER Arch
    CPU architecture.

.EXAMPLE
    Test-NodeChecksum -FilePath $zip -Version $ver -Arch $arch
#>
    param([string]$FilePath, [string]$Version, [string]$Arch)
    $shasums = Invoke-RestMethod -Uri "https://nodejs.org/dist/v$Version/SHASUMS256.txt" -TimeoutSec 30
    $pattern = "([a-f0-9]{64})\s+node-v$Version-win-$Arch.zip"
    $expected = ($shasums -split "`n" | Where-Object { $_ -match $pattern }) -replace $pattern, '$1'
    if (-not $expected) { throw "SHA256 not found for this ZIP in SHASUMS256.txt." }
    $actual = (Get-FileHash -Path $FilePath -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $expected.ToLower()) { throw "Checksum mismatch. Expected $expected, got $actual." }
}
#-----------------------------------------------------------
function Expand-NodeArchive {
<#
.SYNOPSIS
    Extracts the Node.js ZIP archive to the installation directory.

.DESCRIPTION
    Extracts to a temporary directory first, then moves the actual node-v* folder to the final install location.

.PARAMETER ZipPath
    Path to the ZIP file.

.PARAMETER InstallDir
    The final directory for Node.js installation.

.EXAMPLE
    Expand-NodeArchive -ZipPath $zip -InstallDir $dir
#>
    param([string]$ZipPath, [string]$InstallDir)
    $temp = Join-Path $env:TEMP "node-extract-$(Get-Random)"
    Expand-Archive -Path $ZipPath -DestinationPath $temp -Force

    $folder = Get-ChildItem $temp -Directory | Select-Object -First 1
    if (-not $folder) { throw "Extraction failed (archive may be corrupt)." }

    # Remove old install dir if exists
    if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }

    # Ensure parent exists
    $parent = Split-Path $InstallDir -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }

    # Move the extracted directory to the install location (rename)
    Move-Item -Path $folder.FullName -Destination $InstallDir -Force

    # Clean up temp extraction dir
    Remove-Item $temp -Recurse -Force
}
#-----------------------------------------------------------
function Set-NodeUserEnvironment {
<#
.SYNOPSIS
    Updates user environment variables for Node.js and npm.

.DESCRIPTION
    Sets NODEJS_HOME and updates the user PATH to include the Node.js install directory and npm global prefix.
    Configures npm to use the user-specific prefix.

.PARAMETER InstallDir
    Node.js installation directory.

.PARAMETER NpmPrefix
    Directory for global npm packages.

.EXAMPLE
    Set-NodeUserEnvironment -InstallDir $dir -NpmPrefix $prefix
#>
    param([string]$InstallDir, [string]$NpmPrefix)
    [Environment]::SetEnvironmentVariable('NODEJS_HOME', $InstallDir, 'User')
    $userPath = [Environment]::GetEnvironmentVariable('Path','User') -split ';'
    $filtered = $userPath | Where-Object { $_ -and $_ -ne $InstallDir -and $_ -ne $NpmPrefix }
    $newPath = "$InstallDir;$NpmPrefix;" + ($filtered -join ';')
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    # Configure npm global prefix (if npm exists yet)
    $npm = Join-Path $InstallDir 'npm.cmd'
    if (Test-Path $npm) { & $npm config set prefix $NpmPrefix | Out-Null }
}
#-----------------------------------------------------------
function Remove-NodeUserEnvironment {
<#
.SYNOPSIS
    Removes Node.js installation and all related user environment changes.

.DESCRIPTION
    Deletes the install directory and removes it and npm prefix from the user's PATH and NODEJS_HOME.

.PARAMETER InstallDir
    Node.js install directory.

.PARAMETER NpmPrefix
    Directory for global npm packages.

.EXAMPLE
    Remove-NodeUserEnvironment -InstallDir $dir -NpmPrefix $prefix
#>
    param([string]$InstallDir, [string]$NpmPrefix)
    if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
    $userPath = [Environment]::GetEnvironmentVariable('Path','User') -split ';'
    $filtered = $userPath | Where-Object { $_ -and $_ -ne $InstallDir -and $_ -ne $NpmPrefix }
    [Environment]::SetEnvironmentVariable('Path', ($filtered -join ';'), 'User')
    [Environment]::SetEnvironmentVariable('NODEJS_HOME', $null, 'User')
}
#-----------------------------------------------------------
function Test-NodeUserInstall {
<#
.SYNOPSIS
    Verifies that Node.js is installed and functional.

.DESCRIPTION
    Checks for the presence of node.exe and verifies its version.

.PARAMETER InstallDir
    Directory where Node.js should be installed.

.PARAMETER Version
    Expected Node.js version string.

.OUTPUTS
    [bool] True if the installation is correct.

.EXAMPLE
    Test-NodeUserInstall -InstallDir $dir -Version $ver
#>
    param([string]$InstallDir, [string]$Version)
    $node = Join-Path $InstallDir 'node.exe'
    if (-not (Test-Path $node)) { return $false }
    $ver = & $node --version 2>$null
    return ($ver -replace '^v','') -eq $Version
}
#-----------------------------------------------------------

# --- Architecture detection ---
if (-not $Architecture) {
    $Architecture = if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -eq 'Arm64') { 'arm64' } else { 'x64' }
}

# --- Main Logic ---

try {
    $resolvedVersion = Resolve-NodeVersion $Version
    $zipName = "node-v$resolvedVersion-win-$Architecture.zip"
    $zipPath = Join-Path $env:TEMP $zipName
    $installDir = Join-Path $InstallRoot "v$resolvedVersion\win-$Architecture"

    if ($Uninstall) {
        Remove-NodeUserEnvironment -InstallDir $installDir -NpmPrefix $NpmPrefix
        Write-Host "✅ Node.js $resolvedVersion uninstalled for current user." -ForegroundColor Green
        exit 0
    }

    if ($Force -and (Test-Path $installDir)) {
        Remove-Item $installDir -Recurse -Force
    }

    Write-Host "⏬ Downloading Node.js $resolvedVersion ($Architecture)..."
    Invoke-NodeDownload -Url (Get-NodeDownloadUrl -Version $resolvedVersion -Arch $Architecture) -OutFile $zipPath

    Write-Host "🔑 Verifying checksum..."
    Test-NodeChecksum -FilePath $zipPath -Version $resolvedVersion -Arch $Architecture

    Write-Host "📦 Extracting..."
    Expand-NodeArchive -ZipPath $zipPath -InstallDir $installDir

    Remove-Item $zipPath -Force

    Write-Host "🔧 Updating user environment..."
    Set-NodeUserEnvironment -InstallDir $installDir -NpmPrefix $NpmPrefix

    if (Test-NodeUserInstall -InstallDir $installDir -Version $resolvedVersion) {
        Write-Host "`n✅ Node.js $resolvedVersion installed for current user." -ForegroundColor Green
        Write-Host "   Install location: $installDir"
        Write-Host "   Npm global prefix: $NpmPrefix"
        Write-Host "   Please reopen your terminal for PATH changes to take effect."
        exit 0
    } else {
        Write-Error "Installation failed or Node.js is not functioning as expected."
        exit 1
    }
} catch {
    Write-Host "`n❌ ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
