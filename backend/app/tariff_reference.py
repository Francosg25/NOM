"""Dated SNICE Annex 2.4.1 references, never a legal applicability decision.

The bundled index keeps product lookup independent of an external HTTP request.
Refreshes discover the Word compilation linked by SNICE and replace the index
only after validating its structure. NICO rows and qualifications stay attached
to their own tariff row; export-only tables are excluded from import lookup.
"""

from datetime import datetime, timezone
from functools import lru_cache
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urljoin, urlsplit

# Only bounded XML without DTD/entity declarations reaches this parser.
import xml.etree.ElementTree as ET  # nosec B405
from zipfile import BadZipFile, ZipFile

from bs4 import BeautifulSoup

from .collectors.core import CollectionError, SafeFetcher
from .config import get_settings

LIBRARY_URL = "https://www.snice.gob.mx/cs/avi/snice/biblioteca.juridica.html"
SOURCE_PAGE = "https://www.snice.gob.mx/cs/avi/snice/seguridad.normatividad.html"
BUNDLED = Path(__file__).parent / "resources" / "tariff_reference.json.gz"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
MAX_XML = 48 * 1024 * 1024
MAX_INDEX = 16 * 1024 * 1024
NOM_PATTERN = re.compile(r"NOM\s*-\s*(?:EM\s*-\s*)?\d{2,3}\s*-\s*[A-Z0-9/]+\s*-\s*\d{4}")
MONTHS = dict(
    zip(
        "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(),
        range(1, 13),
    )
)


def nom_codes(text):
    return list(dict.fromkeys(re.sub(r"\s+", "", m.group()) for m in NOM_PATTERN.finditer(text)))


def _text(element):
    if element.tag.endswith("}p"):
        return " ".join("".join(n.text or "" for n in element.findall(".//w:t", NS)).split())
    return " ".join(_text(p) for p in element.findall(".//w:p", NS)).strip()


def _document_date(paragraphs):
    dates = []
    for paragraph in paragraphs[:40]:
        match = re.search(r"(?:Modificación|Publicación).*?(\d{1,2}) de ([a-z]+) de (\d{4})", paragraph)
        if match and match[2] in MONTHS:
            dates.append(datetime(int(match[3]), MONTHS[match[2]], int(match[1])).date().isoformat())
    if not dates:
        raise ValueError("La compilación no identifica su fecha documental")
    return max(dates)


def parse_compilation(raw, source_url, *, retrieved_at=None):
    """Read explicit Word table rows; never infer NOMs from neighbouring codes."""
    parsed = urlsplit(source_url)
    if parsed.scheme != "https" or parsed.hostname != "www.snice.gob.mx" or not parsed.path.endswith(".docx"):
        raise ValueError("La referencia debe proceder del documento Word de SNICE")
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            if archive.getinfo("word/document.xml").file_size > MAX_XML:
                raise ValueError("Documento de referencia demasiado grande")
            xml = archive.read("word/document.xml")
    except (BadZipFile, KeyError) as exc:
        raise ValueError("SNICE no devolvió una compilación Word") from exc
    if b"\x00" in xml or b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise ValueError("No se permiten entidades XML en la referencia")
    root = ET.fromstring(xml)  # nosec B314
    body = root.find("w:body", NS)
    if body is None:
        raise ValueError("Documento sin cuerpo")
    paragraphs = [_text(e) for e in body if e.tag.endswith("}p")]
    active, ended, section, heading, default_norms = False, False, "", "", []
    relations = {}
    tables = 0
    for element in body:
        if element.tag.endswith("}p"):
            text = _text(element)
            if re.fullmatch(r"ANEXO\s+2\.4\.1", text):
                active = True
                continue
            if active and re.match(r"ANEXO\s+2\.(?!4\.1)\d", text):
                ended = True
                break
            if not active:
                continue
            numeral = re.match(r"([1-5])\s*\.\s*-", text)
            if numeral:
                section, heading, default_norms = numeral[1], text, []
            elif section == "3" and re.match(r"[IVXLCDM]+\.", text):
                heading = text
                # A heading can also name the cancelled predecessor. Only its
                # first NOM is the standard that introduces this table.
                default_norms = nom_codes(text)[:1]
        elif active and element.tag.endswith("}tbl") and section in {"1", "2", "3", "5"}:
            rows = element.findall("w:tr", NS)
            if not rows:
                continue
            header = [_text(c) for c in rows[0].findall("w:tc", NS)]
            if len(header) != 3 or "Fracción" not in header[0] or "Descripción" not in header[1]:
                raise ValueError("Estructura desconocida en el Anexo 2.4.1")
            tables += 1
            current = None
            for row_index, row in enumerate(rows[1:], 2):
                cells = [_text(c) for c in row.findall("w:tc", NS)]
                if not any(cells):
                    continue
                if len(cells) != 3:
                    raise ValueError(f"Fila arancelaria ambigua ({tables}, {row_index}): {cells!r}")
                code, description, qualification = cells
                if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", code):
                    current = {
                        "description": description,
                        "qualification": qualification,
                        "nom_codes": nom_codes(qualification) or default_norms.copy(),
                        "section": section,
                        "heading": heading,
                        "table": tables,
                        "row": row_index,
                        "nico_rows": [],
                    }
                    relations.setdefault(code.replace(".", ""), []).append(current)
                elif re.fullmatch(r"\d{2}", code) and current is not None:
                    current["nico_rows"].append([code, description, qualification])
                    current["nom_codes"] = list(
                        dict.fromkeys(current["nom_codes"] + nom_codes(qualification))
                    )
                elif not code and not description and not qualification:
                    continue
                else:
                    # Do not attach malformed rows or continuation notes to a
                    # preceding tariff code by guessing.
                    raise ValueError(f"Fracción o NICO no reconocido ({tables}, {row_index}): {cells!r}")
    if not active or not ended or tables < 2 or not relations:
        raise ValueError("Anexo arancelario ausente o incompleto")
    return {
        "schema": 1,
        "source_url": source_url,
        "source_page": SOURCE_PAGE,
        "document_date": _document_date(paragraphs),
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "tables": tables,
        "relations": relations,
    }


