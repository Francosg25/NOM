"""Explainable search for saved SIDOF publications using product information."""

import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..auth import Identity, identity
from ..db import get_db
from ..models import Publication, Source, Version
from ..schemas import ProductSearchInput
from ..matching import normalized

router = APIRouter(prefix="/api", tags=["product search"])

STOP_WORDS = {
    "and",
    "con",
    "del",
    "desde",
    "for",
    "las",
    "los",
    "para",
    "por",
    "the",
    "una",
    "uno",
    "unos",
    "unas",
    "uso",
    "de",
    "el",
    "en",
    "la",
    "o",
    "y",
}


def _description_terms(value: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalized(value))
    return list(dict.fromkeys(token for token in tokens if len(token) >= 3 and token not in STOP_WORDS))[:12]


def _tariff_pattern(value: str, allow_nico: bool = False) -> re.Pattern[str]:
    nico = r"(?:[.\s-]*\d{2})?" if allow_nico else ""
    return re.compile(r"(?<!\d)" + r"[.\s-]*".join(value) + nico + r"(?!\d)")


def _excerpt(content: str, start: int, end: int) -> str:
    return content[max(0, start - 100) : min(len(content), end + 180)].strip()


def _term_excerpt(content: str, terms: list[str]) -> str:
    folded = normalized(content)
    positions = [folded.find(term) for term in terms]
    positions = [position for position in positions if position >= 0]
    if not positions:
        return " ".join(content.split())[:280]
    start = min(positions)
    return _excerpt(content, start, start + max(len(term) for term in terms))


@router.post("/product-search")
def product_search(
    body: ProductSearchInput,
    db: Session = Depends(get_db),
    user: Identity = Depends(identity),
):
    value = body.value.strip()
    stmt = (
        select(Publication, Version, Source)
        .join(Version, Version.id == Publication.current_version_id)
        .join(Source, Source.id == Publication.source_id)
        .where(
            Publication.is_demo.is_(False),
            Source.kind == "sidof",
        )
    )

    tariff = ""
    base_tariff = ""
    terms: list[str] = []
    if body.mode == "fraccion":
        if not re.fullmatch(r"[0-9.\s-]+", value):
            raise HTTPException(422, "Ingresa una fracción mexicana de 8 dígitos, o 10 con NICO.")
        tariff = re.sub(r"\D", "", value)
        if len(tariff) not in (8, 10):
            raise HTTPException(422, "Ingresa una fracción mexicana de 8 dígitos, o 10 con NICO.")
        base_tariff = tariff[:8]
        search_codes = [tariff] if len(tariff) == 8 else [tariff, base_tariff]
        patterns = []
        for code in search_codes:
            chunks = [code[index : index + 2] for index in range(0, len(code), 2)]
            patterns.append("%" + "%".join(chunks) + "%")
        stmt = stmt.where(
            or_(
                *[Publication.title.ilike(pattern) for pattern in patterns],
                *[Version.content.ilike(pattern) for pattern in patterns],
            )
        )
    else:
        if len(value) < 4:
            raise HTTPException(422, "Describe el producto con al menos cuatro caracteres.")
        terms = _description_terms(value)
        if not terms:
            raise HTTPException(422, "Agrega palabras descriptivas del producto, como tipo, material o uso.")
        token_patterns = []
        for term in terms:
            token_patterns.extend((f"%{term}%", "%" + "%".join(term) + "%"))
        stmt = stmt.where(
            or_(
                *[Publication.title.ilike(pattern) for pattern in token_patterns],
                *[Version.content.ilike(pattern) for pattern in token_patterns],
            )
        )

    rows = db.execute(stmt).all()
    results = []
    tariff_pattern = _tariff_pattern(tariff) if tariff else None
    base_pattern = _tariff_pattern(base_tariff, allow_nico=True) if len(tariff) in (8, 10) else None

    for publication, version, source in rows:
        content = f"{publication.title}\n{version.content}"
        if tariff_pattern:
            match = tariff_pattern.search(content)
            match_type = "fraccion_exacta"
            if match and len(re.sub(r"\D", "", match.group())) > len(tariff):
                match_type = "fraccion_base"
            if not match and base_pattern:
                match = base_pattern.search(content)
                match_type = "fraccion_base"
            if not match:
                continue
            matched_terms = [tariff if match_type == "fraccion_exacta" else base_tariff]
            evidence = _excerpt(content, match.start(), match.end())
            score = 1 if match_type == "fraccion_exacta" else 0.8
        else:
            folded = normalized(content)
            matched_terms = [
                term for term in terms if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", folded)
            ]
            if not matched_terms:
                continue
            phrase_match = normalized(value) in folded
            score = len(matched_terms) / len(terms) + (0.25 if phrase_match else 0)
            evidence = _term_excerpt(content, matched_terms)
            match_type = "descripcion"

        results.append(
            {
                "publication": {
                    "id": publication.id,
                    "title": publication.title,
                    "official_id": publication.official_id,
                    "url": publication.url,
                    "kind": publication.kind,
                    "published_on": publication.published_on.isoformat()
                    if publication.published_on
                    else None,
                    "source_name": source.name,
                },
                "match": {
                    "type": match_type,
                    "score": round(score, 3),
                    "matched_terms": matched_terms,
                    "evidence": evidence,
                },
            }
        )

    results.sort(
        key=lambda result: (
            result["match"]["score"],
            result["publication"]["published_on"] or "",
            result["publication"]["id"],
        ),
        reverse=True,
    )
    return {
        "mode": body.mode,
        "value": re.sub(r"\D", "", value) if body.mode == "fraccion" else value,
        "total": len(results),
        "results": results[:30],
        "truncated": len(results) > 30,
        "disclaimer": (
            "Coincidencias textuales en publicaciones SIDOF guardadas. No determinan "
            "si una NOM aplica al producto ni sustituyen la clasificación arancelaria "
            "o revisión de la disposición oficial."
        ),
    }
