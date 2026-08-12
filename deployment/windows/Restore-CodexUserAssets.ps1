[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [string]$UserHome = [Environment]::GetFolderPath('UserProfile')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar)
}

function Get-LinkTargetPath {
    param([Parameter(Mandatory = $true)][IO.FileSystemInfo]$Item)
    $targets = @($Item.Target)
    if ($targets.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$targets[0])) {
        return $null
    }
    return Get-NormalizedPath -Path ([string]$targets[0])
}

function Test-ExactJunction {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Target
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $item = Get-Item -LiteralPath $Path -Force
    if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        return $false
    }
    $actualTarget = Get-LinkTargetPath -Item $item
    if ($null -eq $actualTarget) {
        return $false
    }
    return $actualTarget -ieq (Get-NormalizedPath -Path $Target)
}

function Ensure-Junction {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Target
    )
    if (Test-ExactJunction -Path $Path -Target $Target) {
        return
    }
    if (Test-Path -LiteralPath $Path) {
        $item = Get-Item -LiteralPath $Path -Force
        if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Refusing to replace a real file or directory: $Path"
        }
        Remove-Item -LiteralPath $Path -Force
    }
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    New-Item -ItemType Junction -Path $Path -Target $Target | Out-Null
}

function Test-CodexEntryLayout {
    param(
        [Parameter(Mandatory = $true)][string]$Entry,
        [Parameter(Mandatory = $true)][string]$PersistentRoot,
        [Parameter(Mandatory = $true)][string]$PersistentSkills,
        [Parameter(Mandatory = $true)][string]$PersistentPlugins
    )
    if (Test-ExactJunction -Path $Entry -Target $PersistentRoot) {
        return $true
    }
    if (-not (Test-Path -LiteralPath $Entry)) {
        return $false
    }
    $item = Get-Item -LiteralPath $Entry -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        return $false
    }
    return (Test-ExactJunction -Path (Join-Path $Entry 'skills') -Target $PersistentSkills) -and
        (Test-ExactJunction -Path (Join-Path $Entry 'plugins') -Target $PersistentPlugins)
}

