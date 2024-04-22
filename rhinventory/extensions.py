from flask_debugtoolbar import DebugToolbarExtension
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, AdminIndexView
from flask_github import GitHub
from flask_login import LoginManager

from simpleeval import EvalWithCompoundTypes

db = SQLAlchemy()

db.Model.asdict = lambda self: {c.name: getattr(self, c.name) for c in self.__table__.columns}
# TODO remove this to upgrade to sqlalchemy 2.0.0
db.Model.__allow_unmapped__ = True

admin = Admin()
debug_toolbar = DebugToolbarExtension()
github = GitHub()
login_manager = LoginManager()

simple_eval = EvalWithCompoundTypes()
