from sqlalchemy.orm import DeclarativeBase, Mapped
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, AdminIndexView
from flask_github import GitHub
from flask_login import LoginManager

from simpleeval import EvalWithCompoundTypes

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

db.Model.asdict = lambda self: {c.name: getattr(self, c.name) for c in self.__table__.columns}
# TODO remove this to upgrade to sqlalchemy 2.0.0
db.Model.__allow_unmapped__ = True

admin = Admin(name="Sbírka Herní Archiv", template_mode='bootstrap2')
github = GitHub()
login_manager = LoginManager()

simple_eval = EvalWithCompoundTypes()
