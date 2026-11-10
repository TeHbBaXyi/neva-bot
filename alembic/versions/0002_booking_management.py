from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("manage_token", sa.String(length=64), nullable=True))
    op.add_column("bookings", sa.Column("telegram_user_id", sa.BigInteger(), nullable=True))
    op.create_unique_constraint("uq_bookings_manage_token", "bookings", ["manage_token"])
    op.create_index("ix_bookings_telegram_user_id", "bookings", ["telegram_user_id"])


def downgrade() -> None:
    op.drop_index("ix_bookings_telegram_user_id", table_name="bookings")
    op.drop_constraint("uq_bookings_manage_token", "bookings", type_="unique")
    op.drop_column("bookings", "telegram_user_id")
    op.drop_column("bookings", "manage_token")
