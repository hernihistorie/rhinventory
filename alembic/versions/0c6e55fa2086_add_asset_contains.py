"""Add asset contains

Revision ID: 0c6e55fa2086
Revises: 0923c8b71af8
Create Date: 2022-11-07 18:30:58.725346

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0c6e55fa2086'
down_revision = '0923c8b71af8'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('assets', sa.Column('location_id_new', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'assets', 'assets', ['location_id_new'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'assets', type_='foreignkey')
    op.drop_column('assets', 'location_id_new')
    # ### end Alembic commands ###
