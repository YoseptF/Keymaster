#!/usr/bin/env bash
set -euo pipefail
dist="${1:-dist}"
pick() { (cd "$dist" && ls $1 2>/dev/null | head -n 1) || true; }
windows="$(pick 'keymaster-installer-*-windows.exe')"
linux="$(pick 'keymaster-installer-*-linux.sh')"
where_en=""
where_es=""
if [ -n "${INSTALLER_URL:-}" ]; then
  where_en=" from the [installer release]($INSTALLER_URL)"
  where_es=" desde la [versión del instalador]($INSTALLER_URL)"
fi
if [ -n "$windows" ] && [ -n "$linux" ]; then
  echo "**Install Keymaster:** download \`$windows\` (Windows) or \`$linux\` (Linux)$where_en and run it. It installs everything, including the plugins for the programs you have."
  echo
  echo "**Instalar Keymaster:** descarga \`$windows\` (Windows) o \`$linux\` (Linux)$where_es y ejecútalo. Instala todo, incluidos los plugins para los programas que tienes."
else
  url="https://github.com/${GITHUB_REPOSITORY:-YoseptF/Keymaster}/releases?q=keymaster-installer"
  echo "**Install Keymaster:** download \`keymaster-installer-…-windows.exe\` (Windows) or \`keymaster-installer-…-linux.sh\` (Linux) from the [latest installer release]($url) and run it."
  echo
  echo "**Instalar Keymaster:** descarga \`keymaster-installer-…-windows.exe\` (Windows) o \`keymaster-installer-…-linux.sh\` (Linux) desde la [última versión del instalador]($url) y ejecútalo."
fi
echo
echo "The other files, one zip per package, are for advanced users. / Los demás archivos, un zip por paquete, son para usuarios avanzados."
