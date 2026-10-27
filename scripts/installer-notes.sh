#!/usr/bin/env bash
set -euo pipefail
dist="${1:-dist}"
pick() { (cd "$dist" && ls $1 2>/dev/null | head -n 1) || true; }
windows="$(pick 'keymaster-installer-*-windows.exe')"
linux="$(pick 'keymaster-installer-*-linux.sh')"
if [ -z "$windows" ] || [ -z "$linux" ]; then
  echo "error: $dist needs both the Windows and the Linux installer" >&2
  exit 1
fi
echo "**Install Keymaster:** download \`$windows\` (Windows) or \`$linux\` (Linux) and run it. It installs everything, including the plugins for the programs you have."
echo
echo "**Instalar Keymaster:** descarga \`$windows\` (Windows) o \`$linux\` (Linux) y ejecútalo. Instala todo, incluidos los plugins para los programas que tienes."
echo
echo "The other files, one zip per package, are for advanced users. \`SHA256SUMS\` has every file's checksum. / Los demás archivos, un zip por paquete, son para usuarios avanzados. \`SHA256SUMS\` tiene la suma de verificación de cada archivo."
