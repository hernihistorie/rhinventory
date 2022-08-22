from flask_admin.contrib.sqla import ModelView
from flask import Blueprint, render_template

from rhinventory.models.magdb import Issuer, Magazine, MagazineIssue, Format, MagazineIssueVersion, MagazineIssueVersionPrice


class MagDbModelView(ModelView):
    can_edit = True
    can_create = True
    can_delete = True
    form_excluded_columns = [
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    ]


def add_magdb_views(admin, session):
    admin.add_view(MagDbModelView(Issuer, session, category="MagDB"))
    admin.add_view(MagDbModelView(Magazine, session, category="MagDB"))
    admin.add_view(MagDbModelView(MagazineIssue, session, category="MagDB"))
    admin.add_view(MagDbModelView(Format, session, category="MagDB"))
    admin.add_view(MagDbModelView(MagazineIssueVersion, session, category="MagDB"))
    admin.add_view(MagDbModelView(MagazineIssueVersionPrice, session, category="MagDB"))


magdb_bp = Blueprint("magdb", __name__, url_prefix="/public-magdb")

@magdb_bp.route("/")
def index():
    return render_template("magdb/index.html")


@magdb_bp.route("miss-list")
def miss_list():
    pass