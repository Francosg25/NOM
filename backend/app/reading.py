"""Create a passive reading tree from saved evidence, never executable HTML.

Inline fragments are concatenated as in the original DOM. In particular,
`regulaci<span>ó</span>n` must not become three lines or three separate words.
This is a presentation of existing evidence; it does not rewrite saved versions.
"""

from functools import lru_cache

import json
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

MAX_SOURCE_BYTES = 12 * 1024 * 1024
DROP = {
    "script",
    "style",
    "head",
    "nav",
    "header",
    "footer",
    "form",
    "noscript",
    "iframe",
    "object",
    "embed",
    "button",
    "input",
    "svg",
    "template",
}
BLOCK = {
    "div",
    "p",
    "section",
    "article",
    "main",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "ul",
    "ol",
    "li",
    "pre",
    "figure",
    "figcaption",
}


def official_image(value):
    """Accept only raster figures under the official diary image directory.

    SIDOF's saved HTML still references its former sidofqa host. The production
    host serves those same diary images; keep all loading on the official site.
    """
    try:
        parsed = urlsplit(value)
        if parsed.hostname not in {"sidof.segob.gob.mx", "sidofqa.segob.gob.mx"}:
            return None
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            return None
        if (
            parsed.query
            or parsed.fragment
            or not re.fullmatch(
                r"/imagenes_diarios/[A-Za-z0-9_./-]+\.(?:png|jpg|jpeg|gif|webp)", parsed.path, re.I
            )
            or "/../" in parsed.path
        ):
            return None
        return urlunsplit(("https", "sidof.segob.gob.mx", parsed.path, "", ""))
    except (ValueError, TypeError):
        return None


def compact(value):
    return re.sub(r"\s+", " ", value.replace("\u00ad", ""))


def inline_text(nodes):
    def collect(node):
        if node["type"] == "text":
            return node["text"]
        if node["type"] == "break":
            return "\n"
        return "".join(collect(child) for child in node.get("children", []))

    return "".join(collect(node) for node in nodes).strip()


def _trim(nodes):
    while nodes and (nodes[0]["type"] == "break" or nodes[0].get("text", "x").strip() == ""):
        nodes.pop(0)
    while nodes and (nodes[-1]["type"] == "break" or nodes[-1].get("text", "x").strip() == ""):
        nodes.pop()
    return nodes


def has_figures(nodes):
    return any(node["type"] == "image" or has_figures(node.get("children", [])) for node in nodes)


def merge_inlines(nodes):
    """Source spans often split a word into many nodes with identical styling."""
    result = []
    for node in nodes:
        if result and node["type"] == result[-1]["type"] == "text":
            result[-1]["text"] += node["text"]
        elif result and node["type"] == result[-1]["type"] and node["type"] in {"strong", "em", "sup", "sub"}:
            result[-1]["children"] = merge_inlines(result[-1]["children"] + node["children"])
        else:
            result.append(node)
    return result


def inlines(parent):
    result = []
    for child in parent.children if isinstance(parent, Tag) else parent:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            value = compact(str(child))
            if value:
                result.append({"type": "text", "text": value})
            continue
        if not isinstance(child, Tag) or child.name in DROP:
            continue
        if child.name == "br":
            result.append({"type": "break"})
            continue
        if child.name == "img":
            url = official_image(child.get("src", ""))
            result.append({"type": "image", "src": url, "alt": str(child.get("alt", ""))[:500]})
            continue
        nested = inlines(child)
        style = child.get("style", "")
        kind = (
            "sup"
            if child.name == "sup" or re.search(r"vertical-align\s*:\s*super\b", style, re.I)
            else "sub"
            if child.name == "sub" or re.search(r"vertical-align\s*:\s*sub\b", style, re.I)
            else "strong"
            if child.name in {"b", "strong"}
            or re.search(r"font-weight\s*:\s*(?:bold|[7-9]00)\b", style, re.I)
            else "em"
            if child.name in {"i", "em"} or re.search(r"font-style\s*:\s*italic\b", style, re.I)
            else None
        )
        result.extend([{"type": kind, "children": nested}] if kind else nested)
    return merge_inlines(result)


def _heading_key(value):
    return "".join(char for char in unicodedata.normalize("NFKD", value).casefold() if char.isalnum())


def paragraph(node):
    content = _trim(inlines(node))
    text = inline_text(content)
    if not text and not has_figures(content):
        return None
    numbered = re.match(r"^(\d+(?:\.\d+)*\.?)[ \t]+\S", text)
    annotation = "ANOTACION" in node.get("class", []) and len(text) < 160 and text.isupper()
    heading = node.name in {"h1", "h2", "h3", "h4", "h5", "h6"} and not text.startswith("Al margen")
    if heading or annotation or numbered and len(text) < 180:
        level = 3 if numbered and "." in numbered[1].rstrip(".") else 2
        return {"type": "heading", "level": level, "inlines": content}
    return {"type": "paragraph", "inlines": content}


