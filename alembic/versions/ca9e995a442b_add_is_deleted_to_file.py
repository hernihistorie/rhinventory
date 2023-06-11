"""Add is_deleted to file

Revision ID: ca9e995a442b
Revises: 9f817789cd74
Create Date: 2023-06-11 13:40:19.849231

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ca9e995a442b'
down_revision = '9f817789cd74'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('files', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('files', 'is_deleted')
    # ### end Alembic commands ###
