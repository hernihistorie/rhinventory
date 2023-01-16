from typing import OrderedDict

import flask.templating
from flask import Blueprint, render_template

from rhinventory.models.file import File, FileCategory
from rhinventory.models.magdb import Magazine, MagazineIssue, MagazineIssueVersion, IssueStatus, MagazineIssueVersionFiles, MagDBFileType


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

    logos = {}
    for logo in MagazineIssueVersionFiles.query.filter(MagazineIssueVersionFiles.file_type==MagDBFileType.logo).all():
        magazine_id = logo.magazine_issue_version.magazine_issue.magazine_id
        if not magazine_id in logos:
            logos[magazine_id] = [logo]
        else:
            logos[magazine_id].append(logo)

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
                "logos": logos[issue.magazine_issue.magazine_id] if issue.magazine_issue.magazine_id in logos else [],
            }

    context["magazines"] = OrderedDict(
        sorted(
            context["magazines"].items(),
            key=lambda x: x[1]["magazine"].title,
        )
    )

    return render_template("magdb/miss-list.html", **context)
