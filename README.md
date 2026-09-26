# MU Kirtash

Guías y database de MU Online, generada con [Hugo](https://gohugo.io/).
Cada guía es un archivo Markdown; Hugo lo convierte en una página HTML estática.

## Arrancar en local

1. Instala Hugo (versión 0.146 o superior; probado con 0.166):
   - Windows: `winget install Hugo.Hugo`
   - macOS: `brew install hugo`
   - Linux: descarga el binario de https://github.com/gohugoio/hugo/releases
2. En esta carpeta: `hugo server`
3. Abre http://localhost:1313 (se recarga solo al guardar cambios).

> Abrir los `.html` con doble clic no sirve: el buscador necesita un servidor.

## Añadir una guía

```bash
hugo new content eventos/kalima.md
```

Crea el archivo con todos los campos. Rellena `title` y `description` y ya aparece en
portada, categoría, buscador e índice JSON. Si no escribes texto debajo del `---`,
la guía se genera con las secciones de su categoría (definidas en `data/categories.yaml`).

Para escribir contenido propio, usa `##` para cada sección (forman el índice) y estos atajos:

| Atajo | Resultado |
|---|---|
| `{{< consejo >}}Texto{{< /consejo >}}` | Caja de consejo |
| `{{< nota >}}Texto{{< /nota >}}` | Caja de aviso |
| `{{< pendiente >}}` | Marca de contenido pendiente |
| `{{< guia "dark-knight-skills" >}}` | Enlace a otra guía (nombre del archivo) |

Las tablas Markdown se adaptan solas al móvil y las celdas con `Pendiente` salen atenuadas.
Las listas numeradas (`1.`, `2.`…) se muestran como pasos.

Ejemplo completo: `content/personajes/dark-knight.md`.

### Campos de una guía

| Campo | Para qué sirve |
|---|---|
| `seasons` | Versiones a las que aplica: `s21`, `s20`, `archivo` |
| `status` | `demo` (muestra la etiqueta «Ejemplo») o `verified` |
| `tags` | Alias para el buscador (`bc`, `dk`…) |
| `stats` | Ficha rápida; los campos de la categoría sin valor salen como «Pendiente» |
| `related` | Guías relacionadas (nombre del archivo) |
| `image.src` | Imagen principal; guárdala en `static/img/…` y escribe `/img/…` |
| `requirements`, `drops`, `locations` | Cajas extra de la ficha (aparecen si el campo existe) |
| `weight` | Orden dentro de la categoría (menor = antes) |

## Importar guías de golpe

En `tools/importar/` hay un importador que crea todas las guías a partir de
guiamuonline.com, redactadas con palabras propias. Instrucciones en
[`tools/importar/README.md`](tools/importar/README.md).

## Estructura

```
content/<categoría>/*.md    Guías (una carpeta por categoría)
data/categories.yaml        Categorías: nombre, color, icono, secciones y campos de ficha
data/seasons.yaml           Versiones del juego
data/icons.yaml             Iconos SVG
layouts/                    Plantillas HTML (home, section = categoría, page = guía)
layouts/_partials/          Piezas reutilizables (tarjeta, ficha, índice…)
layouts/_shortcodes/        Atajos para el Markdown
layouts/home.json           Genera /index.json para el buscador
assets/css/main.css         Estilos
assets/js/app.js            Buscador, filtro de Season, índice activo, volver al catálogo
```

Para añadir una categoría nueva: crea `content/<id>/_index.md` y añade su entrada en
`data/categories.yaml` con el mismo `id`.

## Publicar

Genera el sitio con `hugo --minify`: el resultado queda en `public/`.

**Cloudflare Pages** (recomendado): conecta el repositorio y configura
- Framework preset: Hugo
- Build command: `hugo --minify`
- Output directory: `public`
- Variable de entorno: `HUGO_VERSION` = `0.166.0`

Después cambia `baseURL` en `hugo.toml` por la dirección final.

**GitHub Pages**: el flujo `.github/workflows/hugo.yml` ya está incluido. Activa
*Settings → Pages → Source: GitHub Actions* y cada push a `main` publica la web.
