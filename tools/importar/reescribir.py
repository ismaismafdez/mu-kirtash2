#!/usr/bin/env python3
"""
Paso 2 · Convierte las páginas descargadas en guías de MU Kirtash (content/<categoría>/<slug>.md)

Cada página se envía a la API de Claude, que extrae los datos y redacta la guía
con palabras propias en nuestro formato. Nunca sobrescribe guías con texto propio:
solo crea archivos nuevos o sustituye las guías de ejemplo vacías.

Requisitos: variable de entorno ANTHROPIC_API_KEY (https://console.anthropic.com)

Uso:
    python tools/importar/reescribir.py --limite 5            # prueba
    python tools/importar/reescribir.py                       # todo
    python tools/importar/reescribir.py --categoria mapas     # solo una categoría
    python tools/importar/reescribir.py --modelo claude-sonnet-5   # más calidad, más caro
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]          # carpeta del proyecto Hugo
FUENTES = Path(__file__).parent / "_fuentes"
CONTENT = RAIZ / "content"
REVISAR = FUENTES / "revisar.md"
EJEMPLO = CONTENT / "mapas" / "kalima.md"

MODELO_DEFECTO = "claude-haiku-4-5-20251001"
# USD por millón de tokens (entrada, salida), solo para mostrar el gasto aproximado
PRECIOS = {"claude-haiku-4-5-20251001": (1.0, 5.0)}

# Guías cuyo título indica una versión anterior a esta Season van a "Archivo".
# Ej.: "Blood Castle (0.97 - S9)" -> archivo · "Blood Castle (S15 EP1)" -> s21/s20
ARCHIVO_ANTES_DE = 15


def seasons_de(titulo: str) -> list[str]:
    for version in re.findall(r"\(([^)]*)\)", titulo):
        if re.search(r"\b(0\.9\d|eX70\d|SX|Season\s*X)\b", version, re.I):
            return ["archivo"]
        numeros = [int(n) for n in re.findall(r"\b(?:S|Season\s*)(\d{1,2})\b", version, re.I)]
        if numeros and max(numeros) < ARCHIVO_ANTES_DE:
            return ["archivo"]
    return ["s21", "s20"]


def cargar_categorias():
    return {c["id"]: c for c in yaml.safe_load((RAIZ / "data" / "categories.yaml").read_text("utf-8"))}


def es_plantilla_vacia(path: Path) -> bool:
    """True si la guía existente solo tiene frontmatter (guía de ejemplo sin texto)."""
    partes = path.read_text("utf-8").split("---", 2)
    return len(partes) == 3 and not partes[2].strip()


def instrucciones(categorias: dict) -> str:
    cats = "\n".join(
        f"- {c['id']}: secciones sugeridas {c['template']}; campos de ficha (stats) {c['fields']}"
        for c in categorias.values())
    ejemplo = EJEMPLO.read_text("utf-8") if EJEMPLO.exists() else ""
    return f"""Eres editor de MU Kirtash, una web de guías de MU Online en español.
Recibes el texto de una página de otra web de guías y escribes una guía NUEVA para MU Kirtash.

REGLAS DE REDACCIÓN
1. Escribe con tus propias palabras. No copies frases ni párrafos de la fuente, ni siquiera cambiando
   alguna palabra. Reorganiza la información y redacta de cero, en español neutro y claro.
2. Conserva los DATOS con exactitud: nombres de mapas, monstruos, items, NPCs, niveles, requisitos,
   cantidades, porcentajes, horarios. Los nombres propios del juego se dejan en inglés tal cual.
3. No inventes nada. Si un dato no está en la fuente, escribe "Pendiente" en la celda o usa
   {{{{< pendiente >}}}}. No añadas consejos que la fuente no respalde.
4. Prefiere tablas Markdown para datos repetitivos (listas de monstruos, stats, recompensas, requisitos).
5. No incluyas imágenes ni URLs de imágenes. No menciones la web de origen dentro del texto,
   salvo en la sección final "## Fuentes".
6. Si la fuente no tiene contenido real (solo una lista de enlaces o está vacía), responde
   exactamente: SALTAR

