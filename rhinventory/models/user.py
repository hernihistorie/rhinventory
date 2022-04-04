from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table, Index, Boolean, CheckConstraint
from sqlalchemy.orm import relationship, backref

from rhinventory.extensions import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(255))
    read_access = Column(Boolean(), nullable=False, default=False)
    write_access = Column(Boolean(), nullable=False, default=False)
    admin = Column(Boolean(), nullable=False, default=False)

    github_access_token = Column(String(255))
    github_id = Column(Integer)
    github_login = Column(String(255))

    party_id = Column(Integer, ForeignKey('parties.id'))
    party = relationship("Party")

    organization_id = Column(Integer, ForeignKey('organizations.id'))
    organization = relationship("Organization", backref=backref("users", order_by=id))

    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
    
    def __str__(self):
        return self.username or self.github_login