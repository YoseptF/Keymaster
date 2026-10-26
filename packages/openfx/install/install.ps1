$ErrorActionPreference = 'Stop'
$common = if ($env:CommonProgramW6432) { $env:CommonProgramW6432 } else { $env:CommonProgramFiles }
$dest = if ($env:OFX_PLUGIN_DIR) { $env:OFX_PLUGIN_DIR } else { Join-Path $common 'OFX\Plugins' }
$lang = if ($env:KEYMASTER_LANGUAGE) { $env:KEYMASTER_LANGUAGE } else { (Get-UICulture).Name }

function Say([string]$en, [string]$es) {
    if ($lang -like 'es*') { Write-Host $es } else { Write-Host $en }
}

$src = Join-Path $PSScriptRoot 'Keymaster.ofx.bundle'
if (-not (Test-Path $src)) {
    Say 'Keymaster.ofx.bundle was not found next to this script.' 'No se encontró Keymaster.ofx.bundle junto a este script.'
    exit 1
}

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$admin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin -and -not $env:OFX_PLUGIN_DIR) {
    Say 'Asking for administrator rights to write to the shared OFX plugin folder...' 'Pidiendo permisos de administrador para escribir en la carpeta compartida de plugins OFX...'
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $argList -Wait
    exit
}

New-Item -ItemType Directory -Force -Path $dest | Out-Null
$target = Join-Path $dest 'Keymaster.ofx.bundle'
if (Test-Path $target) { Remove-Item -Recurse -Force $target }
Copy-Item -Recurse -Path $src -Destination $dest
Say "Keymaster is installed in $target. Restart DaVinci Resolve or Nuke to load it." "Keymaster quedó instalado en $target. Reinicia DaVinci Resolve o Nuke para cargarlo."
if (-not $env:OFX_PLUGIN_DIR) { Start-Sleep -Seconds 4 }
