$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$name = 'com.keymaster.adobe'
$source = Join-Path $here $name
$extensions = Join-Path $env:APPDATA 'Adobe\CEP\extensions'
$target = Join-Path $extensions $name
$settingsFile = if ($env:KEYMASTER_SETTINGS) { $env:KEYMASTER_SETTINGS } else { Join-Path $env:APPDATA 'Keymaster\settings.json' }

$settings = $null
if (Test-Path -LiteralPath $settingsFile) {
    try { $settings = Get-Content -LiteralPath $settingsFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $settings = $null }
}
function Get-KeymasterSpanish($settings) {
    $pinned = $env:KEYMASTER_LANGUAGE
    if (-not ($pinned -in @('en', 'es-419')) -and $settings -and $settings.language) { $pinned = $settings.language }
    if ($pinned -eq 'es-419') { return $true }
    if ($pinned -eq 'en') { return $false }
    return (Get-UICulture).Name -like 'es*'
}
$spanish = Get-KeymasterSpanish $settings

function Say([string]$en, [string]$es) {
    if ($spanish) { Write-Host $es } else { Write-Host $en }
}

if (-not (Test-Path -LiteralPath $source)) {
    Say "Could not find the $name folder next to this script. Unzip the whole download first." "No se encontró la carpeta $name junto a este script. Primero descomprime toda la descarga."
    exit 1
}

New-Item -ItemType Directory -Force -Path $extensions | Out-Null
if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
}
Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
Get-ChildItem -LiteralPath $target -Recurse -File | Unblock-File

foreach ($version in @('11', '12')) {
    $key = "HKCU:\Software\Adobe\CSXS.$version"
    if (-not (Test-Path -LiteralPath $key)) {
        New-Item -Path $key | Out-Null
    }
    New-ItemProperty -LiteralPath $key -Name 'PlayerDebugMode' -Value '1' -PropertyType String -Force | Out-Null
}

Say "Keymaster panel installed in $target" "Panel de Keymaster instalado en $target"
if (-not $settings -or -not $settings.python -or -not $settings.core) {
    Say "The Keymaster core is not installed yet. Install it before using the panel." "El núcleo de Keymaster todavía no está instalado. Instálalo antes de usar el panel."
}
Say "Restart After Effects or Premiere Pro, then open Window > Extensions > Keymaster." "Reinicia After Effects o Premiere Pro y abre Ventana > Extensiones > Keymaster."
