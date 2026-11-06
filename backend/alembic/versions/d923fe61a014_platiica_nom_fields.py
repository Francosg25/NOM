"""Store official NOM status and PLATIICA catalog change metadata."""

from alembic import op
import sqlalchemy as sa

revision = "d923fe61a014"
down_revision = "c812df402004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("publications", sa.Column("norm_status", sa.String(length=100), nullable=True))
    op.add_column("publications", sa.Column("product_scope", sa.Text(), nullable=True))
    op.add_column("publications", sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("publications", "source_updated_at")
    op.drop_column("publications", "product_scope")
    op.drop_column("publications", "norm_status")
