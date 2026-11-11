"""Evidence-backed fallbacks for incomplete SIDOF API responses.

The portal's calendar and the original journal PDF are still official SIDOF
resources. Neither a weekend nor an HTTP 404 alone establishes an empty day.
"""

import hashlib
import io
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from pypdf import PdfReader

from .core import CollectionError, Document, _kind, _soup

ORIGIN = "https://sidof.segob.gob.mx"
PDF_MAX_BYTES = 64 * 1024 * 1024
MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def portal_calendar_absence(client, day, calendar):
    """Require the linked calendar's explicit disabled selector and no conflict.

    The portal rolls a non-publishing date back to the preceding edition. Validate
    that behavior too; accepting any successful landing page would be unsafe.
    """
    today = datetime.now(ZoneInfo("America/Mexico_City")).date()
    diaries = calendar.get("ListaDiarios")
    if day >= today or not isinstance(diaries, list):
        return None
    stamp = day.strftime("%d-%m-%Y")
    if any(not isinstance(row, dict) or row.get("fecha") == stamp for row in diaries):
        return None
    page_url = f"{ORIGIN}/welcome/{stamp}"
    page = client(page_url)
    if page.url and page.url.rstrip("/") != page_url:
        return None
    soup = _soup(page.body)
    css_path = f"/assets/css/calendarCss/{day.year}.css"
    if not soup.select_one(f'link[href="{css_path}"]'):
        return None
    field = soup.select_one("input#fechaPub[value]")
    try:
        displayed = datetime.strptime(field["value"], "%d-%m-%Y").date() if field else None
    except (ValueError, TypeError):
        return None
    if displayed is None or displayed >= day:
        return None
    css_url = ORIGIN + css_path
    css = client(css_url)
    if css.url and css.url != css_url:
        return None
    text = css.body.decode("utf-8", errors="strict")
    # A date in an unrelated CSS rule/comment is not an absence declaration.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    selector = f'td[data-day="{day.strftime("%d/%m/%Y")}"]'
    disabled, contradictory = False, False
    for selectors, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        if selector not in [part.strip() for part in selectors.split(",")]:
            continue
        if re.search(r"(?:^|;)\s*cursor\s*:\s*not-allowed\s*(?:!important)?\s*(?:;|$)", declarations, re.I):
            disabled = True
        elif re.search(r"\bborder\s*:|\bcursor\s*:", declarations, re.I):
            contradictory = True
    if not disabled or contradictory:
        return None
    return {
        "absence_basis": "sidof_portal_calendar",
        "calendar_url": css_url,
        "calendar_sha256": hashlib.sha256(css.body).hexdigest(),
        "calendar_page_url": page_url,
        "calendar_page_sha256": hashlib.sha256(page.body).hexdigest(),
        "calendar_displayed_date": str(displayed),
    }


