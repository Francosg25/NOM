"""Explainable suggestions, never legal or import decisions."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol


def normalized(text: str) -> str:
    return "".join(
        "-" if c in "‐‑‒–—−" else c
        for c in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(c) and c != "\u00ad"
    )


@dataclass
class Match:
    reason: str
    evidence: str


def suggest(content: str, item) -> list[Match]:
    """Match only configured terms; even unknown documents enter the general inbox."""
    folded = normalized(content)
    found: list[Match] = []
    terms = [("palabra clave", x) for x in (item.keywords or [])]
    terms += [("sinónimo", x) for x in (item.synonyms or [])]
    terms += [("norma vigilada", x) for x in (item.watched_norms or [])]
    for category, term in terms:
        if not isinstance(term, str) or not term.strip():
            continue
        pattern = r"(?<!\w)" + re.escape(normalized(term.strip())) + r"(?!\w)"
        if category == "norma vigilada":
            parts = re.split(r"[\s-]+", normalized(term.strip()))
            pattern = r"(?<!\w)" + r"[\s-]*".join(re.escape(part) for part in parts) + r"(?!\w)"
        hit = re.search(pattern, folded)
        if hit:
            # Text offsets are approximate under Unicode folding; preserve enough surrounding text.
            excerpt = content[max(0, hit.start() - 90) : min(len(content), hit.end() + 160)]
            found.append(Match(f"Coincidencia de {category}: {term}", excerpt))
    tariff = re.sub(r"\D", "", item.tariff_code or "")
    nico = re.sub(r"\D", "", getattr(item, "nico", None) or "")
    if len(tariff) == 8:
        base = r"(?<!\d)" + r"[.\s-]*".join(tariff)
        exact = None
        if len(nico) == 2:
            exact = re.search(base + r"[.\s-]*" + r"[.\s-]*".join(nico) + r"(?!\d)", content)
            if exact:
                found.append(
                    Match(
                        f"Fracción y NICO configurados: {item.tariff_code} {nico}",
                        content[max(0, exact.start() - 80) : exact.end() + 120],
                    )
                )
        base_hit = None if exact else re.search(base + r"(?:[.\s-]*\d{2})?(?!\d)", content)
        if base_hit:
            found.append(
                Match(
                    f"Fracción base configurada: {item.tariff_code}",
                    content[max(0, base_hit.start() - 80) : base_hit.end() + 120],
                )
            )
    return found


class OptionalAIAnalyzer(Protocol):
    """Future adapters must return evidence and uncertainty, never an import verdict.

    This interface is not invoked by the first version and requires no paid service.
    """

    def propose(self, content: str, catalog: list[dict]) -> list[dict]: ...
