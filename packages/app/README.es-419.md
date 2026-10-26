# App de Keymaster

**English:** [README.md](README.md)

Una app de escritorio para Linux y Windows que recorta clips de pantalla verde con CorridorKey 2.0.
Arrastra tus clips, presiona Iniciar y obtén la máscara alfa, el primer plano sin reflejo verde y un
recorte listo para componer junto a cada clip. No necesitas ningún programa de edición.

Necesitas una tarjeta gráfica NVIDIA y tener instalado primero el núcleo de Keymaster
(`keymaster-core`). La app usa el mismo Python del núcleo, así que solo le agrega una pequeña
biblioteca de interfaz.

## Instalación

1. Instala `keymaster-core` y ejecuta su instalador. Descarga los modelos y guarda su ubicación en
   el archivo de configuración de Keymaster.
2. Descomprime `keymaster-app-<versión>.zip` en una carpeta permanente (la app se ejecuta desde ahí).
3. Ejecuta el instalador desde la carpeta `keymaster-app` que descomprimiste:
   - Linux: `bash install.sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy Bypass -File install.ps1`

El instalador agrega PySide6 (la biblioteca de interfaz) al Python del núcleo y crea un lanzador:

- Linux: `~/.local/bin/keymaster-app` y una entrada **Keymaster** en tu menú de aplicaciones.
- Windows: `keymaster-app.bat` en la carpeta de la app y un acceso directo **Keymaster** en el menú
  Inicio.

Si el núcleo todavía no está instalado, el instalador se detiene y te lo avisa.

## Uso

1. Arrastra videos o carpetas de cuadros a la cola, o usa **Agregar archivos…** / **Agregar
   carpeta…**. Si sueltas un solo cuadro, se agrega toda su carpeta.
2. Opcional: selecciona un clip y presiona **Elegir guía…** para darle una máscara de su primer
   cuadro (blanco donde está el sujeto, negro donde no, del mismo tamaño que el clip). Si no eliges
   una, el modelo recorta el clip por su cuenta.
3. Elige las opciones:
   - **Calidad de la guía** y **Quitar reflejo verde** (de 0 a 1).
   - **Salidas**: máscara alfa, primer plano, recorte (RGBA) y una vista sobre cuadrícula.
   - **Formato**: secuencias de imágenes EXR o archivos de video.
   - **Modo de poca VRAM** para tarjetas gráficas con menos memoria (más lento).
   - **Carpeta de salida**: déjala vacía para guardar una carpeta `<clip>_keyed` junto a cada clip.
4. Presiona **Iniciar**. Los clips se procesan de uno en uno; **Cancelar** detiene el clip actual y
   deja los demás en espera. Si presionas **Iniciar** otra vez, se reintentan los clips que fallaron
   o que cancelaste.
5. Selecciona un clip terminado para ver su primer cuadro sobre una cuadrícula, y usa **Abrir
   carpeta de salida** para llegar a los archivos. Los resultados EXR se abren en tu programa de
   composición; la app solo muestra la vista previa de resultados PNG.

**Revisar instalación** ejecuta el diagnóstico del núcleo (tarjeta gráfica, FFmpeg, archivos del
modelo, PyTorch) y te dice qué falta.

El menú de idioma tiene tres opciones: **Idioma del sistema** (la predeterminada: español si tu
sistema está en cualquier variante de español, inglés en los demás casos), **English** y **Español
(Latinoamérica)**. El cambio se aplica al instante y se guarda para todos los programas de
Keymaster. La variable de entorno `KEYMASTER_LANGUAGE` (`en` o `es-419`) tiene prioridad sobre lo
que guardaste, y los instaladores siguen las mismas reglas.

También puedes abrir la app con clips ya en la cola: `keymaster-app clip1.mp4 carpeta_de_cuadros/`.

## Solución de problemas

- Linux, "could not load the Qt platform plugin xcb": instala el paquete `libxcb-cursor` de tu
  distribución (por ejemplo `libxcb-cursor0` en Ubuntu).
- La app dice que falta la biblioteca de interfaz: vuelve a ejecutar el instalador.
