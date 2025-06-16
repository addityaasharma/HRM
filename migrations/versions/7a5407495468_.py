"""empty message

Revision ID: 7a5407495468
Revises: 35e8baa54209
Create Date: 2025-06-14 19:14:19.385052

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '7a5407495468'
down_revision = '35e8baa54209'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Sanitize data to prevent enum conversion error
    op.execute(
        """
        UPDATE adminleave
        SET leaveType = 'casual'
        WHERE leaveType NOT IN ('casual', 'sick') OR leaveType IS NULL
        """
    )

    # Step 2: Convert column to Enum
    with op.batch_alter_table('adminleave', schema=None) as batch_op:
        batch_op.alter_column('leaveType',
            existing_type=mysql.VARCHAR(length=120),
            type_=sa.Enum('casual', 'sick', name='leave_type_enum'),
            nullable=False)


def downgrade():
    with op.batch_alter_table('adminleave', schema=None) as batch_op:
        batch_op.alter_column('leaveType',
            existing_type=sa.Enum('casual', 'sick', name='leave_type_enum'),
            type_=mysql.VARCHAR(length=120),
            nullable=True)
