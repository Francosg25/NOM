"""Index explicit NOM references without scanning document bodies at startup."""

from alembic import op
import sqlalchemy as sa

revision = "b17d6408a075"
down_revision = "fa91c2d6e842"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "publication_history_index",
        sa.Column("publication_id", sa.Integer(), sa.ForeignKey("publications.id"), primary_key=True),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("versions.id"), nullable=False),
    )
    op.create_table(
        "publication_norm_references",
        sa.Column("norm_code", sa.String(100), primary_key=True),
        sa.Column("publication_id", sa.Integer(), sa.ForeignKey("publications.id"), primary_key=True),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("versions.id"), nullable=False),
        sa.Column("location", sa.String(20), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
    )
    op.create_index("ix_publications_demo_published", "publications", ["is_demo", "published_on", "id"])
    op.create_index("ix_audit_history_days", "audit", ["action", "entity_type", "id"])


def downgrade():
    op.drop_index("ix_audit_history_days", table_name="audit")
    op.drop_index("ix_publications_demo_published", table_name="publications")
    op.drop_table("publication_norm_references")
    op.drop_table("publication_history_index")
