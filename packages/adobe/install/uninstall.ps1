$ErrorActionPreference = 'Stop'
$name = 'com.keymaster.adobe'
$target = Join-Path $env:APPDATA "Adobe\CEP\extensions\$name"
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

if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
    Say "Keymaster panel removed. Restart After Effects or Premiere Pro." "Panel de Keymaster eliminado. Reinicia After Effects o Premiere Pro."
} else {
    Say "The Keymaster panel was not installed." "El panel de Keymaster no estaba instalado."
}
Say "PlayerDebugMode was left on because other unsigned panels may need it." "PlayerDebugMode se dejó activado porque otros paneles sin firma pueden necesitarlo."
