"""Durable catalogue queue, source scheduling and read indexes."""
from alembic import op
import sqlalchemy as sa

revision = 'b67d1201c003'
down_revision = '067cfa6eebf5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sources', sa.Column('expected_terms', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('versions', sa.Column('links', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('sources', sa.Column('schedule_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('sources', sa.Column('schedule_start', sa.Date(), nullable=True))
    op.add_column('sources', sa.Column('next_due_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table('reevaluations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('catalog_id', sa.Integer(), sa.ForeignKey('catalog.id'), nullable=False, unique=True),
        sa.Column('requested_revision', sa.Integer(), nullable=False),
        sa.Column('completed_revision', sa.Integer(), nullable=False),
        sa.Column('cursor', sa.Integer(), nullable=False),
        sa.Column('actor', sa.String(200), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('error', sa.Text(), nullable=True))
    op.create_index('ix_publications_demo_detected', 'publications', ['is_demo', 'detected_at'])
    op.create_index('ix_alerts_catalog', 'alerts', ['catalog_id'])
    op.create_index('ix_audit_entity_action', 'audit', ['entity_type', 'entity_id', 'action', 'id'])


def downgrade():
    op.drop_column('sources', 'expected_terms')
    op.drop_column('versions', 'links')
    op.drop_index('ix_audit_entity_action', 'audit')
    op.drop_index('ix_alerts_catalog', 'alerts')
    op.drop_index('ix_publications_demo_detected', 'publications')
    op.drop_table('reevaluations')
    op.drop_column('sources', 'next_due_at')
    op.drop_column('sources', 'schedule_start')
    op.drop_column('sources', 'schedule_enabled')
