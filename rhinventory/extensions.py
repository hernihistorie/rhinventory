from flask_debugtoolbar import DebugToolbarExtension
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_github import GitHub
from flask_login import LoginManager

from dictalchemy import make_class_dictable
from simpleeval import EvalWithCompoundTypes

db = SQLAlchemy()
make_class_dictable(db.Model)

admin = Admin()
debug_toolbar = DebugToolbarExtension()
github = GitHub()
login_manager = LoginManager()

simple_eval = EvalWithCompoundTypes()