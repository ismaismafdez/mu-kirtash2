# Importador de guías

Crea de golpe las guías de MU Kirtash a partir de guiamuonline.com, en dos pasos:

1. **`descargar.py`** lee el menú de la web y guarda el texto de cada guía en `_fuentes/`
   (sin menú, anuncios ni imágenes). Va despacio a propósito (1,5 s entre páginas) para no
   saturar su servidor: unas 250 páginas tardan unos 7 minutos. Si se corta, vuelve a
   ejecutarlo y sigue donde lo dejó.
2. **`reescribir.py`** envía cada página a la API de Claude, que extrae los datos y redacta la
   guía con palabras propias en nuestro formato. Las guarda en `content/<categoría>/`.

`_fuentes/` es solo material de trabajo: está en `.gitignore` y no se publica.

## Preparación (una vez)

```bash
pip install -r tools/importar/requirements.txt
```

Para el paso 2 necesitas una clave de API de Anthropic (se crea en https://console.anthropic.com,
es un servicio de pago por uso distinto de la suscripción de Claude.ai):

```bash
# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-..."
# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Uso

Ejecuta todo desde la carpeta raíz del proyecto. Empieza siempre con una prueba pequeña:

```bash
python tools/importar/descargar.py --limite 5
python tools/importar/reescribir.py --limite 5
hugo server        # revisa las 5 guías en http://localhost:1313
```

Si te convence el resultado, lanza el resto:

```bash
python tools/importar/descargar.py
python tools/importar/reescribir.py
```

Opciones de `reescribir.py`:

| Opción | Para qué |
|---|---|
| `--limite N` | Procesar solo N guías |
| `--categoria mapas` | Solo una categoría |
| `--modelo claude-sonnet-5` | Redacción de más calidad (más cara que el modelo por defecto, Haiku 4.5) |

## Qué hace y qué no toca

- **Nunca sobrescribe una guía con texto propio** (como `dark-knight.md` o `kalima.md`).
  Solo crea archivos nuevos o sustituye las guías de ejemplo vacías.
- Todas las guías importadas llevan `status: demo` (etiqueta «Ejemplo») y el campo `source`
  con la URL de origen. Cámbialo a `verified` cuando las revises.
- **Seasons:** si el título trae una versión anterior a S15 (p. ej. «Blood Castle (0.97 - S9)»),
  la guía va a *Archivo*; el resto se marca como Season 21 y 20. El corte se cambia en
  `ARCHIVO_ANTES_DE` dentro de `reescribir.py`.
- Las páginas sin contenido real (solo listas de enlaces) se saltan.
- Al terminar, si alguna guía conserva frases muy parecidas a la fuente, aparece en
  `_fuentes/revisar.md` para que las reescribas.
- Las imágenes no se importan: los huecos de imagen quedan listos para las tuyas.
- No se descargan las herramientas interactivas de su web (Master Skill Tree, Spots…),
  que no son artículos.

## Después de importar

- Revisa las guías de una categoría con `hugo server` y corrige lo que haga falta.
- Rellena `related:` en las guías que quieras enlazar entre sí.
- Algunos nombres de archivo pueden repetir una guía de ejemplo con otro nombre
  (p. ej. una guía importada y una de ejemplo del mismo mapa). Borra la que sobre.
