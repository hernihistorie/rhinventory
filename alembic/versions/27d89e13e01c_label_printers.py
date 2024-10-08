"""Label printers

Revision ID: 27d89e13e01c
Revises: aab311acf6d9
Create Date: 2024-08-15 18:57:57.462369

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '27d89e13e01c'
down_revision = 'aab311acf6d9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('label_printer_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'users', 'organizations', ['label_printer_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'users', type_='foreignkey')
    op.drop_column('users', 'label_printer_id')
    # ### end Alembic commands ###