class JournalRecovery:
    """Read the exact indexed page of an original, bounded journal PDF.

    Page-only entries often coexist with a normal HTML note in SIDOF. Scan the
    whole page for NOM terms so that additional headings on a shared page cannot
    be silently discarded. Cache one journal per batch, not one copy per note.
    """

    def __init__(self, client):
        self.client = client
        self.cached = None

    def recover(self, expected, note, day, relevant):
        code, diary = expected["id"], expected["diary"]
        page = note.get("pagina")
        section = note.get("codSeccion")
        if (
            isinstance(page, bool)
            or not re.fullmatch(r"[0-9]{1,4}", str(page))
            or not 1 <= int(page) <= 1500
            or section != "UNICA"
            or expected.get("page", page) != page
            or expected.get("section", section) != section
        ):
            raise CollectionError("SIDOF: página del PDF no verificable para esta referencia")
        url = f"{ORIGIN}/dof/sidof/documentos/pdf/{diary}"
        if self.cached is None or self.cached[0] != url:
            result = self.client(url)
            if (
                not result.body.startswith(b"%PDF-")
                or len(result.body) > PDF_MAX_BYTES
                or result.url
                and result.url != url
            ):
                raise CollectionError("SIDOF: la descarga no corresponde al PDF oficial solicitado")
            try:
                reader = PdfReader(io.BytesIO(result.body))
                if reader.is_encrypted or not 1 <= len(reader.pages) <= 1500:
                    raise ValueError("unsupported PDF")
            except Exception as exc:
                raise CollectionError("SIDOF: PDF oficial no procesable") from exc
            self.cached = url, result, reader
        _, result, reader = self.cached
        if int(page) > len(reader.pages):
            raise CollectionError("SIDOF: página ausente en el PDF oficial")
        try:
            content = (reader.pages[int(page) - 1].extract_text() or "").strip()
        except Exception as exc:
            raise CollectionError("SIDOF: no se pudo extraer la página del PDF oficial") from exc
        header = re.sub(r"\s+", " ", content[:350]).lower()
        first_line = re.sub(r"\s+", " ", content.splitlines()[0]).lower() if content else ""
        date_text = rf"\b{day.day}\s+de\s+{MONTHS[day.month - 1]}\s+de\s+{day.year}\b"
        # Exact date + page header prevents accepting a default/current journal.
        if (
            len(content) < 100
            or "diario oficial" not in header
            or not re.search(date_text, header)
            or not (
                first_line.startswith(f"{int(page)} ")
                or re.search(rf"diario oficial\s+{int(page)}(?:\s|$)", first_line)
            )
        ):
            raise CollectionError("SIDOF: la página del PDF no confirma fecha, número y texto")
        lines = content.splitlines()
        heading = re.compile(
            r"^(?:NORMA|PROYECTO|ACUERDO|AVISO|DECRETO|RESOLUCI[OÓ]N|CONVENIO|"
            r"CIRCULAR|DECLARATORIA|TIPO|TASA|TASAS|VALOR|[IÍ]NDICE|ANEXOS?|FE\s+de\s+erratas)\b"
        )
        title = expected.get("title", "")
        if not title:
            for i, line in enumerate(lines):
                if heading.match(line.strip()):
                    parts = [line.strip()]
                    for following in lines[i + 1 : i + 10]:
                        if not following.strip() or re.match(
                            r"Al margen|[A-ZÁÉÍÓÚ ]{15,}$", following.strip()
                        ):
                            break
                        parts.append(following.strip())
                    title = " ".join(parts)[:1500]
                    break
        title = title or f"Página {page} del Diario Oficial del {day.strftime('%d/%m/%Y')}"
        evidence = {
            "id": f"DOF:{code}",
            "title": title,
            "method": "official_pdf_page",
            "url": url,
            "page": int(page),
            "section": section,
            "pdf_sha256": hashlib.sha256(result.body).hexdigest(),
            "page_text_sha256": hashlib.sha256(content.encode()).hexdigest(),
        }
        # PDF page references are not necessarily separate legal instruments.
        selected = relevant(title) or relevant(content)

        # SIDOF emits an untitled image-page record immediately alongside the
        # same publication's normal titled record. Keep the page evidence, but
        # prefer the separately queued note when its entire heading matches.
        def heading_key(value):
            return "".join(c for c in unicodedata.normalize("NFKD", value).casefold() if c.isalnum())

        def norm_codes(value):
            value = re.sub(r"[\u2010-\u2015\u2212]", "-", unicodedata.normalize("NFKC", value)).upper()
            return {
                re.sub(r"\s", "", match)
                for match in re.findall(
                    r"\b(?:PROY\s*-\s*)?NOM\s*-\s*[A-Z0-9]+(?:\s*[-/]\s*[A-Z0-9]+)*\s*-\s*\d{4}\b", value
                )
            }

        if selected and not expected.get("title") and note.get("existeDoc") == "N":
            aliases = [
                entry
                for entry in expected.get("page_titles", [])
                if entry["id"] != code
                and relevant(entry["title"])
                and heading_key(entry["title"]) == heading_key(title)
            ]
            codes = norm_codes(content)
            represented = norm_codes("\n".join(entry["title"] for entry in expected.get("page_titles", [])))
            if len(aliases) == 1 and codes and codes <= represented:
                evidence["represented_by"] = f"DOF:{aliases[0]['id']}"
                selected = False
        evidence["selected"] = selected
        document = (
            Document(
                f"DOF:{code}",
                f"{ORIGIN}/notas/{code}",
                title,
                content,
                day,
                _kind(title),
                raw=result.body,
                media_type="application/pdf",
                links=[url + f"#page={page}"],
            )
            if selected
            else None
        )
        return document, evidence