FORMATO DE SALIDA (solo el archivo, sin explicaciones ni bloques ```)
- Frontmatter YAML entre líneas ---, con: title, description (una frase, máx. 160 caracteres),
  tags (alias útiles para el buscador), stats (lista de {{label, value}} usando los campos de la
  categoría cuando haya dato), related: [].
- Opcional, solo para monstruos/items si la fuente lo trae: requirements, drops, locations (listas de texto).
- Cuerpo en Markdown con secciones "## ". Usa las secciones sugeridas de la categoría como guía,
  pero solo las que tengan contenido. Listas numeradas solo para pasos en orden.
- Puedes usar {{{{< consejo >}}}}texto{{{{< /consejo >}}}} y {{{{< nota >}}}}texto{{{{< /nota >}}}}.
- Termina siempre con la sección "## Fuentes" con el enlace a la URL de origen.
- Si el título de la fuente indica una versión concreta del juego (p. ej. "S15 EP1"), mantenla en title.

CATEGORÍAS
{cats}

EJEMPLO DE GUÍA TERMINADA
{ejemplo}"""


def pedir_guia(cliente, modelo: str, sistema: str, reg: dict) -> tuple[str, object]:
    mensaje = (f"Categoría: {reg['categoria']}\nTítulo en la fuente: {reg['titulo']}\n"
               f"URL de origen: {reg['url']}\n\nTEXTO DE LA FUENTE:\n{reg['texto']}")
    resp = cliente.messages.create(
        model=modelo, max_tokens=8000, system=sistema,
        messages=[{"role": "user", "content": mensaje}],
    )
    texto = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    return texto, resp.usage


def normalizar(salida: str, reg: dict, orden: int) -> str:
    """Valida el frontmatter y fija los campos que no decide el modelo."""
    salida = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", salida.strip())
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", salida, re.S)
    if not m:
        raise ValueError("la respuesta no tiene frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    cuerpo = m.group(2).strip()
    if not fm.get("title") or not cuerpo:
        raise ValueError("falta el título o el contenido")

    fm["description"] = str(fm.get("description") or "").strip()[:200]
    fm["weight"] = orden
    fm["seasons"] = seasons_de(reg["titulo"])
    fm["status"] = "demo"                    # pasa a "verified" cuando lo revises
    fm["updated"] = date.today().strftime("%Y-%m")
    fm["source"] = reg["url"]
    fm["tags"] = [str(t) for t in (fm.get("tags") or [])]
    fm["stats"] = [s for s in (fm.get("stats") or []) if isinstance(s, dict) and s.get("label")]
    fm["related"] = []
    if "## Fuentes" not in cuerpo:
        cuerpo += f"\n\n## Fuentes\n\n- [{reg['titulo'] or 'Fuente original'}]({reg['url']})"

    orden_campos = ["title", "description", "weight", "seasons", "status", "updated", "source",
                    "tags", "stats", "requirements", "drops", "locations", "related"]
    fm = {k: fm[k] for k in orden_campos if k in fm}
    return "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=200) + "---\n\n" + cuerpo + "\n"


def frases_copiadas(fuente: str, guia: str, n: int = 10) -> list[str]:
    """Detecta secuencias de n palabras idénticas entre fuente y guía (fuera de tablas)."""
    def palabras(t):
        prosa = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("|"))
        return re.findall(r"\w+", prosa.lower())
    f, g = palabras(fuente), palabras(guia)
    grams = {" ".join(f[i:i + n]) for i in range(len(f) - n + 1)}
    return [" ".join(g[i:i + n]) for i in range(len(g) - n + 1) if " ".join(g[i:i + n]) in grams]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limite", type=int, default=0, help="procesar solo N guías")
    ap.add_argument("--categoria", help="procesar solo esta categoría")
    ap.add_argument("--modelo", default=MODELO_DEFECTO)
    args = ap.parse_args()

    try:
        import anthropic
    except ImportError:
        sys.exit("Falta el paquete anthropic: pip install -r tools/importar/requirements.txt")
    cliente = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY
    categorias = cargar_categorias()
    sistema = instrucciones(categorias)

    fuentes = sorted(FUENTES.glob("*/*.json"))
    if args.categoria:
        fuentes = [p for p in fuentes if p.parent.name == args.categoria]
    if not fuentes:
        sys.exit("No hay páginas descargadas. Ejecuta primero descargar.py")

    hechas = saltadas = errores = 0
    tok_in = tok_out = 0
    avisos = []
    for i, path in enumerate(fuentes, start=1):
        reg = json.loads(path.read_text("utf-8"))
        destino = CONTENT / reg["categoria"] / f"{reg['slug']}.md"
        if destino.exists() and not es_plantilla_vacia(destino):
            continue  # ya existe con contenido: no se toca
        if args.limite and hechas >= args.limite:
            break
        if len(reg["texto"]) < 150:
            saltadas += 1
            continue
        try:
            salida, uso = pedir_guia(cliente, args.modelo, sistema, reg)
            tok_in += uso.input_tokens
            tok_out += uso.output_tokens
            if salida.strip() == "SALTAR":
                saltadas += 1
                print(f"  saltada (sin contenido): {reg['categoria']}/{reg['slug']}")
                continue
            md = normalizar(salida, reg, orden=100 + i)
        except Exception as e:  # noqa: BLE001
            errores += 1
            print(f"  ERROR {reg['categoria']}/{reg['slug']}: {e}")
            continue

        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(md, "utf-8")
        hechas += 1
        copiadas = frases_copiadas(reg["texto"], md)
        marca = f"  ⚠ {len(copiadas)} fragmentos parecidos a la fuente" if copiadas else ""
        if copiadas:
            avisos.append(f"- `content/{reg['categoria']}/{reg['slug']}.md`: «{copiadas[0]}…»")
        print(f"  [{hechas}] {reg['categoria']}/{reg['slug']}.md{marca}")

    if avisos:
        FUENTES.mkdir(exist_ok=True)
        REVISAR.write_text("# Guías con fragmentos parecidos a la fuente\n\nReescribe estas frases:\n\n"
                           + "\n".join(avisos) + "\n", "utf-8")

    precio = PRECIOS.get(args.modelo)
    coste = f" · coste aprox. {tok_in / 1e6 * precio[0] + tok_out / 1e6 * precio[1]:.2f} USD" if precio else ""
    print(f"\nListo: {hechas} guías creadas, {saltadas} saltadas, {errores} errores"
          f" · {tok_in:,} tokens de entrada, {tok_out:,} de salida{coste}")
    if avisos:
        print(f"Revisa {REVISAR.relative_to(RAIZ)}: {len(avisos)} guías con frases parecidas a la fuente")
    if errores:
        print("Vuelve a ejecutar el script para reintentar las que fallaron.")
    return 0 if not errores else 1


if __name__ == "__main__":
    sys.exit(main())
