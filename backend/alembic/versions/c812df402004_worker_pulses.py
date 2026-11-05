"""Persistent worker liveness for web and separate worker modes."""
from alembic import op
import sqlalchemy as sa

revision = 'c812df402004'
down_revision = 'b67d1201c003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('worker_pulses',
        sa.Column('name', sa.String(40), primary_key=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('consecutive_errors', sa.Integer(), nullable=False))


def downgrade():
    op.drop_table('worker_pulses')
