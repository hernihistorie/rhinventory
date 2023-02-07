import enum

from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table, Index, Boolean, CheckConstraint
from sqlalchemy.orm import relationship, backref

from rhinventory.extensions import db


class TransactionType(enum.Enum):
    unknown     = 0

    acquisition = 1
    disposal    = -1

    purchase    = 2
    sale        = -2

    donation_in = 3
    donation_out = -3

    creation    = 4
    loss        = -4

    borrow      = 5
    return_out  = -5

    return_in   = 6
    lend        = -6


class Transaction(db.Model):
    __tablename__ = 'transactions'
    id          = Column(Integer, primary_key=True)
    transaction_type = Column(Enum(TransactionType))
    user_id     = Column(Integer) # deprecated
    counterparty = Column(String) # deprecated
    cost        = Column(Numeric)
    note        = Column(Text)
    date        = Column(DateTime)

    our_party_id = Column(Integer, ForeignKey('parties.id'))
    counterparty_id = Column(Integer, ForeignKey('parties.id'))

    url         = Column(String)
    penouze_id  = Column(Integer)

    finalized     = Column(Boolean, default=True, server_default="true")

    our_party = relationship("Party", foreign_keys=our_party_id)
    counterparty_new = relationship("Party", foreign_keys=counterparty_id)
    assets      = relationship(
        "Asset",
        secondary='transaction_assets',
        overlaps="transactions")


transaction_assets = Table('transaction_assets', db.Model.metadata,
    Column('transaction_id', Integer, ForeignKey('transactions.id')),
    Column('asset_id', Integer, ForeignKey('assets.id'))
)
