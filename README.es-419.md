# Keymaster

[English](README.md)

Recorte de pantalla verde y azul con IA dentro de DaVinci Resolve, Nuke, After Effects, Premiere Pro
y Blender, además de una app independiente.

## Instalación

Descarga el instalador de la [última versión](https://github.com/YoseptF/Keymaster/releases/latest) y
ejecútalo. Instala todo lo que Keymaster necesita (Python, PyTorch, los modelos y ffmpeg) y agrega
Keymaster a los programas que tienes.

- Windows: `keymaster-installer-<versión>-windows.exe`, un asistente de instalación normal.
- Linux: `keymaster-installer-<versión>-linux.sh`, ejecuta `bash keymaster-installer-<versión>-linux.sh`.

Descarga unos 12 GB, así que dale tiempo. Los detalles y las opciones están en
[packages/installer](packages/installer/README.es-419.md).

## Requisitos

- NVIDIA RTX serie 30 o más reciente: 4 GB de VRAM para hasta 1440p, 6 GB para 4K, y un driver actual
- Windows o Linux (64 bits)
- Unos 15 GB libres en disco

## Paquetes

Para usuarios avanzados: cada paquete también se publica por separado, con sus propios pasos de
instalación.

| Paquete | Qué es |
|---|---|
| [installer](packages/installer/README.es-419.md) | El instalador de un clic para Windows y Linux. Empieza aquí. |
| [core](packages/core) | El motor de recorte que usan todos los demás paquetes. Instálalo primero. |
| [app](packages/app) | App independiente: suelta tus clips y obtén los mattes. |
| [openfx](packages/openfx) | Plugin OpenFX para DaVinci Resolve y Nuke. |
| [blender](packages/blender) | Complemento para Blender. |
| [adobe](packages/adobe) | Panel para After Effects y Premiere Pro. |

La carpeta de cada paquete explica cómo instalarlo.

## Créditos y licencia

Keymaster usa CorridorKey de Corridor Digital y se distribuye bajo la licencia de CorridorKey en
[LICENSE](LICENSE). Los avisos de los modelos de terceros están en
[packages/core/upstream/THIRD_PARTY_NOTICES.md](packages/core/upstream/THIRD_PARTY_NOTICES.md).
