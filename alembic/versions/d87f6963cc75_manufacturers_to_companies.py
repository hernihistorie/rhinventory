"""Manufacturers to companies

Revision ID: d87f6963cc75
Revises: 5f970ea791b9
Create Date: 2022-10-23 20:15:38.093682

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd87f6963cc75'
down_revision = '5f970ea791b9'
branch_labels = None
depends_on = None



from sqlalchemy import orm
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Company(Base):
    __tablename__ = 'companies'
    id: int          = sa.Column(sa.Integer, primary_key=True)  # type: ignore
    name: str        = sa.Column(sa.String, nullable=False)  # type: ignore

def asset_n_to_n_table(other_table) -> sa.Table:
    other_name = other_table.__name__.lower()
    return sa.Table(
        f"asset_{other_name}",
        Base.metadata,
        sa.Column("asset_id", sa.ForeignKey("assets.id")),
        sa.Column(f"{other_name}_id", sa.ForeignKey(other_table.id)),
    )

asset_company_table = asset_n_to_n_table(Company)

class Asset(Base):
    __tablename__ = 'assets'
    id            = sa.Column(sa.Integer, primary_key=True)
    name          = sa.Column(sa.String, nullable=False)
    manufacturer  = sa.Column(sa.String)
    companies     = relationship(Company, secondary=asset_company_table, backref="assets")


def upgrade():
    bind = op.get_bind()
    session = orm.Session(bind=bind)

    companies: dict[str, Company] = {}

    print("Iterating over assets")

    asset: Asset
    for asset in session.query(Asset).order_by(Asset.id):
        if not asset.manufacturer:
            continue
        manufacturers = map(str.strip, asset.manufacturer.replace("\n", ";").split(";"))

        for manufacturer in manufacturers:
            if not manufacturer:
                continue
            if manufacturer.lower() in companies:
                company = companies[manufacturer.lower()]
                asset.companies.append(company)
                session.add(asset)
            else:
                company = Company(name=manufacturer)
                session.add(company)
                companies[manufacturer.lower()] = company
                print(f"New company: {company.name}")
    
    print("Committing")

    session.commit()


def downgrade():
    pass

