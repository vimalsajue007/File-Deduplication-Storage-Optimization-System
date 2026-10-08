"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

BigInt = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
MYSQL_OPTS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # duplicate_groups is created before files; its FK to files is added afterwards (circular reference)
    op.create_table(
        "duplicate_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("file_size", BigInt, nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("original_file_id", sa.Integer(), nullable=True),
        sa.Column("total_storage", BigInt, nullable=False),
        sa.Column("potential_savings", BigInt, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_duplicate_groups_owner_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_duplicate_groups"),
        sa.UniqueConstraint("owner_id", "content_hash", name="uq_duplicate_groups_owner_hash"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_duplicate_groups_owner_id", "duplicate_groups", ["owner_id"])

    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("size_bytes", BigInt, nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=False),
        sa.Column("extension", sa.String(32), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("status_message", sa.String(500), nullable=True),
        sa.Column("is_protected", sa.Boolean(), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False),
        sa.Column("duplicate_group_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_files_owner_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["duplicate_group_id"], ["duplicate_groups.id"], name="fk_files_duplicate_group_id_duplicate_groups", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_files"),
        sa.UniqueConstraint("storage_key", name="uq_files_storage_key"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_files_owner_id", "files", ["owner_id"])
    op.create_index("ix_files_extension", "files", ["extension"])
    op.create_index("ix_files_category", "files", ["category"])
    op.create_index("ix_files_status", "files", ["status"])
    op.create_index("ix_files_is_duplicate", "files", ["is_duplicate"])
    op.create_index("ix_files_duplicate_group_id", "files", ["duplicate_group_id"])
    op.create_index("ix_files_uploaded_at", "files", ["uploaded_at"])
    op.create_index("ix_files_owner_uploaded", "files", ["owner_id", "uploaded_at"])
    op.create_index("ix_files_owner_size", "files", ["owner_id", "size_bytes"])

    if op.get_bind().dialect.name != "sqlite":  # SQLite cannot ALTER TABLE ADD CONSTRAINT
        op.create_foreign_key(
            "fk_duplicate_groups_original_file_id_files", "duplicate_groups", "files",
            ["original_file_id"], ["id"], ondelete="SET NULL",
        )

    op.create_table(
        "file_hashes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("algorithm", sa.String(16), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", BigInt, nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], name="fk_file_hashes_file_id_files", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_file_hashes"),
        sa.UniqueConstraint("file_id", name="uq_file_hashes_file_id"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_file_hashes_owner_sha256", "file_hashes", ["owner_id", "sha256"])

    op.create_table(
        "file_metadata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("extension", sa.String(32), nullable=False),
        sa.Column("declared_mime", sa.String(255), nullable=True),
        sa.Column("detected_mime", sa.String(255), nullable=False),
        sa.Column("signature", sa.String(64), nullable=True),
        sa.Column("is_text", sa.Boolean(), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], name="fk_file_metadata_file_id_files", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_file_metadata"),
        sa.UniqueConstraint("file_id", name="uq_file_metadata_file_id"),
        **MYSQL_OPTS,
    )

    op.create_table(
        "deletion_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("size_bytes", BigInt, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("was_duplicate", sa.Boolean(), nullable=False),
        sa.Column("was_original", sa.Boolean(), nullable=False),
        sa.Column("duplicate_group_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_deletion_history_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_deletion_history"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_deletion_history_user_id", "deletion_history", ["user_id"])
    op.create_index("ix_deletion_history_deleted_at", "deletion_history", ["deleted_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_audit_logs_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_action_resource_created", "audit_logs", ["action", "resource_id", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("fk_duplicate_groups_original_file_id_files", "duplicate_groups", type_="foreignkey")
    for table in ("audit_logs", "deletion_history", "file_metadata", "file_hashes", "files", "duplicate_groups", "users"):
        op.drop_table(table)
