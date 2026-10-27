# Keymaster para Blender

[English](README.md)

Una extensión para Blender 5 que quita la pantalla verde en el editor de secuencias de video con
CorridorKey. Manda el clip activo al núcleo de Keymaster y regresa el resultado a la línea de
tiempo, cuadro por cuadro encima del original.

## Instalación

1. Primero instala el núcleo de Keymaster y corre su configuración, para que se descarguen los
   modelos y Keymaster sepa dónde está su Python.
2. Descarga `keymaster-blender-<versión>.zip` de los
   [releases](https://github.com/YoseptF/Keymaster/releases/latest). No lo descomprimas.
3. En Blender, abre Editar > Preferencias > Obtener extensiones, abre el menú de arriba a la
   derecha y elige Instalar desde disco. Selecciona el zip.
4. En las preferencias de la extensión, presiona Revisar configuración. Cada línea debe tener una
   palomita. Ahí mismo ves qué núcleo y qué Python encontró Keymaster.

## Idioma

El complemento está en English o Español (Latinoamérica) y sigue el idioma de la interfaz de
Blender: cualquier variante de español da español, todo lo demás inglés. Si la traducción de la
interfaz está apagada o el idioma está en Automático, sigue el idioma de tu sistema. Para fijar un
idioma en todas las apps de Keymaster, pon `"language"` en `"en"` o `"es-419"` en el archivo de
configuración compartido de Keymaster (`"auto"`, el valor por defecto, sigue al programa), o define
la variable de entorno `KEYMASTER_LANGUAGE`. El panel cambia la próxima vez que se redibuja; las
descripciones emergentes y los nombres en el menú de búsqueda F3 cambian al reiniciar Blender.

## Uso

1. En el editor de secuencias, selecciona un clip de video o de secuencia de imágenes para que sea
   el clip activo.
2. Abre la barra lateral (N) y la pestaña Keymaster.
3. Si quieres, elige una imagen guía del primer cuadro y ajusta la calidad de la guía, el derrame
   verde que se quita, qué salidas escribir y el formato (secuencia de imágenes EXR por defecto).
4. Presiona Recortar fondo. Puedes seguir usando Blender mientras trabaja; la barra muestra cada
   paso y Cancelar lo detiene.
5. Al terminar, el recorte aparece en el primer canal libre encima del original con mezcla Alpha
   Over, alineado con los cuadros del original, incluidos sus recortes de inicio y fin. Con
   "Agregar también las otras salidas como clips" activado, las salidas de alfa, primer plano y
   tablero se agregan encima, silenciadas.

Los archivos recortados se guardan en la carpeta de salida que elijas, o en una carpeta `keymaster`
junto al archivo `.blend` guardado (la carpeta temporal del sistema si no lo has guardado). Solo se
procesan los cuadros hasta el final de la parte visible del clip.

## Desarrollo

- `bash packages/blender/test.sh` corre las pruebas unitarias y, si `blender` está en el PATH,
  también instala la extensión en un perfil de Blender desechable y recorta clips con el núcleo de
  prueba.
- `python3 packages/blender/build.py --out DIR --version V` genera `keymaster-blender-V.zip`.
- Para probar el código fuente directamente, enlaza `packages/blender/keymaster` dentro de la
  carpeta de un repositorio local de extensiones; así lee sus traducciones desde el repositorio.
