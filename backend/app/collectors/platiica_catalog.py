"""Incremental discovery of NOM records in the official PLATIICA catalogue."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from typing import Callable
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .core import (
    Batch,
    CollectionError,
    Document,
    FetchResult,
    SafeFetcher,
    normalize_url,
    validate_url,
)

SITEMAP_URL = "https://platiica.economia.gob.mx/normalizacion/wp-sitemap.xml"
_POST_SITEMAP = re.compile(r"/normalizacion/wp-sitemap-posts-post-\d+\.xml")
_NOM_PAGE = re.compile(r"/normalizacion/(nom-[a-z0-9]+(?:-[a-z0-9]+)*)/?", re.I)
_NOM_CODE = re.compile(r"\bNOM-[A-Z0-9]+(?:-[A-Z0-9]+)+\b", re.I)
_MAX_NOM_PAGES = 10_000


def _xml_entries(raw: bytes) -> list[tuple[str, str | None]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise CollectionError("El sitemap oficial no contiene XML válido; inventario pendiente") from exc
    entries = []
    for element in root:
        fields = {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in element}
        if fields.get("loc"):
            entries.append((fields["loc"], fields.get("lastmod") or None))
    return entries


def _parse_lastmod(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CollectionError("El sitemap incluye una fecha lastmod inválida; sincronización pendiente") from exc
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _stored_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _page_text(soup: BeautifulSoup) -> tuple[str, BeautifulSoup]:
    node = soup.select_one(".entry-content") or soup.select_one("article") or soup.select_one("main") or soup.body
    if node is None:
        raise CollectionError("La ficha oficial no contiene una sección de contenido; requiere revisión")
    for element in node.select("script, style, nav, header, footer, form, noscript"):
        element.decompose()
    lines = [line.strip() for line in node.get_text("\n", strip=True).splitlines() if line.strip()]
    if not lines:
        raise CollectionError("La ficha oficial no contiene texto útil; requiere revisión")
    return "\n".join(lines), node


def _field(lines: list[str], label: str) -> str:
    prefix = re.compile(rf"^{re.escape(label)}\s*:\s*(.*)$", re.I)
    for index, line in enumerate(lines):
        match = prefix.match(line.strip())
        if match:
            value = match.group(1).strip()
            if value:
                return value
            for candidate in lines[index + 1 :]:
                if candidate.strip() and not candidate.strip().endswith(":"):
                    return candidate.strip()
    return ""


def _field_date(value: str) -> date | None:
    match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", value)
    if not match:
        return None
    try:
        return date(int(match[3]), int(match[2]), int(match[1]))
    except ValueError:
        return None


def _document(url: str, fetched: FetchResult, sitemap_lastmod: str | None) -> Document:
    if fetched.media_type not in {"text/html", "application/xhtml+xml"}:
        raise CollectionError("La ficha del catálogo no respondió como HTML; requiere revisión")
    if fetched.url and urlsplit(fetched.url).path.rstrip("/") != urlsplit(url).path.rstrip("/"):
        raise CollectionError("La ficha redirigió a otra ruta; requiere revisión")
    soup = BeautifulSoup(fetched.body, "html.parser")
    title = soup.select_one("h1")
    page_title = title.get_text(" ", strip=True) if title else ""
    content, node = _page_text(soup)
    lines = content.splitlines()
    code = _field(lines, "Clave de la Norma")
    code_match = _NOM_CODE.search(code.upper())
    status = _field(lines, "Estado de la Norma")
    product_scope = _field(lines, "Producto, servicio, proceso o sistema")
    official_title = _field(lines, "Título de la Norma") or page_title
    if not code_match or not official_title:
        raise CollectionError(
            "La ficha carece de clave o título estructurado; requiere revisión"
        )
    norm_code = code_match.group(0).upper()
    if not _NOM_CODE.fullmatch(norm_code):
        raise CollectionError("La clave oficial de la ficha no corresponde a una NOM")
    status = status or "Estado no informado"
    notes = []
    if status == "Estado no informado":
        notes.append("La ficha oficial no informa su estado; revisión pendiente")
    if not product_scope:
        notes.append("La ficha oficial no informa producto o servicio; revisión pendiente")
    modified = _parse_lastmod(sitemap_lastmod)
    links = set()
    for anchor in node.select("a[href]"):
        try:
            links.add(normalize_url(urljoin(url, anchor["href"])))
        except (CollectionError, AttributeError):
            continue
    return Document(
        official_id=f"PLATIICA:{norm_code}",
        url=url,
        title=f"{norm_code} - {official_title}",
        content=content,
        published_on=_field_date(_field(lines, "Fecha de publicación en el DOF")),
        kind="norma_vigente" if status.casefold() == "vigente" else "norma_no_vigente",
        raw=fetched.body,
        media_type=fetched.media_type,
        processing_note="; ".join(notes) or None,
        links=sorted(links),
        norm_status=status,
        product_scope=product_scope,
        source_updated_at=modified,
    )


def _discover(fetcher: Callable[[str], FetchResult]) -> tuple[list[tuple[str, str | None]], int]:
    index = _xml_entries(fetcher(SITEMAP_URL).body)
    sitemap_urls = []
    for location, _ in index:
        parts = urlsplit(location)
        if parts.hostname == "platiica.economia.gob.mx" and _POST_SITEMAP.fullmatch(parts.path):
            sitemap_urls.append(validate_url(location, "platiica"))
    if not sitemap_urls:
        raise CollectionError("El índice de PLATIICA no publicó sitemaps de fichas; inventario pendiente")

    pages: dict[str, str | None] = {}
    for sitemap_url in sorted(set(sitemap_urls)):
        for location, lastmod in _xml_entries(fetcher(sitemap_url).body):
            parts = urlsplit(location)
            if parts.hostname != "platiica.economia.gob.mx" or not _NOM_PAGE.fullmatch(parts.path.lower()):
                continue
            page_url = validate_url(location, "platiica")
            pages[page_url] = lastmod
            if len(pages) > _MAX_NOM_PAGES:
                raise CollectionError("El sitemap excede el límite operativo de páginas NOM")
    if not pages:
        raise CollectionError("Los sitemaps no contienen fichas NOM; no se declara un catálogo vacío")
    return sorted(pages.items()), len(set(sitemap_urls))


def collect_catalog(
    urls: list[str],
    continuation: dict | None,
    limit: int,
    known_updated: dict[str, datetime | None],
    *,
    fetcher: Callable[[str], FetchResult] | None = None,
) -> Batch:
    if urls != [SITEMAP_URL]:
        raise CollectionError("La fuente del catálogo requiere el sitemap oficial de PLATIICA")
    if not 1 <= limit <= 200:
        raise CollectionError("Límite de fichas debe estar entre 1 y 200")

    own_fetcher = fetcher is None
    client = SafeFetcher() if own_fetcher else fetcher
    try:
        if continuation is None:
            pages, sitemap_count = _discover(client)
            queue = []
            skipped = 0
            for page_url, lastmod in pages:
                remote = _parse_lastmod(lastmod)
                existing = _stored_datetime(known_updated.get(page_url))
                if existing is not None and remote is not None and remote <= existing:
                    skipped += 1
                    continue
                queue.append({"url": page_url, "lastmod": lastmod})
            state = {
                "version": 1,
                "queue": queue,
                "cursor": 0,
                "failed": [],
                "discovered": len(pages),
                "skipped": skipped,
                "sitemaps": sitemap_count,
            }
        else:
            state = dict(continuation)
            if state.get("version") != 1 or not isinstance(state.get("queue"), list):
                raise CollectionError("El punto de continuación del catálogo no es válido")
            state["queue"] = list(state["queue"])
            state["failed"] = list(state.get("failed", []))
            state["cursor"] = int(state.get("cursor", 0))
            if not 0 <= state["cursor"] <= len(state["queue"]):
                raise CollectionError("El cursor del catálogo está fuera de rango")

        documents = []
        errors = []
        failed = []
        batch_end = min(state["cursor"] + limit, len(state["queue"]))
        for item in state["queue"][state["cursor"] : batch_end]:
            page_url = validate_url(item["url"], "platiica")
            try:
                documents.append(_document(page_url, client(page_url), item.get("lastmod")))
            except CollectionError as exc:
                errors.append(f"{page_url}: {exc}")
                failed.append(item)
        state["failed"].extend(failed)
        state["cursor"] = batch_end

        if state["cursor"] < len(state["queue"]):
            next_state = state
            complete = False
        elif state["failed"]:
            next_state = {
                **state,
                "queue": state["failed"],
                "cursor": 0,
                "failed": [],
            }
            complete = False
        else:
            next_state = None
            complete = True
        coverage = (
            f"PLATIICA: {state['sitemaps']} sitemaps oficiales consultados; "
            f"{state['discovered']} descubiertas, {state['skipped']} sin cambios y "
            f"{state['discovered'] - state['skipped']} pendientes de actualización en esta pasada. "
            "El catálogo solo se considera sincronizado al completar la cola; no certifica aplicabilidad legal."
        )
        checks = [
            {
                "source": "PLATIICA",
                "sitemaps": state["sitemaps"],
                "discovered_nom_pages": state["discovered"],
                "unchanged_pages": state["skipped"],
                "pages_to_fetch": state["discovered"] - state["skipped"],
            }
        ]
        return Batch(documents, complete, next_state, coverage, errors=errors, checks=checks)
    finally:
        if own_fetcher:
            client.close()
