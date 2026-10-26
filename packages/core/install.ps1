$ErrorActionPreference = "Stop"

$Core = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Core ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"
$TorchIndex = "https://download.pytorch.org/whl/cu128"

function Test-Supported([string[]]$Command) {
    $exe = $Command[0]
    $rest = @()
    if ($Command.Length -gt 1) { $rest = $Command[1..($Command.Length - 1)] }
    try {
        & $exe @rest -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3, 12), (3, 13)) else 1)" 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe exited with code $LASTEXITCODE" }
}

$HasUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)

if ((Test-Path $Py) -and -not (Test-Supported @($Py))) {
    Write-Host "Removing $Venv because it does not use Python 3.12 or 3.13"
    Remove-Item -Recurse -Force $Venv
}

if (-not (Test-Path $Py)) {
    if ($HasUv) {
        Invoke-Checked "uv" @("venv", "--python", "3.12", $Venv)
    } else {
        $Base = $null
        foreach ($candidate in @(@("py", "-3.12"), @("py", "-3.13"), @("python"))) {
            if ((Get-Command $candidate[0] -ErrorAction SilentlyContinue) -and (Test-Supported $candidate)) {
                $Base = $candidate
                break
            }
        }
        if (-not $Base) {
            Write-Error "Keymaster needs Python 3.12 or 3.13 (or uv, which can fetch it). Install one and run this again."
            exit 1
        }
        $rest = @()
        if ($Base.Length -gt 1) { $rest = $Base[1..($Base.Length - 1)] }
        Invoke-Checked $Base[0] ($rest + @("-m", "venv", $Venv))
    }
}

function Install-Packages([string[]]$Arguments) {
    if ($HasUv) {
        Invoke-Checked "uv" (@("pip", "install", "--python", $Py) + $Arguments)
    } else {
        Invoke-Checked $Py (@("-m", "pip", "install") + $Arguments)
    }
}

if (-not $HasUv) { Invoke-Checked $Py @("-m", "pip", "install", "--upgrade", "pip") }
Install-Packages @("torch==2.9.1", "torchvision==0.24.1", "--index-url", $TorchIndex)
Install-Packages @("-r", (Join-Path $Core "upstream\requirements.txt"))

Push-Location $Core
try {
    Invoke-Checked $Py @("-m", "keymaster", "setup")
    & $Py -m keymaster doctor
} finally {
    Pop-Location
}