def _paths():
    folder = Path(get_settings().storage_path) / "_references"
    return folder / "tariff_reference.json.gz", folder / "tariff_reference_status.json"


@lru_cache(maxsize=2)
def _read(path, signature):
    with gzip.open(path, "rb") as stream:
        raw = stream.read(MAX_INDEX + 1)
    if len(raw) > MAX_INDEX:
        raise ValueError("Índice arancelario demasiado grande")
    data = json.loads(raw)
    if (
        data.get("schema") != 1
        or not isinstance(data.get("relations"), dict)
        or not all(
            isinstance(data.get(key), str)
            for key in ("document_date", "retrieved_at", "source_url", "source_sha256")
        )
    ):
        raise ValueError("Índice arancelario desconocido")
    return data


def load_reference():
    runtime, _ = _paths()
    candidates = []
    for path in (runtime, BUNDLED):
        try:
            stat = path.stat()
            candidates.append(_read(str(path), (stat.st_mtime_ns, stat.st_size)))
        except (OSError, ValueError, EOFError):
            continue
    # An older persistent cache must not override a newer bundled reference
    # after an application update. Equal document dates prefer the live copy.
    return max(candidates, key=lambda data: data["document_date"]) if candidates else None


def lookup_tariff(tariff):
    data = load_reference()
    if not data:
        return {"available": False, "matches": [], "source_page": SOURCE_PAGE}
    _, state_path = _paths()
    try:
        state = json.loads(state_path.read_text())
    except (OSError, ValueError):
        state = {}
    return {
        "available": True,
        "document_date": data["document_date"],
        "retrieved_at": data["retrieved_at"],
        "source_url": data["source_url"],
        "source_page": SOURCE_PAGE,
        "source_sha256": data["source_sha256"],
        "indexed_tariffs": len(data["relations"]),
        "base_tariff": tariff[:8],
        "requested_nico": tariff[8:] or None,
        "match_level": "fraccion_base",
        "last_refresh_at": state.get("checked_at"),
        "refresh_failed": bool(state.get("error")),
        "matches": data["relations"].get(tariff[:8], []),
    }


def _atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        name = stream.name
        try:
            stream.write(content)
            stream.close()
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def refresh_reference(*, fetcher=None, force=False):
    """At most daily; a failed refresh never replaces the last valid index."""
    target, state_path = _paths()
    now = datetime.now(timezone.utc)
    if not force:
        try:
            state = json.loads(state_path.read_text())
            checked = datetime.fromisoformat(state["checked_at"])
            if 0 <= (now - checked).total_seconds() < 86400:
                return False
        except (OSError, ValueError, KeyError, TypeError):
            pass
    own_client = fetcher is None
    client = fetcher
    try:
        if client is None:
            client = SafeFetcher(attempts=1)
        page = client(LIBRARY_URL)
        soup = BeautifulSoup(page.body, "html.parser")
        urls = set()
        for link in soup.select("a[href]"):
            url = urljoin(LIBRARY_URL, link["href"])
            parsed = urlsplit(url)
            if (
                parsed.hostname == "www.snice.gob.mx"
                and re.fullmatch(r"/~oracle/SNICE_DOCS/ACUERDO-REGLAS-SE-[A-Za-z0-9_.-]+\.docx", parsed.path)
                and parsed.scheme == "https"
            ):
                urls.add(url)
        if len(urls) != 1:
            raise ValueError("Compilación SNICE ausente o ambigua")
        source_url = urls.pop()
        result = client(source_url)
        previous = load_reference()
        if previous and hashlib.sha256(result.body).hexdigest() == previous["source_sha256"]:
            _atomic_write(state_path, json.dumps({"checked_at": now.isoformat(), "error": False}).encode())
            return True
        data = parse_compilation(result.body, source_url, retrieved_at=now.isoformat())
        if previous and (
            data["document_date"] < previous["document_date"]
            or len(data["relations"]) < len(previous["relations"]) / 2
        ):
            raise ValueError("La referencia recibida está incompleta o es anterior")
        if len(data["relations"]) < 100:
            raise ValueError("Referencia incompleta")
        _atomic_write(target, gzip.compress(json.dumps(data, ensure_ascii=False).encode(), mtime=0))
        _atomic_write(state_path, json.dumps({"checked_at": now.isoformat(), "error": False}).encode())
        _read.cache_clear()
        return True
    except (CollectionError, OSError, ValueError, ET.ParseError):
        _atomic_write(state_path, json.dumps({"checked_at": now.isoformat(), "error": True}).encode())
        return False
    finally:
        if own_client and client is not None:
            client.close()
