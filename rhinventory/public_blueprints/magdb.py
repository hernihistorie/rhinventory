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

    for logo in File.query.filter(File.category == FileCategory.logo).all():
        if logo.magazine_issue is not None:
            magazine_id = logo.magazine_issue.magazine_id

            if magazine_id not in context["logos"]:
                context["logos"][magazine_id] = []

            context["logos"][magazine_id].append(logo)

    return render_template("magdb/catalog.html", **context)


@magdb_bp.route("/catalog/magazine-detail/<int:magazine_id>")
def magazine_detail(magazine_id):
    context = {
        "magazine": Magazine.query.get(magazine_id),
        "issues_by_year": {},
        "files": {
            "cover_pages": {}
        }
    }

    special_issues = []

    for file in File.query.filter(File.category == FileCategory.cover_page).all():
        issue_version_id = file.magazine_issue_version_id

        if issue_version_id is None:
            continue

        if issue_version_id not in context["files"]["cover_pages"]:
            context["files"]["cover_pages"][issue_version_id] = []

        context["files"]["cover_pages"][issue_version_id].append(file)

    for issue in MagazineIssue.query.filter(
            MagazineIssue.magazine_id == magazine_id
    ).order_by(MagazineIssue.published_year, MagazineIssue.published_month, MagazineIssue.published_day).all():

        if issue.is_special_issue:
            special_issues.append(issue)
            continue

        if issue.published_year not in context["issues_by_year"]:
            context["issues_by_year"][issue.published_year] = []

        context["issues_by_year"][issue.published_year].append(issue)

    if len(special_issues):
        context["issues_by_year"]["Speciály"] = special_issues

    return render_template("magdb/magazine_detail.html", **context)


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
