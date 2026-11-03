"""link cinema admins to keycloak accounts

Admins sign in at Keycloak now. The table keeps only which account manages
which cinema, keyed by the account's user id (the `sub` claim); e-mail and
password hash move out.

Existing admins are deleted in both directions: a row without its Keycloak
account, or without a password after a downgrade, can never sign in. They
are linked again with scripts/add_admin.py (see k8s/README.md).

Revision ID: 36578f67a025
Revises: 22f849fcd347
Create Date: 2026-11-03 20:53:34.501290

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '36578f67a025'
down_revision: Union[str, Sequence[str], None] = '22f849fcd347'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DELETE FROM cinema_admins")

    op.drop_index(op.f('ix_cinema_admins_email'), table_name='cinema_admins')
    op.drop_column('cinema_admins', 'email')
    op.drop_column('cinema_admins', 'password_hash')
    op.add_column('cinema_admins', sa.Column('subject', sqlmodel.sql.sqltypes.AutoString(), nullable=False))
    op.create_index(op.f('ix_cinema_admins_subject'), 'cinema_admins', ['subject'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM cinema_admins")

    op.drop_index(op.f('ix_cinema_admins_subject'), table_name='cinema_admins')
    op.drop_column('cinema_admins', 'subject')
    op.add_column('cinema_admins', sa.Column('password_hash', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.add_column('cinema_admins', sa.Column('email', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.create_index(op.f('ix_cinema_admins_email'), 'cinema_admins', ['email'], unique=True)
