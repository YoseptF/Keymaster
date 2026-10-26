# Keymaster

[English](README.md)

Recorte de pantalla verde y azul con IA dentro de DaVinci Resolve, Nuke, After Effects, Premiere Pro
y Blender, además de una app independiente.

## Requisitos

- NVIDIA RTX serie 30 o más reciente: 4 GB de VRAM para hasta 1440p, 6 GB para 4K
- Windows o Linux
- `ffmpeg` en tu PATH

## Paquetes

| Paquete | Qué es |
|---|---|
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
