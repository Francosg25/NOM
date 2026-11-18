"""Small, durable reference index for opt-in history. No source calls in HTTP requests."""

import re

from sqlalchemy import delete, func, or_, select

from .models import Publication, PublicationHistoryIndex, PublicationNormReference, Source, Version

# Keep the number, issuer, year and emergency marker. PROY is an instrument
# prefix, whereas EM is part of a different identifier. Never merge years.
_DASH = r"[\-‐‑‒–—−]"
_SEP = rf"\s*{_DASH}\s*"
_CODE = re.compile(
    rf"(?<![A-Z0-9])(?:PROY{_SEP})?NOM{_SEP}(?:(EM){_SEP})?"
    rf"(\d{{2,4}}){_SEP}([A-Z][A-Z0-9]{{0,14}}(?:\s*/\s*[A-Z][A-Z0-9]{{0,14}})*)"
    rf"{_SEP}((?:19|20)\d{{2}})(?![A-Z0-9])",
    re.I,
)


def reference_matches(value):
    """Return canonical codes and verbatim context, preserving accents and offsets."""
    for hit in _CODE.finditer(value or ""):
        emergency, number, issuer, year = hit.groups()
        code = f"NOM-{'EM-' if emergency else ''}{number}-{re.sub(r'\s+', '', issuer).upper()}-{year}"
        yield code, " ".join(value[max(0, hit.start() - 110) : hit.end() + 190].split())


def primary_codes(publication):
    # A title or official identifier identifies the selected NOM. A reference
    # buried in its bibliography must not become an identity for that NOM.
    return sorted(
        {code for text in (publication.title, publication.official_id) for code, _ in reference_matches(text)}
    )


def index_publication(db, publication, version):
    db.execute(
        delete(PublicationNormReference).where(PublicationNormReference.publication_id == publication.id)
    )
    references = {}
    for location, value in (
        ("title", publication.title),
        ("identifier", publication.official_id),
        ("text", version.content),
    ):
        for code, snippet in reference_matches(value):
            references.setdefault(code, (location, snippet))
    db.add_all(
        [
            PublicationNormReference(
                norm_code=code,
                publication_id=publication.id,
                version_id=version.id,
                location=location,
                snippet=snippet,
            )
            for code, (location, snippet) in references.items()
        ]
    )
    marker = db.get(PublicationHistoryIndex, publication.id)
    if marker:
        marker.version_id = version.id
    else:
        db.add(PublicationHistoryIndex(publication_id=publication.id, version_id=version.id))


def pending_query(is_demo=None):
    stmt = (
        select(Publication.id)
        .join(Source, Publication.source_id == Source.id)
        .outerjoin(PublicationHistoryIndex, PublicationHistoryIndex.publication_id == Publication.id)
        .where(
            Source.kind == "sidof",
            Publication.current_version_id.is_not(None),
            or_(
                PublicationHistoryIndex.version_id.is_(None),
                PublicationHistoryIndex.version_id != Publication.current_version_id,
            ),
        )
    )
    return stmt.where(Publication.is_demo == is_demo) if is_demo is not None else stmt


def pending_count(db, is_demo=False):
    return db.scalar(select(func.count()).select_from(pending_query(is_demo).subquery())) or 0


def index_history_batch(db, limit=10):
    # Read one document body at a time, outside HTTP and startup. A marker for
    # zero matches prevents repeatedly scanning the same bibliography-free copy.
    ids = db.scalars(pending_query().order_by(Publication.id).limit(limit)).all()
    for publication_id in ids:
        publication = db.get(Publication, publication_id)
        version = db.get(Version, publication.current_version_id)
        if version:
            index_publication(db, publication, version)
        db.commit()
    return len(ids)
