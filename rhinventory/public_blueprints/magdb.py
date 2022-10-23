from typing import OrderedDict

from flask import Blueprint, render_template

from rhinventory.models.file import File, FileCategory
from rhinventory.models.magdb import Magazine, MagazineIssue, MagazineIssueVersion, IssueStatus


magdb_bp = Blueprint("magdb", __name__, url_prefix="/public-magdb")

@magdb_bp.route("/")
def index():
    return render_template("magdb/index.html")

@magdb_bp.route("/catalog")
def catalog():
    context = {
        "magazines": Magazine.query.order_by(Magazine.title).all(),
        "logos": {},
    }


    # for issue in MagazineIssue.query.order(MagazineIssue.issue_number).all():
    #     magazine_id = issue.magazine_issue.magazine_id
    #     year = issue.published_year
    #
    #     if year not in context["magazine_issues_by_year"]:
    #         context["magazine_issues_by_year"][year] = []
    #
    #     context["magazine_issues_by_year"][year].append(issue)

    for logo in File.query.filter(File.category == FileCategory.logo).all():
        if logo.magazine_issue is not None:
            magazine_id = logo.magazine_issue.magazine_id

            if magazine_id not in context["logos"]:
                context["logos"][magazine_id] = []

            context["logos"][magazine_id].append(logo)

    return render_template("magdb/catalog.html", **context)


@magdb_bp.route("/catalog/magazine-detail/<int:magazine_id>")
def magazine_detail(magazine_id):
    return magazine_id


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
