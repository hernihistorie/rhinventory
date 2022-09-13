"""A number of asset attribute tables

Revision ID: dab4e5bb9f5a
Revises: 20cd509a831e
Create Date: 2022-09-13 20:10:45.129454

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'dab4e5bb9f5a'
down_revision = '20cd509a831e'
branch_labels = None
depends_on = None

from sqlalchemy import orm
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ProductCode(Base):
    __tablename__ = 'product_codes'
    id: int          = sa.Column(sa.Integer, primary_key=True)  # type: ignore
    asset_id: int    = sa.Column(sa.Integer, sa.ForeignKey('assets.id'))  # type: ignore
    name: str        = sa.Column(sa.String, nullable=False)  # type: ignore

# in-progress asset table
class Asset(Base):
    __tablename__ = 'assets'
    id            = sa.Column(sa.Integer, primary_key=True)
    
    # old product_codes column
    product_codes = sa.Column(sa.ARRAY(sa.String))



def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('companies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('packagings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('platforms',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tags',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('company_aliases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('alias', sa.String(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('asset_assettag',
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('assettag_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['assettag_id'], ['tags.id'], )
    )
    op.create_table('asset_mediums',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('medium_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['medium_id'], ['media.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('asset_packaging',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('packaging_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['packaging_id'], ['packagings.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('asset_platform',
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('platform_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['platform_id'], ['platforms.id'], )
    )
    op.create_table('product_codes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.alter_column('assets', 'category',
               existing_type=postgresql.ENUM('unknown', 'game', 'console', 'computer', 'console_accesory', 'computer_accessory', 'computer_component', 'computer_mouse', 'keyboard', 'television', 'monitor', 'software', 'multimedia', 'receipt', 'literature', 'other', 'rewritable_media', name='assetcategory'),
               nullable=False)
    
    # Migrate product codes
    print("Migrating product codes...")
    
    bind = op.get_bind()
    session = orm.Session(bind=bind)

    asset: Asset
    for asset in session.query(Asset):
        for product_code in asset.product_codes or []:
            product_code_obj = ProductCode(name=product_code, asset_id=asset.id)
        
            session.add(product_code_obj)
        
    session.commit()
    
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('assets', 'category',
               existing_type=postgresql.ENUM('unknown', 'game', 'console', 'computer', 'console_accesory', 'computer_accessory', 'computer_component', 'computer_mouse', 'keyboard', 'television', 'monitor', 'software', 'multimedia', 'receipt', 'literature', 'other', 'rewritable_media', name='assetcategory'),
               nullable=True)
    op.drop_table('product_codes')
    op.drop_table('asset_platform')
    op.drop_table('asset_packaging')
    op.drop_table('asset_mediums')
    op.drop_table('asset_assettag')
    op.drop_table('company_aliases')
    op.drop_table('tags')
    op.drop_table('platforms')
    op.drop_table('packagings')
    op.drop_table('companies')
    # ### end Alembic commands ###
