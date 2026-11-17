"""durable email notification cursor and retry state"""
from alembic import op
import sqlalchemy as sa

revision = "e74b90c7d1a"
down_revision = "c812df402004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_cursors",
        sa.Column("name", sa.String(80), primary_key=True),
        sa.Column("last_event_id", sa.Integer(), nullable=False),
        sa.Column("retry_after_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("notification_cursors")
