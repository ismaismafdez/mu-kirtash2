#!/usr/bin/env python3
"""
Paso 1 · Descarga las guías de guiamuonline.com a tools/importar/_fuentes/

Solo guarda el texto del artículo (sin menú ni imágenes) en un JSON por página.
Es reanudable: las páginas ya descargadas se saltan.

Uso:
    python tools/importar/descargar.py --limite 5     # prueba
    python tools/importar/descargar.py                # todo (~250 páginas)
"""
import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

BASE = "https://www.guiamuonline.com/"
PAUSA = 1.5  # segundos entre peticiones: no saturar su servidor
USER_AGENT = "MU-Kirtash-importador/1.0 (proyecto de fans)"
DESTINO = Path(__file__).parent / "_fuentes"

# Primer segmento de la URL -> categoría de MU Kirtash
SECCIONES = {
    "personajes": "personajes",
    "skills-mu-online": "skills",
    "quest-mu-online": "quests",
    "eventos-mu-online": "eventos",
    "mapas-mu-online": "mapas",
    "monstruos-mu-online": "monstruos",
    "items-de-mu-online": "items",
    "npc": "sistemas",
}
# En su web estos eventos están dentro de "Quest"; aquí van a Eventos
A_EVENTOS = ("blood-castle", "devil-square", "chaos-castle", "illusion-temple")


def categoria_de(url: str):
    partes = [p for p in urlparse(url).path.split("/") if p]
    if not partes or partes[0] not in SECCIONES:
        return None
    cat = SECCIONES[partes[0]]
    if cat == "quests" and any(p.startswith(A_EVENTOS) for p in partes[1:]):
        cat = "eventos"
    return cat


def es_guia(url: str) -> bool:
    """Descarta portadas de sección, herramientas .html y enlaces externos."""
    u = urlparse(url)
    if u.netloc.replace("www.", "") != urlparse(BASE).netloc.replace("www.", ""):
        return False
    if u.path.endswith(".html") or u.query:
        return False
    partes = [p for p in u.path.split("/") if p]
    # "npc" es una página única; el resto necesita al menos sección/guía
    return categoria_de(url) is not None and (len(partes) >= 2 or partes == ["npc"])


def recoger_enlaces(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    vistos, urls = set(), []
    for a in soup.find_all("a", href=True):
        url = urljoin(BASE, a["href"]).split("#")[0].rstrip("/")
        u, b = urlparse(url), urlparse(BASE)
        if u.netloc.replace("www.", "") == b.netloc.replace("www.", ""):
            url = u._replace(scheme=b.scheme, netloc=b.netloc).geturl()  # mismo esquema y host que BASE
        if url not in vistos and es_guia(url):
            vistos.add(url)
            urls.append(url)
    return urls


def a_texto(bloque) -> str:
    """Aplana el HTML (tablas anidadas incluidas) a líneas "celda | celda" fáciles de leer."""
    for br in bloque.find_all("br"):
        br.replace_with("\n")
    for celda in bloque.find_all(["td", "th"]):
        celda.append(" | ")
    for tag in bloque.find_all(["tr", "p", "li", "div", "h1", "h2", "h3", "h4", "table"]):
        tag.append("\n")
    for a in bloque.find_all("a"):
        a.unwrap()
    lineas = []
    for linea in bloque.get_text("").splitlines():
        linea = re.sub(r"[ \t\xa0]+", " ", linea)
        linea = re.sub(r"(\s*\|\s*)+", " | ", linea).strip(" |")
        if linea:
            lineas.append(linea)
    return "\n".join(lineas)


def extraer_articulo(html: str) -> tuple[str, str]:
    """Devuelve (título, texto en Markdown) del artículo, sin menú, anuncios ni imágenes."""
    soup = BeautifulSoup(html, "html.parser")
    titulo = (soup.title.string or "").split("|")[0].strip() if soup.title else ""
    for tag in soup(["script", "style", "noscript", "iframe", "img", "form"]):
        tag.decompose()

    # Joomla 1.5 guarda el artículo en tablas "contentpaneopen"
    bloques = soup.select("table.contentpaneopen") or soup.select(".article-content, .item-page, article")
    if bloques:
        md = "\n\n".join(a_texto(b) for b in bloques)
    else:
        # Plan B: recortar entre "Escrito por" y "Última actualización"
        md = markdownify(str(soup.body or soup), heading_style="ATX")
        ini = md.find("Escrito por")
        fin = min([i for i in (md.find("Última actualización", ini), md.find("Copyright ©", ini)) if i > 0], default=-1)
        md = md[ini:fin] if ini >= 0 else ""

    # Limpieza: enlaces a texto plano, sin líneas de autoría/fechas, sin blancos repetidos
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)
    md = re.sub(r"^.*(Escrito por|Última actualización).*$", "", md, flags=re.M)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return titulo, md


