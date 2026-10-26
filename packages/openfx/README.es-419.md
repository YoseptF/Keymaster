# Keymaster para OpenFX

[English](README.md)

Un plugin OpenFX que lleva el keyer de pantalla verde con IA de Keymaster a DaVinci Resolve (la
versión gratuita y Studio), Nuke y otros programas compatibles con OpenFX en Linux y Windows.

El plugin no ejecuta el modelo por su cuenta. Le envía el clip al núcleo de Keymaster, así que
primero instala [keymaster-core](../core). El instalador del núcleo guarda su ubicación en el
archivo de configuración compartido y el plugin la busca ahí. También puedes indicarla con las
variables de entorno `KEYMASTER_PYTHON` y `KEYMASTER_CORE`.

## Instalación

Descarga `keymaster-openfx-<versión>-linux.zip` o `keymaster-openfx-<versión>-windows.zip` desde
la página de versiones y descomprímelo.

- **Linux:** ejecuta `./install.sh`. Copia `Keymaster.ofx.bundle` en `/usr/OFX/Plugins` y te pide
  tu contraseña si hace falta. La versión para Linux necesita glibc 2.38 o más reciente (Ubuntu
  24.04, Fedora 39, Rocky Linux 10 o posteriores).
- **Windows:** haz clic derecho en `install.ps1` y elige **Ejecutar con PowerShell**. Pide permisos
  de administrador y copia `Keymaster.ofx.bundle` en `C:\Program Files\Common Files\OFX\Plugins`.

Define `OFX_PLUGIN_DIR` antes de ejecutar cualquiera de los dos scripts para instalarlo en otra
carpeta. Después reinicia el programa.

### DaVinci Resolve

Al reiniciar, Keymaster aparece en la biblioteca de **Efectos**, en **OpenFX > Filtros >
Keymaster**. Arrástralo a un nodo en la página Color o a un clip en la página Editar. Si no
aparece, revisa **Preferencias > Sistema > Plugins de video** y confirma que Keymaster esté
activado.

### Nuke

Nuke lee la misma carpeta. Al reiniciar, presiona Tab en el Node Graph y escribe `Keymaster`, o
búscalo en el menú **Keymaster** de la barra de herramientas. Si lo instalaste en otra carpeta,
agrégala a `OFX_PLUGIN_PATH`.

## Uso

1. Aplica Keymaster a un clip con pantalla verde. Mientras el clip no esté procesado, muestra el
   origen tal cual y un aviso que lo indica.
2. Presiona **Procesar clip**. Keymaster lee todos los fotogramas del clip, se los envía al núcleo
   y muestra el progreso. El procesamiento usa la GPU y puede tardar varios minutos; puedes
   cancelarlo desde la ventana de progreso.
3. Elige una **Salida**: **Recorte** (premultiplicado, listo para componer), **Alfa**, **Primer
   plano** u **Origen**.

**Calidad de la guía** y **Quitar derrame** se usan al procesar. Si los cambias, o si recortas o
reemplazas el clip de origen, Keymaster vuelve a mostrar el origen hasta que presiones **Procesar
clip** otra vez.

**Codificación del clip** le indica a Keymaster cómo vienen codificados los valores de píxel que
recibe. Déjalo en **Con gamma** para líneas de tiempo de Resolve y usa **Lineal de escena** en
Nuke, donde es el valor predeterminado.

**Borrar key** elimina el resultado guardado. Los resultados se guardan en disco, en
`~/.cache/keymaster/openfx` en Linux y en `%LOCALAPPDATA%\Keymaster\openfx` en Windows, y se
conservan al guardar y volver a abrir el proyecto.

## Idioma

El plugin está en inglés y en español latinoamericano y sigue el idioma de tu sistema. Para elegir
uno tú mismo, pon `"language": "es-419"` o `"en"` en el archivo de configuración de Keymaster, o
define la variable de entorno `KEYMASTER_LANGUAGE`. El programa toma el cambio la próxima vez que
se inicie.
