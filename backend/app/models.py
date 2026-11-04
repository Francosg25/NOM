from datetime import date, datetime, timezone
from typing import Any
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = 'sources'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(40))
    urls: Mapped[list] = mapped_column(JSON, default=list)
    expected_terms: Mapped[list] = mapped_column(JSON, default=list)
    frequency_hours: Mapped[int] = mapped_column(default=24)
    active: Mapped[bool] = mapped_column(default=True)
    coverage: Mapped[str] = mapped_column(Text, default='Validación en vivo pendiente')
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    schedule_enabled: Mapped[bool] = mapped_column(default=False)
    schedule_start: Mapped[date | None] = mapped_column(Date)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CatalogItem(Base):
    __tablename__ = 'catalog'
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('catalog.id'))
    name: Mapped[str] = mapped_column(String(300))
    model: Mapped[str | None] = mapped_column(String(200))
    part_number: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    technical: Mapped[dict] = mapped_column(JSON, default=dict)
    use: Mapped[str | None] = mapped_column(Text)
    tariff_code: Mapped[str | None] = mapped_column(String(30))
    nico: Mapped[str | None] = mapped_column(String(10))
    owner: Mapped[str | None] = mapped_column(String(200))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    synonyms: Mapped[list] = mapped_column(JSON, default=list)
    watched_norms: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(default=True)
    is_demo: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Publication(Base):
    __tablename__ = 'publications'
    __table_args__ = (UniqueConstraint('source_id', 'official_id', name='uq_publication_source_official'),
                      Index('ix_publications_demo_detected', 'is_demo', 'detected_at'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey('sources.id'))
    official_id: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(60), default='clasificacion_pendiente')
    published_on: Mapped[date | None] = mapped_column(Date)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    review_status: Mapped[str] = mapped_column(String(30), default='pendiente')
    processing_note: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(default=False)
    current_version_id: Mapped[int | None] = mapped_column(Integer)
    effective_on: Mapped[date | None] = mapped_column(Date)
    effective_verified: Mapped[bool] = mapped_column(default=False)


class Version(Base):
    __tablename__ = 'versions'
    __table_args__ = (UniqueConstraint('publication_id', 'sequence', name='uq_version_sequence'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey('publications.id'))
    sequence: Mapped[int] = mapped_column(default=1)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    evidence_key: Mapped[str | None] = mapped_column(String(600))
    media_type: Mapped[str] = mapped_column(String(120), default='text/html')
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processing_note: Mapped[str | None] = mapped_column(Text)
    links: Mapped[list] = mapped_column(JSON, default=list)


class Alert(Base):
    __tablename__ = 'alerts'
    __table_args__ = (UniqueConstraint('publication_id', 'catalog_id', name='uq_alert_catalog'),
                      Index('ix_alerts_catalog', 'catalog_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey('publications.id'))
    catalog_id: Mapped[int | None] = mapped_column(ForeignKey('catalog.id'))
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='pendiente')
    decision: Mapped[str] = mapped_column(String(30), default='propuesta')
    assigned_to: Mapped[str | None] = mapped_column(String(200))
    closure_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(200))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Comment(Base):
    __tablename__ = 'comments'
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey('alerts.id'))
    author: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey('sources.id'))
    status: Mapped[str] = mapped_column(String(30), default='queued')
    requested_by: Mapped[str] = mapped_column(String(200))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    continuation: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_count: Mapped[int] = mapped_column(default=0)
    new_count: Mapped[int] = mapped_column(default=0)
    modified_count: Mapped[int] = mapped_column(default=0)
    error_count: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    active_key: Mapped[str | None] = mapped_column(String(100), unique=True)


class SourceRun(Base):
    __tablename__ = 'source_runs'
    source_snapshot: Mapped[dict | None] = mapped_column(JSON)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey('jobs.id'))
    source_id: Mapped[int] = mapped_column(ForeignKey('sources.id'))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default='running')
    reviewed_count: Mapped[int] = mapped_column(default=0)
    new_count: Mapped[int] = mapped_column(default=0)
    modified_count: Mapped[int] = mapped_column(default=0)
    error_count: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    continuation: Mapped[dict | None] = mapped_column(JSON)


class Audit(Base):
    __tablename__ = 'audit'
    __table_args__ = (Index('ix_audit_entity_action', 'entity_type', 'entity_id', 'action', 'id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(100))
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Reevaluation(Base):
    """Durable, coalesced catalogue work. Saving a product never scans the archive."""
    __tablename__ = 'reevaluations'
    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int] = mapped_column(ForeignKey('catalog.id'), unique=True)
    requested_revision: Mapped[int] = mapped_column(default=1)
    completed_revision: Mapped[int] = mapped_column(default=0)
    cursor: Mapped[int] = mapped_column(default=0)
    actor: Mapped[str] = mapped_column(String(200))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    error: Mapped[str | None] = mapped_column(Text)
