$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$PysideVersion = "6.12.0"
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Settings = if ($env:KEYMASTER_SETTINGS) { $env:KEYMASTER_SETTINGS } else { Join-Path $env:APPDATA "Keymaster\settings.json" }

$Data = $null
if (Test-Path -LiteralPath $Settings) {
    try { $Data = Get-Content -LiteralPath $Settings -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $Data = $null }
}

function Setting([string]$Name) {
    if ($Data -and $Data.PSObject.Properties[$Name]) { return [string]$Data.$Name }
    return ""
}

$Language = if ($env:KEYMASTER_LANGUAGE) { $env:KEYMASTER_LANGUAGE } else { Setting "language" }
if (-not $Language) {
    $Language = if ((Get-Culture).TwoLetterISOLanguageName -eq "es") { "es-419" } else { "en" }
}
if ($Language -ne "es-419") { $Language = "en" }

function Load-Table([string]$Lang) {
    $table = @{}
    $path = Join-Path $AppDir "i18n\$Lang.json"
    if (Test-Path -LiteralPath $path) {
        $json = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($p in $json.PSObject.Properties) { $table[$p.Name] = [string]$p.Value }
    }
    return $table
}

$Tables = @{ "en" = (Load-Table "en"); "es-419" = (Load-Table "es-419") }

function msg([string]$Key, [hashtable]$Params = @{}, [string]$Lang = $Language) {
    $text = $Tables[$Lang][$Key]
    if (-not $text) { $text = $Key }
    foreach ($name in $Params.Keys) { $text = $text.Replace("{$name}", [string]$Params[$name]) }
    return $text
}

function say([string]$Key, [hashtable]$Params = @{}) {
    Write-Host (msg $Key $Params)
}

function Fail([string]$Key, [hashtable]$Params = @{}) {
    [Console]::Error.WriteLine((msg $Key $Params))
    exit 1
}

$Python = if ($env:KEYMASTER_PYTHON) { $env:KEYMASTER_PYTHON } else { Setting "python" }
$Core = if ($env:KEYMASTER_CORE) { $env:KEYMASTER_CORE } else { Setting "core" }

if (-not $Core -or -not (Test-Path -LiteralPath (Join-Path $Core "keymaster") -PathType Container)) {
    Fail "app.install.no_core" @{ path = $Settings }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    $shown = if ($Python) { $Python } else { "?" }
    Fail "app.install.bad_python" @{ path = $shown }
}

function Invoke-Quiet([string]$Exe, [string[]]$Arguments) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Exe @Arguments *> $null; return ($LASTEXITCODE -eq 0) } catch { return $false } finally { $ErrorActionPreference = $previous }
}

function Invoke-Loud([string]$Exe, [string[]]$Arguments) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Exe @Arguments; return ($LASTEXITCODE -eq 0) } catch { return $false } finally { $ErrorActionPreference = $previous }
}

$Spec = "PySide6-Essentials==$PysideVersion"
$check = "import sys, PySide6; sys.exit(PySide6.__version__ != '$PysideVersion')"
if (Invoke-Quiet $Python @("-c", $check)) {
    say "app.install.already" @{ version = $PysideVersion }
} else {
    say "app.install.installing" @{ version = $PysideVersion }
    $ok = $false
    if (Invoke-Quiet $Python @("-m", "pip", "--version")) {
        $ok = Invoke-Loud $Python @("-m", "pip", "install", "--upgrade", $Spec)
    } elseif (Get-Command uv -ErrorAction SilentlyContinue) {
        $ok = Invoke-Loud "uv" @("pip", "install", "--python", $Python, $Spec)
    } elseif (Invoke-Loud $Python @("-m", "ensurepip", "--upgrade")) {
        $ok = Invoke-Loud $Python @("-m", "pip", "install", "--upgrade", $Spec)
    }
    if (-not $ok) { Fail "app.install.pip_failed" }
}

$PythonW = Join-Path (Split-Path -Parent $Python) "pythonw.exe"
if (-not (Test-Path -LiteralPath $PythonW)) { $PythonW = $Python }

$Launcher = Join-Path $AppDir "keymaster-app.bat"
$bat = @(
    "@echo off",
    "chcp 65001 >nul",
    "set ""PYTHONPATH=%~dp0;%PYTHONPATH%""",
    "start """" ""$PythonW"" -m keymaster_app %*"
)
[System.IO.File]::WriteAllLines($Launcher, [string[]]$bat, (New-Object System.Text.UTF8Encoding($false)))
say "app.install.launcher" @{ path = $Launcher }

$Programs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
New-Item -ItemType Directory -Force -Path $Programs | Out-Null
$Shell = New-Object -ComObject WScript.Shell
$Link = $Shell.CreateShortcut((Join-Path $Programs "Keymaster.lnk"))
$Link.TargetPath = $PythonW
$Link.Arguments = "-m keymaster_app"
$Link.WorkingDirectory = $AppDir
$Link.Description = msg "app.desktop.comment"
$Link.Save()
say "app.install.shortcut"
say "app.install.done"
