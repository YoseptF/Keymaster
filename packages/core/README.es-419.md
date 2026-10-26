# Keymaster core

El motor detrás de todos los hosts de Keymaster. Ejecuta el keyer de pantalla verde
CorridorKey 2.0 (una copia sin modificar vive en `upstream/`) y les da a los hosts una sola línea
de comandos, `python -m keymaster`, que habla JSON. Solo lo usas directamente para instalar los
modelos o para hacer keying desde una terminal.

## Requisitos

- Linux o Windows con una GPU NVIDIA (serie RTX 30 o más nueva, 4 GB de VRAM hasta 1440p,
  6 GB para 4K) y un driver de NVIDIA actualizado
- `ffmpeg` en tu PATH (lo necesitan las salidas de video)
- `git`, y Python 3.12 o 3.13, o [uv](https://docs.astral.sh/uv/), que descarga Python por ti
- Unos 12 GB de disco: 7 GB para PyTorch y compañía, 5 GB para los modelos

## Instalación

Desde esta carpeta:

    ./install.sh                                        # Linux
    powershell -ExecutionPolicy Bypass -File install.ps1  # Windows

El instalador crea `.venv`, instala PyTorch 2.9.1 (CUDA 12.8) y los requisitos de CorridorKey,
descarga los modelos en `upstream/weights` y `upstream/vfms`, guarda su ubicación en la
configuración compartida de Keymaster para que los hosts lo encuentren y termina con una revisión
del sistema. Si lo vuelves a ejecutar, solo completa lo que falte.

## Uso

Ejecuta esto desde esta carpeta con el Python del entorno (`.venv/bin/python` en Linux,
`.venv\Scripts\python.exe` en Windows):

    python -m keymaster doctor
    python -m keymaster key --input /tomas/plate.mov --output-dir /tomas/keyed
    python -m keymaster key --input /tomas/plate_frames --output-dir /tomas/keyed \
        --format video --outputs alpha cutout checker --despill 0.7
    python -m keymaster key --input /tomas/plate.mov --output-dir /tomas/keyed \
        --start-frame 100 --frames 48 --low-vram
    python -m keymaster setup
    python -m keymaster settings get
    python -m keymaster settings set language es-419

Opciones de `key`:

| Opción | Significado |
|---|---|
| `--input` | un archivo de video, o una carpeta de cuadros `.exr`/`.png`/`.jpg` |
| `--output-dir` | dónde se guardan los resultados |
| `--format exr` | secuencias EXR half-float en espacio lineal de escena (predeterminado) |
| `--format video` | videos de vista previa: MP4 para alpha, fg y checker, MOV ProRes 4444 para cutout |
| `--outputs` | cualquiera de `alpha fg cutout checker` (predeterminado `alpha fg cutout`) |
| `--despill` | quita el derrame de verde en cutout y checker, de 0 a 1 (predeterminado 0.5) |
| `--start-frame`, `--frames` | procesa solo una parte del clip: desde el cuadro S (contando desde 0), N cuadros |
| `--hint-first-frame` | un mate aproximado para el primer cuadro procesado |
| `--hint-video` | un mate aproximado para cada cuadro, como video o carpeta de cuadros |
| `--hint-quality` | cuánto confiar en las pistas, de 0 a 1 (predeterminado 0.95) |
| `--low-vram` | modo más lento para GPUs pequeñas |

Agrega `--json` para recibir un evento JSON por línea en stdout, que es lo que leen los hosts; el
formato está descrito en `docs/ARCHITECTURE.md` en la raíz del repositorio. Sin esa opción, el
progreso y los resultados se muestran como texto en tu idioma. Los mensajes siguen el idioma de tu
sistema, a menos que elijas uno con `settings set language en|es-419` (o `auto` para volver a
seguir el sistema).

Presiona Ctrl-C para cancelar: el core se detiene de forma ordenada y borra sus archivos temporales.