def slug_de(url: str, categoria: str, usados: set) -> str:
    base = re.sub(r"[^a-z0-9-]+", "-", urlparse(url).path.rstrip("/").split("/")[-1].lower()).strip("-")
    # "mapa-lorencia", "karutan-1", "gun-crasher-skill" -> "lorencia", "karutan", "gun-crasher"
    base = re.sub(r"^(mapa|mapas|personaje|skill|evento)-", "", base)
    base = re.sub(r"-(mapa|mapas|map|maps|items|skill|monstruos|1)$", "", base) or "guia"
    if categoria == "monstruos" and not base.startswith("monstruos"):
        base = f"monstruos-{base}"
    slug = base if base not in usados else f"{base}-{categoria}"
    n = 2
    while slug in usados:
        slug = f"{base}-{n}"
        n += 1
    usados.add(slug)
    return slug


def main():
    global BASE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limite", type=int, default=0, help="descargar solo N páginas nuevas (prueba)")
    ap.add_argument("--base", default=BASE, help=argparse.SUPPRESS)  # para pruebas locales
    args = ap.parse_args()

    BASE = args.base.rstrip("/") + "/"
    sesion = requests.Session()
    sesion.headers["User-Agent"] = USER_AGENT

    robots = RobotFileParser(urljoin(BASE, "robots.txt"))
    try:
        robots.read()
    except Exception:
        robots = None

    print(f"Leyendo el menú de {BASE} …")
    urls = recoger_enlaces(sesion.get(BASE, timeout=30).text)
    print(f"{len(urls)} páginas candidatas")

    DESTINO.mkdir(parents=True, exist_ok=True)
    indice_path = DESTINO / "_indice.json"
    indice = json.loads(indice_path.read_text("utf-8")) if indice_path.exists() else {}
    usados = {v["slug"] for v in indice.values()}

    nuevas = errores = 0
    for url in urls:
        if url in indice:
            continue
        if args.limite and nuevas >= args.limite:
            break
        if robots and not robots.can_fetch(USER_AGENT, url):
            print(f"  robots.txt no permite {url}")
            continue
        cat = categoria_de(url)
        try:
            resp = sesion.get(url, timeout=30)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            titulo, texto = extraer_articulo(resp.text)
        except Exception as e:  # noqa: BLE001
            errores += 1
            print(f"  ERROR {url}: {e}")
            time.sleep(PAUSA)
            continue

        slug = slug_de(url, cat, usados)
        registro = {"url": url, "titulo": titulo, "categoria": cat, "slug": slug,
                    "texto": texto, "descargado": date.today().isoformat()}
        (DESTINO / cat).mkdir(exist_ok=True)
        (DESTINO / cat / f"{slug}.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1), "utf-8")
        indice[url] = {"slug": slug, "categoria": cat, "titulo": titulo, "caracteres": len(texto)}
        indice_path.write_text(json.dumps(indice, ensure_ascii=False, indent=1), "utf-8")
        nuevas += 1
        aviso = "  (casi vacía)" if len(texto) < 150 else ""
        print(f"  [{nuevas}] {cat}/{slug} · {len(texto)} caracteres{aviso}")
        time.sleep(PAUSA)

    print(f"\nListo: {nuevas} nuevas, {errores} errores, {len(indice)} en total en {DESTINO}")
    if errores:
        print("Vuelve a ejecutar el script para reintentar las que fallaron.")
    return 0 if not errores else 1


if __name__ == "__main__":
    sys.exit(main())
