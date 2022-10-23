from typing import OrderedDict

from flask import Blueprint, render_template

from rhinventory.models.file import File
from rhinventory.models.magdb import MagazineIssue, MagazineIssueVersion, IssueStatus


magdb_bp = Blueprint("magdb", __name__, url_prefix="/public-magdb")

@magdb_bp.route("/")
def index():
    return render_template("magdb/index.html")


@magdb_bp.route("/miss-list")
def miss_list():
    context = {
        "missing_magazines": {},
        "magazines": {},
    }

    for issue in MagazineIssueVersion.query.filter(
            MagazineIssueVersion.status != IssueStatus.have
    ).all():

        magazine_id = issue.magazine_issue.magazine_id
        if magazine_id not in context["missing_magazines"]:
            context["missing_magazines"][magazine_id] = []

        context["missing_magazines"][magazine_id].append(
            issue
        )

        if magazine_id not in context["magazines"]:
            context["magazines"][magazine_id] = {
                "magazine": issue.magazine_issue.magazine,
                "logos": File.query.filter(
                    File.magazine_issue_id == MagazineIssue.id,
                    MagazineIssue.magazine_id == magazine_id
                ).all()
            }

    context["magazines"] = OrderedDict(
        sorted(
            context["magazines"].items(),
            key=lambda x: x[1]["magazine"].title,
        )
    )

    return render_template("magdb/miss-list.html", **context)
