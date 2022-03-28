"""Add Organization table

Revision ID: eb86981e00db
Revises: 4572c83cb6b6
Create Date: 2022-03-28 21:37:37.944844

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb86981e00db'
down_revision = '4572c83cb6b6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('organizations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('shortname', sa.String(length=16), nullable=True),
    sa.Column('url', sa.String(length=255), nullable=True),
    sa.Column('icon_url', sa.String(length=255), nullable=True),
    sa.Column('image_url', sa.String(length=255), nullable=True),
    sa.Column('visible', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('assets', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'assets', 'organizations', ['organization_id'], ['id'])
    op.add_column('parties', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'parties', 'organizations', ['organization_id'], ['id'])
    op.drop_column('parties', 'is_member')
    op.add_column('users', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'users', 'organizations', ['organization_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'users', type_='foreignkey')
    op.drop_column('users', 'organization_id')
    op.add_column('parties', sa.Column('is_member', sa.BOOLEAN(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'parties', type_='foreignkey')
    op.drop_column('parties', 'organization_id')
    op.drop_constraint(None, 'assets', type_='foreignkey')
    op.drop_column('assets', 'organization_id')
    op.drop_table('organizations')
    # ### end Alembic commands ###
