"""magdb file categories

Revision ID: a57843bea4c3
Revises: 9b8aa0e04d0a
Create Date: 2022-10-22 16:38:31.749756

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a57843bea4c3'
down_revision = '9b8aa0e04d0a'
branch_labels = None
depends_on = None


def upgrade():
    for new_category in ['cover_page', 'index_page', 'logo']:
        op.execute("COMMIT")
        op.execute(f"ALTER TYPE filecategory ADD VALUE '{new_category}' BEFORE 'dump'")


def downgrade():
    pass