function Get-FileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try {
        $hash = $algorithm.ComputeHash($stream)
        return ([BitConverter]::ToString($hash)).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

function Get-TreeIntegrity {
    param([Parameter(Mandatory = $true)][string]$Root)
    $normalizedRoot = Get-NormalizedPath -Path $Root
    $files = @(Get-ChildItem -LiteralPath $normalizedRoot -Recurse -File -Force)
    $relativePaths = [string[]]@($files | ForEach-Object {
        $_.FullName.Substring($normalizedRoot.Length + 1)
    })
    [Array]::Sort($relativePaths, [StringComparer]::Ordinal)

    $builder = New-Object Text.StringBuilder
    $byteCount = [long]0
    foreach ($relativePath in $relativePaths) {
        $filePath = Join-Path $normalizedRoot $relativePath
        $file = Get-Item -LiteralPath $filePath -Force
        $byteCount += [long]$file.Length
        $portablePath = $relativePath.Replace('\', '/')
        [void]$builder.Append((Get-FileSha256 -Path $filePath))
        [void]$builder.Append('  ')
        [void]$builder.Append($portablePath)
        [void]$builder.Append("`n")
    }

    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($builder.ToString())
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $treeHash = ([BitConverter]::ToString($algorithm.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $algorithm.Dispose()
    }

    return [pscustomobject]@{
        FileCount = $relativePaths.Count
        ByteCount = $byteCount
        TreeSha256 = $treeHash
    }
}

$recoveryDirectory = Get-NormalizedPath -Path $PSScriptRoot
$persistentRoot = Get-NormalizedPath -Path (Join-Path $recoveryDirectory '..')
$manifestPath = Join-Path $recoveryDirectory 'install-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Missing install manifest: $manifestPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$centralRepository = Get-NormalizedPath -Path (Join-Path $persistentRoot ([string]$manifest.central_repository.relative_path))
$centralSkills = Join-Path $centralRepository 'skills'
$persistentSkills = Join-Path $persistentRoot 'skills'
$persistentPlugins = Join-Path $persistentRoot 'plugins'
$pluginSources = Join-Path $persistentPlugins 'plugins'
$marketplacePath = Join-Path $persistentPlugins 'marketplace.json'
$codexEntry = Join-Path (Get-NormalizedPath -Path $UserHome) '.agents'

if (-not (Test-Path -LiteralPath $centralSkills)) {
    throw "Central repository skills are missing: $centralSkills"
}

$centralSkillDirectories = @(Get-ChildItem -LiteralPath $centralSkills -Directory | Sort-Object Name)
if ($centralSkillDirectories.Count -ne [int]$manifest.central_skill_count) {
    throw "Central skill count mismatch. Expected $($manifest.central_skill_count), found $($centralSkillDirectories.Count)."
}

foreach ($localSkillName in @($manifest.local_skills)) {
    $localSkillPath = Join-Path $persistentSkills ([string]$localSkillName)
    if (-not (Test-Path -LiteralPath (Join-Path $localSkillPath 'SKILL.md'))) {
        throw "Persistent local skill is missing: $localSkillPath"
    }
}

if (-not (Test-Path -LiteralPath $marketplacePath)) {
    throw "Personal marketplace is missing: $marketplacePath"
}
if (-not (Test-Path -LiteralPath (Join-Path $pluginSources 'cowart\.codex-plugin\plugin.json'))) {
    throw "Persistent Cowart plugin source is missing."
}

foreach ($integrityRecord in @($manifest.integrity)) {
    $integrityPath = Get-NormalizedPath -Path (Join-Path $persistentRoot ([string]$integrityRecord.relative_path))
    if (-not (Test-Path -LiteralPath $integrityPath)) {
        throw "Integrity target is missing: $integrityPath"
    }
    $actualIntegrity = Get-TreeIntegrity -Root $integrityPath
    if ($actualIntegrity.FileCount -ne [int]$integrityRecord.file_count -or
        $actualIntegrity.ByteCount -ne [long]$integrityRecord.byte_count -or
        $actualIntegrity.TreeSha256 -ine [string]$integrityRecord.tree_sha256) {
        throw "Integrity check failed: $($integrityRecord.name)"
    }
}

if (-not $ValidateOnly) {
    foreach ($skillDirectory in $centralSkillDirectories) {
        Ensure-Junction -Path (Join-Path $persistentSkills $skillDirectory.Name) -Target $skillDirectory.FullName
    }
    Ensure-Junction -Path (Join-Path $pluginSources 'skillxc') -Target $centralRepository

    if (-not (Test-CodexEntryLayout -Entry $codexEntry -PersistentRoot $persistentRoot -PersistentSkills $persistentSkills -PersistentPlugins $persistentPlugins)) {
        if (Test-Path -LiteralPath $codexEntry) {
            $item = Get-Item -LiteralPath $codexEntry -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "The Codex user entry points somewhere else: $codexEntry"
            }
            $nonDirectoryEntries = @(Get-ChildItem -LiteralPath $codexEntry -Force -Recurse | Where-Object {
                -not $_.PSIsContainer -or ($_.Attributes -band [IO.FileAttributes]::ReparsePoint)
            })
            if ($nonDirectoryEntries.Count -ne 0) {
                throw "The Codex user entry is not empty. Back it up before recovery: $codexEntry"
            }
            Remove-Item -LiteralPath $codexEntry -Recurse -Force
            New-Item -ItemType Junction -Path $codexEntry -Target $persistentRoot | Out-Null
        }
        else {
            New-Item -ItemType Junction -Path $codexEntry -Target $persistentRoot | Out-Null
        }
    }
}

$errors = New-Object System.Collections.Generic.List[string]
foreach ($skillDirectory in $centralSkillDirectories) {
    $installedSkill = Join-Path $persistentSkills $skillDirectory.Name
    if (-not (Test-ExactJunction -Path $installedSkill -Target $skillDirectory.FullName)) {
        $errors.Add("Invalid central skill junction: $installedSkill")
    }
    elseif (-not (Test-Path -LiteralPath (Join-Path $installedSkill 'SKILL.md'))) {
        $errors.Add("Missing SKILL.md through junction: $installedSkill")
    }
}

if (-not (Test-ExactJunction -Path (Join-Path $pluginSources 'skillxc') -Target $centralRepository)) {
    $errors.Add('Invalid skillxc plugin junction.')
}
if (-not (Test-CodexEntryLayout -Entry $codexEntry -PersistentRoot $persistentRoot -PersistentSkills $persistentSkills -PersistentPlugins $persistentPlugins)) {
    $errors.Add("Invalid Codex user entry: $codexEntry")
}

try {
    $marketplace = Get-Content -LiteralPath $marketplacePath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($pluginName in @($manifest.plugins | ForEach-Object { [string]$_.name })) {
        $entries = @($marketplace.plugins | Where-Object { $_.name -eq $pluginName })
        if ($entries.Count -ne 1) {
            $errors.Add("Marketplace entry count is not one for plugin: $pluginName")
        }
    }
}
catch {
    $errors.Add("Marketplace JSON is invalid: $($_.Exception.Message)")
}

if ($errors.Count -gt 0) {
    foreach ($message in $errors) {
        Write-Error $message
    }
    throw "Recovery validation failed with $($errors.Count) error(s)."
}

Write-Host "Persistent root: $persistentRoot"
Write-Host "Codex user entry: $codexEntry"
Write-Host "Central skills validated: $($centralSkillDirectories.Count)"
Write-Host "Local skills validated: $(@($manifest.local_skills).Count)"
Write-Host "Plugins validated: $(@($manifest.plugins).Count)"
Write-Host "Persistent trees verified: $(@($manifest.integrity).Count)"
Write-Host 'Recovery validation passed.'
