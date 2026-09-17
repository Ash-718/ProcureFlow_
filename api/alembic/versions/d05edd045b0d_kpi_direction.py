"""kpi direction

Every KPI must say which way is good.  Achievement can never be judged by
comparing validated_value with target_value alone: 6 minutes against a target of
7 is a success, 93 percent against a target of 95 is not, and the numbers by
themselves cannot tell the two apart.

Revision ID: d05edd045b0d
Revises: 2c1d8d82eac8
Create Date: 2026-09-17 20:49:11.634811
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d05edd045b0d"
down_revision: Union[str, None] = "2c1d8d82eac8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

kpi_direction = sa.Enum("HIGHER_IS_BETTER", "LOWER_IS_BETTER", name="kpi_direction")


def upgrade() -> None:
    kpi_direction.create(op.get_bind(), checkfirst=True)

    # Added nullable first so the migration works on a table that already holds
    # rows, then backfilled, then made mandatory.
    op.add_column("kpi", sa.Column("direction", kpi_direction, nullable=True))

    # Any row that predates this column has no recorded direction. The only rows
    # in this prototype are seeded ones, which the seed rewrites with the correct
    # direction on the next reset. On a database with real rows, every KPI
    # carried over by this statement needs reviewing before its achievement is
    # computed.
    op.execute("UPDATE kpi SET direction = 'HIGHER_IS_BETTER' WHERE direction IS NULL")

    op.alter_column("kpi", "direction", nullable=False)


def downgrade() -> None:
    op.drop_column("kpi", "direction")
    kpi_direction.drop(op.get_bind(), checkfirst=True)