def blocks(parent, depth=0):
    if depth > 35:
        raise ValueError("Reading structure too deep")
    result, pending = [], []

    def flush():
        nonlocal pending
        pending = _trim(pending)
        if inline_text(pending) or has_figures(pending):
            result.append({"type": "paragraph", "inlines": pending})
        pending = []

    for child in parent.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            value = compact(str(child))
            if value.strip():
                pending.append({"type": "text", "text": value})
            elif pending:
                pending.append({"type": "text", "text": " "})
            continue
        if not isinstance(child, Tag) or child.name in DROP:
            continue
        if child.name not in BLOCK:
            # Keep inline text/figures in a paragraph rather than separating spans.
            pending.extend(inlines([child]))
            continue
        flush()
        if child.name == "table":
            rows = []
            for row in child.find_all("tr"):
                if row.find_parent("table") is not child:
                    continue
                cells = []
                for cell in row.find_all(["td", "th"], recursive=False):

                    def span(name):
                        raw = str(cell.get(name, "1"))
                        return int(raw) if raw.isdigit() and 1 <= int(raw) <= 1000 else 1

                    cells.append(
                        {
                            "header": cell.name == "th",
                            "row_span": span("rowspan"),
                            "col_span": span("colspan"),
                            "blocks": blocks(cell, depth + 1),
                        }
                    )
                if cells:
                    rows.append({"cells": cells})
            if rows:
                result.append({"type": "table", "rows": rows})
        elif child.name in {"ol", "ul"}:
            raw_start = str(child.get("start", "1"))
            items = [blocks(item, depth + 1) for item in child.find_all("li", recursive=False)]
            result.append(
                {
                    "type": "list",
                    "ordered": child.name == "ol",
                    "start": int(raw_start) if raw_start.isdigit() and len(raw_start) < 7 else 1,
                    "items": items,
                }
            )
        elif child.find(list(BLOCK), recursive=True):
            result.extend(blocks(child, depth + 1))
        else:
            entry = paragraph(child)
            if entry:
                result.append(entry)
    flush()
    return result


def plain_reading(content):
    """Conservative fallback when original HTML is unavailable.

    Preserve line boundaries rather than guessing paragraph/word boundaries in
    already flattened technical text. Normal HTML evidence avoids this fallback.
    """
    return [
        {"type": "paragraph", "inlines": [{"type": "text", "text": part.strip()}]}
        for part in re.split(r"\n\s*\n", content)
        if part.strip()
    ]


@lru_cache(maxsize=8)
def reading_tree(raw, media_type, content, title=""):
    html, source = None, "text"
    media_type = media_type.split(";", 1)[0].strip().lower()
    try:
        if (
            raw
            and len(raw) <= MAX_SOURCE_BYTES
            and (media_type == "application/json" or raw.lstrip().startswith(b"{"))
        ):
            payload = json.loads(raw)
            note = payload.get("Nota") if isinstance(payload, dict) else None
            if isinstance(note, list) and len(note) == 1:
                note = note[0]
            if isinstance(note, dict):
                html = next(
                    (
                        value
                        for key in ("cadenaContenido", "contenido")
                        if isinstance(value := note.get(key), str)
                        and value.strip()
                        and value.strip().lower() not in {"null", "none"}
                    ),
                    None,
                )
                source = "sidof_json"
        elif raw and len(raw) <= MAX_SOURCE_BYTES and media_type in {"text/html", "application/xhtml+xml"}:
            if re.search(rb"<\s*(?:!doctype|html|body|p|div|table|article|main|h[1-6]|ul|ol)\b", raw, re.I):
                html, source = raw, "html"
        if html:
            soup = BeautifulSoup(html, "html.parser")
            # Limit tree size before recursive formatting; never truncate a norm.
            if len(soup.find_all()) > 50000:
                raise ValueError("Reading structure too large")
            root = (
                soup.find(id=["DivDetalleNota", "DivDetalle"])
                or soup.find(class_="DetaDoc")
                or soup.find(["article", "main"])
                or soup.body
                or soup
            )
            result = blocks(root)
            if (
                result
                and result[0]["type"] == "heading"
                and _heading_key(inline_text(result[0]["inlines"])) == _heading_key(title)
            ):
                result.pop(0)  # The reader already shows the complete publication title.
            if result:
                return {"format": "structured", "source": source, "blocks": result}
    except (ValueError, TypeError, RecursionError, UnicodeError):
        pass
    return {"format": "plain", "source": "text", "blocks": plain_reading(content)}
