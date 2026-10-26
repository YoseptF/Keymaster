# Keymaster para After Effects y Premiere Pro

[English](README.md)

Un panel que hace el key de material con pantalla verde o azul usando CorridorKey, dentro de
After Effects y Premiere Pro (2022 o más reciente, Windows). Envía el clip seleccionado al núcleo
de Keymaster, muestra el progreso, importa el resultado y coloca el recorte justo encima de tu
origen.

## Instalación

1. Instala primero el núcleo de Keymaster y deja que termine de descargar los modelos. El panel
   usa el Python del núcleo y lo encuentra en la configuración compartida de Keymaster.
2. Descomprime `keymaster-adobe-<versión>.zip` donde quieras.
3. Haz doble clic en `install.cmd` (o ejecuta `install.ps1` en PowerShell). Copia el panel a
   `%APPDATA%\Adobe\CEP\extensions\com.keymaster.adobe` y activa `PlayerDebugMode` para CEP 11
   y 12, que las aplicaciones de Adobe necesitan para cargar un panel sin firma.
4. Reinicia After Effects o Premiere Pro y abre **Ventana > Extensiones > Keymaster**.
5. Haz clic en **Revisar instalación**. Cada línea debe tener una palomita.

El panel todavía no está firmado. Para pruebas no hay problema, pero por eso hace falta
`PlayerDebugMode`. Para quitar el panel, ejecuta `uninstall.cmd`. Deja `PlayerDebugMode`
activado porque otros paneles sin firma pueden necesitarlo.

## Uso en After Effects

1. En una composición, selecciona una capa cuyo origen sea un archivo de video o una secuencia
   de imágenes.
2. Elige tus opciones y haz clic en **Hacer key**.
3. Al terminar, los resultados quedan en una carpeta **Keymaster** del panel Proyecto y el
   recorte queda justo encima de la capa de origen, con la misma sincronía, transformaciones y
   máscaras (los efectos no se copian). **Apagar el origen** oculta la capa original.

En After Effects el formato predeterminado es una secuencia EXR. Los EXR son lineales de escena,
así que usa un espacio de trabajo lineal o la gestión de color que normalmente usas con EXR.

## Uso en Premiere Pro

1. En la secuencia activa, selecciona un clip.
2. Elige tus opciones y haz clic en **Hacer key**.
3. Los resultados van a una bandeja **Keymaster**. El recorte se coloca en la primera pista de
   video libre encima del clip, en la misma posición y con los mismos puntos de entrada y
   salida. Nada más se mueve en la línea de tiempo; si todas las pistas de arriba están ocupadas
   en ese tramo, se agrega una pista nueva.

En Premiere Pro el formato predeterminado es video, que da un recorte ProRes 4444 con alfa.

## Opciones

- **Guía del primer cuadro**: una máscara aproximada opcional del primer cuadro (blanco
  conserva, negro quita).
- **Calidad de la guía** y **Quitar derrame**: de 0 a 1.
- **Salidas**: recorte, mate alfa, primer plano y una vista previa con cuadrícula. Solo el
  recorte se coloca en la línea de tiempo; las demás se importan junto a él.
- **Formato**: secuencia EXR o video.
- **Carpeta de salida**: de forma predeterminada, una carpeta `Keymaster` junto al origen, con
  una subcarpeta por cada ejecución.
- **Modo de poca VRAM**: más lento, para tarjetas gráficas con poca memoria.

**Cancelar** detiene el núcleo y borra la carpeta de la ejecución que no terminó.

## Idioma

El panel sigue el idioma de tu aplicación de Adobe: español cuando la aplicación está en
cualquier variante de español, inglés en los demás casos. Para fijar un idioma en todos los
programas de Keymaster, pon `language` en `en` o `es-419` en el archivo de configuración
compartido (`%APPDATA%\Keymaster\settings.json`); `auto` o sin valor sigue a la aplicación. La
variable de entorno `KEYMASTER_LANGUAGE` tiene prioridad sobre ambos.

## Para desarrolladores

`bash test.sh` corre las pruebas en Linux con Node 24 y Python 3, usando el núcleo simulado.
Para probar el panel desde el repositorio en Windows, enlaza `packages\adobe\extension` en
`%APPDATA%\Adobe\CEP\extensions\com.keymaster.adobe` (`mklink /J`) y activa `PlayerDebugMode`;
con esa estructura el panel lee las traducciones directamente del repositorio.
