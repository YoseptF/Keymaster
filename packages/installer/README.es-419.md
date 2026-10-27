# Instalador de Keymaster

[English](README.md)

Una sola descarga que instala Keymaster y lo agrega a los programas que tienes: el núcleo de keying
(Python, PyTorch y los modelos de CorridorKey), la app independiente y los plugins para Blender,
DaVinci Resolve y Nuke (OpenFX), y After Effects y Premiere Pro. No necesitas tener Python, git ni
ffmpeg de antemano.

Necesitas una tarjeta gráfica NVIDIA con un driver actual, Windows o Linux de 64 bits, conexión a
internet y unos 15 GB libres en disco. El instalador descarga unos 12 GB, así que la primera
instalación tarda un rato.

## Windows

1. Descarga `keymaster-installer-<versión>-windows.exe` de las
   [versiones](https://github.com/YoseptF/Keymaster/releases) y haz doble clic. El instalador
   todavía no está firmado: si Windows SmartScreen lo detiene, elige **Más información** y luego
   **Ejecutar de todas formas**.
2. Elige qué instalar. Los programas que se encontraron en esta computadora ya están marcados; los
   demás dicen "no se encontró en esta computadora".
3. Deja la carpeta sugerida (`%LOCALAPPDATA%\Programs\Keymaster`) o elige otra y presiona
   **Instalar**. El registro muestra cada paso mientras se descargan Python, PyTorch y los modelos.
4. Si elegiste DaVinci Resolve y Nuke, Windows pide permisos de administrador una vez, solo para
   copiar el plugin a `C:\Program Files\Common Files\OFX\Plugins`. Todo lo demás queda en tu cuenta
   de usuario.
5. El último paso revisa la instalación y te dice si todo está listo. Reinicia Blender, Resolve,
   Nuke, After Effects o Premiere Pro para ver Keymaster; la app está en el menú Inicio.

Para quitar Keymaster, usa **Configuración > Aplicaciones > Keymaster > Desinstalar** (o Agregar o
quitar programas). Quita el núcleo, los modelos, los plugins, la entrada del menú Inicio y las
entradas de registro que agregó. Tus clips procesados nunca se tocan.

Instalación silenciosa, por ejemplo para un laboratorio: `keymaster-installer-<versión>-windows.exe /S`,
con `/COMPONENTS=app,blender,openfx,adobe` para elegir las partes opcionales y `/D=C:\ruta` (al
final) para la carpeta. Desinstalación silenciosa: `"%LOCALAPPDATA%\Programs\Keymaster\uninstall.exe" /S`.

## Linux

1. Descarga `keymaster-installer-<versión>-linux.sh` de las
   [versiones](https://github.com/YoseptF/Keymaster/releases).
2. Ejecútalo en una terminal: `bash keymaster-installer-<versión>-linux.sh`
3. Responde las preguntas (Enter elige la respuesta sugerida). Se instala en
   `~/.local/share/keymaster` y no necesita permisos de administrador, salvo para el plugin OpenFX:
   copiarlo a `/usr/OFX/Plugins` pide tu contraseña con `sudo`. Si lo omites, muestra el comando
   para hacerlo después.
4. Al terminar, muestra el resultado de la revisión y cómo abrir cada parte.

Opciones:

| Opción | Significado |
|---|---|
| `--yes` | sin preguntas, instala lo que se encontró |
| `--components core,app,blender,openfx` | elige las partes (el núcleo siempre se instala) |
| `--prefix CARPETA` | instala en otro lugar |
| `--bundled-ffmpeg` | usa el ffmpeg propio de Keymaster aunque ya haya uno instalado |
| `--uninstall` | quita Keymaster |

Para quitar Keymaster: `bash ~/.local/share/keymaster/uninstall.sh`. Quita la carpeta, el lanzador
y la entrada del menú de la app, la extensión de Blender, el plugin OpenFX y el archivo de
configuración si lo creó el instalador. Tus clips procesados nunca se tocan.

## Qué instala y descarga

| Parte | Dónde |
|---|---|
| Núcleo, Python 3.12, PyTorch 2.9.1 (CUDA 12.8), modelos | la carpeta de instalación |
| App independiente | la carpeta de instalación, más una entrada en el menú Inicio o un lanzador `keymaster-app` y una entrada de menú |
| Extensión de Blender | la carpeta de extensiones de Blender, para cada Blender 5 que se encuentre |
| Plugin OpenFX | `C:\Program Files\Common Files\OFX\Plugins` o `/usr/OFX/Plugins` |
| Panel de After Effects y Premiere Pro (Windows) | `%APPDATA%\Adobe\CEP\extensions`, y `PlayerDebugMode` para CEP 11 y 12, que los paneles sin firma necesitan |
| Configuración compartida | `%APPDATA%\Keymaster\settings.json` o `~/.config/keymaster/settings.json` |

Las descargas están fijadas a versiones exactas y se verifican con sus sumas SHA-256:
[uv](https://github.com/astral-sh/uv) (que instala Python y PyTorch; incluido en Windows,
descargado en Linux cuando falta `uv`) y una compilación estática de ffmpeg (en Windows siempre, en
Linux cuando falta ffmpeg). ffmpeg se descarga de sus publicadores originales
([gyan.dev](https://www.gyan.dev/ffmpeg/builds/) para Windows,
[johnvansickle.com](https://johnvansickle.com/ffmpeg/) para Linux) y tiene licencia GPL versión 3;
sus archivos de licencia quedan junto a él. Los modelos vienen de Hugging Face y Google Cloud
Storage, igual que en el núcleo.

## Solución de problemas

- Los detalles de cada paso están en `logs/install.log` dentro de la carpeta de instalación.
- Una descarga fallida o una suma de verificación que no coincide detiene el instalador sin usar el
  archivo. Ejecútalo de nuevo; continúa donde se detuvo y conserva lo que ya se descargó.
- Ejecutar el instalador de nuevo repara o actualiza una instalación sin volver a descargar los
  modelos.

## Desarrollo

- `python3 packages/installer/build.py --out CARPETA --version V --platform linux|windows` genera
  `keymaster-installer-V-linux.sh` o `keymaster-installer-V-windows.exe`. Compila los demás
  paquetes que incluye, así que necesita lo mismo que ellos, más `makensis` (`apt install nsis`)
  para Windows. Las descargas se guardan en `tmp/installer-cache`. Los archivos de las versiones
  solo los genera CI.
- `bash packages/installer/test.sh` prueba los generadores, genera el instalador de Linux y lo
  instala en un home desechable con un núcleo falso y descargas falsas; con `makensis`, `wine` y
  `xvfb-run` también instala y desinstala el instalador de Windows en modo silencioso con Wine.
- Las descargas fijadas están en `pins.json`. Cuando `packages/core/upstream/requirements.txt`
  cambia una dependencia de git, actualiza su versión ahí o la compilación se detiene.
