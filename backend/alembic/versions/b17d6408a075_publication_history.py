"""Index explicit NOM references without scanning document bodies at startup."""

from alembic import op
import sqlalchemy as sa

revision = "b17d6408a075"
down_revision = "fa91c2d6e842"
branch_labels = None
depends_on = None


def _table_names():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name):
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _verify_columns(table_name, expected):
    actual = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
    if actual != expected:
        raise RuntimeError(
            f"La tabla parcial {table_name} tiene columnas inesperadas: "
            f"esperadas={sorted(expected)}, actuales={sorted(actual)}"
        )


def upgrade():
    # SQLite DDL is not transactional. If App Service loses access to its mounted
    # storage halfway through this migration, keep the successfully created
    # objects and resume with only the missing ones on the next startup.
    if "publication_history_index" not in _table_names():
        op.create_table(
            "publication_history_index",
            sa.Column("publication_id", sa.Integer(), sa.ForeignKey("publications.id"), primary_key=True),
            sa.Column("version_id", sa.Integer(), sa.ForeignKey("versions.id"), nullable=False),
        )
    else:
        _verify_columns("publication_history_index", {"publication_id", "version_id"})

    if "publication_norm_references" not in _table_names():
        op.create_table(
            "publication_norm_references",
            sa.Column("norm_code", sa.String(100), primary_key=True),
            sa.Column("publication_id", sa.Integer(), sa.ForeignKey("publications.id"), primary_key=True),
            sa.Column("version_id", sa.Integer(), sa.ForeignKey("versions.id"), nullable=False),
            sa.Column("location", sa.String(20), nullable=False),
            sa.Column("snippet", sa.Text(), nullable=False),
        )
    else:
        _verify_columns(
            "publication_norm_references",
            {"norm_code", "publication_id", "version_id", "location", "snippet"},
        )

    if "ix_publications_demo_published" not in _index_names("publications"):
        op.create_index("ix_publications_demo_published", "publications", ["is_demo", "published_on", "id"])
    if "ix_audit_history_days" not in _index_names("audit"):
        op.create_index("ix_audit_history_days", "audit", ["action", "entity_type", "id"])


def downgrade():
    op.drop_index("ix_audit_history_days", table_name="audit")
    op.drop_index("ix_publications_demo_published", table_name="publications")
    op.drop_table("publication_norm_references")
    op.drop_table("publication_history_index")
