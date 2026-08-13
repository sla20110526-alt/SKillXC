[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [string]$UserHome = [Environment]::GetFolderPath('UserProfile'),
    [string]$CodexExecutable,
    [string]$PythonExecutable
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar)
}

$scriptDirectory = Get-NormalizedPath -Path $PSScriptRoot
$manifestPath = Join-Path $scriptDirectory 'install-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Missing install manifest: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $sourceCandidate = Get-NormalizedPath -Path (Join-Path $scriptDirectory '..\..')
    if (Test-Path -LiteralPath (Join-Path $sourceCandidate '.codex-plugin\plugin.json')) {
        $RepositoryRoot = $sourceCandidate
    }
    else {
        $persistentRoot = Get-NormalizedPath -Path (Join-Path $scriptDirectory '..')
        $RepositoryRoot = Get-NormalizedPath -Path (Join-Path $persistentRoot ([string]$manifest.central_repository.relative_path))
    }
}
$RepositoryRoot = Get-NormalizedPath -Path $RepositoryRoot
$UserHome = Get-NormalizedPath -Path $UserHome

if ([string]::IsNullOrWhiteSpace($CodexExecutable)) {
    $bundledCodex = Join-Path $UserHome '.codex\plugins\.plugin-appserver\codex.exe'
    if (Test-Path -LiteralPath $bundledCodex -PathType Leaf) {
        $CodexExecutable = (Get-Item -LiteralPath $bundledCodex).FullName
    }
    else {
        $codexCommand = Get-Command codex.exe -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $codexCommand) {
            $codexCommand = Get-Command codex -ErrorAction SilentlyContinue | Select-Object -First 1
        }
        if ($null -eq $codexCommand) {
            throw 'Codex CLI was not found. Install and start Codex once before runtime validation.'
        }
        $CodexExecutable = $codexCommand.Source
    }
}

if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $pythonCommand) {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if ($null -eq $pythonCommand) {
        throw 'Python 3 was not found. Install Python 3 before validating the SKillXC runtime catalog.'
    }
    $PythonExecutable = $pythonCommand.Source
}

$validator = Join-Path $scriptDirectory 'validate_codex_runtime.py'
if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) {
    throw "Missing runtime validator: $validator"
}
$contractValidator = Join-Path $RepositoryRoot 'deployment\validate_installation_contract.py'
if (-not (Test-Path -LiteralPath $contractValidator -PathType Leaf)) {
    throw "Missing installation contract validator: $contractValidator"
}

& $PythonExecutable $contractValidator --root $RepositoryRoot
if ($LASTEXITCODE -ne 0) {
    throw "SKillXC installation contract validation failed with exit code $LASTEXITCODE."
}

& $PythonExecutable $validator --root $RepositoryRoot --user-home $UserHome --codex $CodexExecutable
if ($LASTEXITCODE -ne 0) {
    throw "Codex Skill runtime validation failed with exit code $LASTEXITCODE."
}
