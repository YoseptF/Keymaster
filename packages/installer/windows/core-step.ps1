param(
    [Parameter(Mandatory = $true)][ValidateSet("ffmpeg", "core", "settings", "app", "doctor")][string]$Action,
    [Parameter(Mandatory = $true)][string]$InstallDir,
    [string]$FfmpegUrl = "",
    [string]$FfmpegSha256 = ""
)
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::Default } catch { }
$env:PYTHONIOENCODING = "$([System.Text.Encoding]::Default.WebName):replace"

$Core = Join-Path $InstallDir "core"
$Py = Join-Path $Core ".venv\Scripts\python.exe"
$FfmpegDir = Join-Path $InstallDir "ffmpeg"
$Ffmpeg = Join-Path $FfmpegDir "bin\ffmpeg.exe"
$Log = Join-Path $InstallDir "logs\install.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Log) | Out-Null

$env:PATH = (Join-Path $InstallDir "bin") + ";" + $env:PATH
$env:UV_PYTHON_INSTALL_DIR = Join-Path $InstallDir "python"
$env:UV_PYTHON_PREFERENCE = "only-managed"
$env:KEYMASTER_WHEELS = Join-Path $InstallDir "wheels"
$OwnCache = -not $env:UV_CACHE_DIR
if ($OwnCache) { $env:UV_CACHE_DIR = Join-Path $InstallDir "cache" }

function Write-Log([string]$Line) {
    [Console]::Out.WriteLine($Line)
    Add-Content -LiteralPath $Log -Value $Line -Encoding UTF8
}

function Invoke-Logged([string]$Exe, [string[]]$Arguments) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Exe @Arguments 2>&1 | ForEach-Object { Write-Log "$_" }
        return $LASTEXITCODE
    } catch {
        Write-Log "$_"
        return 1
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Invoke-Script([string]$Path) {
    return Invoke-Logged "powershell.exe" @("-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", $Path)
}

function Get-Ffmpeg {
    if (Test-Path -LiteralPath $Ffmpeg) { return 0 }
    $work = Join-Path ([System.IO.Path]::GetTempPath()) "keymaster-ffmpeg-$PID"
    $zip = Join-Path $work "ffmpeg.zip"
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    try {
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            $ProgressPreference = "SilentlyContinue"
            Write-Log $FfmpegUrl
            Invoke-WebRequest -UseBasicParsing -Uri $FfmpegUrl -OutFile $zip
        } catch {
            Write-Log "$_"
            return 2
        }
        $actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $FfmpegSha256.ToLowerInvariant()) {
            Write-Log "sha256 $actual != $FfmpegSha256"
            return 3
        }
        Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $work "x") -Force
        $found = Get-ChildItem -LiteralPath (Join-Path $work "x") -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
        if (-not $found) { return 2 }
        $root = Split-Path -Parent $found.Directory.FullName
        New-Item -ItemType Directory -Force -Path (Join-Path $FfmpegDir "bin") | Out-Null
        Copy-Item -Path (Join-Path $found.Directory.FullName "*") -Destination (Join-Path $FfmpegDir "bin") -Force
        Get-ChildItem -LiteralPath $root -File | Copy-Item -Destination $FfmpegDir -Force
        Write-Log $Ffmpeg
        return 0
    } finally {
        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Install-Core {
    $code = Invoke-Script (Join-Path $Core "install.ps1")
    if ($code -ne 0) { return 4 }
    if ($OwnCache) { Remove-Item -LiteralPath $env:UV_CACHE_DIR -Recurse -Force -ErrorAction SilentlyContinue }
    return 0
}

function Save-Settings {
    Push-Location $Core
    try {
        $pairs = @(@("python", $Py), @("core", $Core))
        if (Test-Path -LiteralPath $Ffmpeg) { $pairs += , @("ffmpeg", $Ffmpeg) }
        foreach ($pair in $pairs) {
            if ((Invoke-Logged $Py @("-m", "keymaster", "settings", "set", $pair[0], $pair[1])) -ne 0) { return 4 }
        }
        return 0
    } finally {
        Pop-Location
    }
}

function Install-App {
    if ((Invoke-Script (Join-Path $InstallDir "app\install.ps1")) -ne 0) { return 5 }
    return 0
}

function Invoke-Doctor {
    Push-Location $Core
    try {
        return (Invoke-Logged $Py @("-m", "keymaster", "doctor"))
    } finally {
        Pop-Location
    }
}

$result = switch ($Action) {
    "ffmpeg" { Get-Ffmpeg }
    "core" { Install-Core }
    "settings" { Save-Settings }
    "app" { Install-App }
    "doctor" { Invoke-Doctor }
}
exit ([int]($result | Select-Object -Last 1))
