from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Пустые значения нужны только для безопасного обновления существующих записей.
    # Новые группы и заявки API и бот без Zoom-ссылки и почты не сохранят.
    op.add_column(
        "groups",
        sa.Column("zoom_url", sa.String(length=2048), nullable=False, server_default=""),
    )
    op.add_column(
        "bookings",
        sa.Column("email", sa.String(length=254), nullable=False, server_default=""),
    )
    op.alter_column("groups", "zoom_url", server_default=None)
    op.alter_column("bookings", "email", server_default=None)


def downgrade() -> None:
    op.drop_column("bookings", "email")
    op.drop_column("groups", "zoom_url")
