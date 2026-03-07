from collections import defaultdict
import json
from typing import Any, OrderedDict

import flask.templating
from flask import Blueprint, redirect, render_template, request
import yaml

from rhinventory.models.magdb import Magazine, MagazineIssue, MagazineIssueVersion, IssueStatus, \
    MagazineIssueVersionFiles, MagDBFileType
from rhinventory.service.public_magdb import PublicMagDBService

magdb_bp = Blueprint("magdb", __name__, url_prefix="/public-magdb")


@magdb_bp.route("/")
def index():
    # return render_template("magdb/index.html")
    return redirect('https://herniarchiv.cz/magazines/', 308)

def is_data_endpoint():
    return request.path.endswith('.json') or request.path.endswith('.yaml')

def render_yaml_data_template(template_name: str, context: dict[str, Any]):
    data_yaml = render_template(template_name, **context)
    if request.path.endswith('.yaml'):
        return data_yaml, 200, {'Content-Type': 'text/yaml'}
    elif request.path.endswith('.json'):
        data_json = json.dumps(yaml.load(data_yaml, Loader=yaml.FullLoader))
        return data_json, 200, {'Content-Type': 'application/json'}

@magdb_bp.route("/catalog.json")
@magdb_bp.route("/catalog.yaml")
@magdb_bp.route("/catalog")
def catalog():
    context = {
        "magazines": Magazine.query.order_by(Magazine.title).all(),
        "logos": {},
    }

    for logo in MagazineIssueVersionFiles.query.filter(MagazineIssueVersionFiles.file_type==MagDBFileType.logo).all():
        local_magazine_id = logo.magazine_issue_version.magazine_issue.magazine_id
        if local_magazine_id not in context["logos"]:
            context["logos"][local_magazine_id] = set()

        context["logos"][local_magazine_id].add(logo.file)

    if is_data_endpoint():
        return render_yaml_data_template("magdb/catalog.yaml.jinja2", context)
    # return render_template("magdb/catalog.html", **context)
    return redirect('https://herniarchiv.cz/magazines/catalog/', 308)


@magdb_bp.route("/catalog/magazine-detail/<int:magazine_id>.json")
@magdb_bp.route("/catalog/magazine-detail/<int:magazine_id>.yaml")
@magdb_bp.route("/catalog/magazine-detail/<int:magazine_id>")
@magdb_bp.route("/catalog/magazine-detail/<string:magazine_slug>.json")
@magdb_bp.route("/catalog/magazine-detail/<string:magazine_slug>.yaml")
@magdb_bp.route("/catalog/magazine-detail/<string:magazine_slug>")
def magazine_detail(magazine_id: int | None = None, magazine_slug: str | None = None):
    magazine = None
    if magazine_id:
        magazine = Magazine.query.get(magazine_id)
    elif magazine_slug:
        magazine = Magazine.query.filter_by(slug=magazine_slug).first()

    if not magazine:
        return "Magazine not found", 404

    assert isinstance(magazine, Magazine)

    context = {
        "magazine": magazine,
        "issues_by_year": defaultdict(list),
        "files": {
            "cover_pages": defaultdict(list),
            "index_pages": defaultdict(list),
            "logos": defaultdict(set),
        }
    }

    special_issues = []
    issue_ids = set()

    service = PublicMagDBService()
    new_data = service.list_magazine(magazine.id)

    for issue in new_data:
        issue_ids.add(issue.id)

        if issue.is_special_issue:
            special_issues.append(issue)
            continue

        context["issues_by_year"][issue.published_year].append(issue)

    if len(special_issues):
        context["issues_by_year"]["Speciály"] = special_issues

    # get logos

    logos = MagazineIssueVersionFiles.query \
        .join(MagazineIssueVersion).join(MagazineIssue) \
        .filter(MagazineIssueVersionFiles.file_type == MagDBFileType.logo) \
        .filter(MagazineIssueVersion.magazine_issue_id.in_(issue_ids)) \
        .all()

    for logo in logos:
        context["files"]["logos"][magazine.id].add(logo.file)


    if is_data_endpoint():
        return render_yaml_data_template("magdb/magazine_detail.yaml.jinja2", context)
    # return render_template("magdb/magazine_detail.html", **context)
    return redirect(f'https://herniarchiv.cz/magazines/catalog/{magazine.slug or magazine.id}', 308)


@magdb_bp.route("/miss-list.json")
@magdb_bp.route("/miss-list.yaml")
@magdb_bp.route("/miss-list")
def miss_list():
    context = {
        "missing_magazines": {},
        "magazines": {},
    }

    logos = defaultdict(set)
    for logo in MagazineIssueVersionFiles.query.filter(MagazineIssueVersionFiles.file_type==MagDBFileType.logo).all():
        magazine_id = logo.magazine_issue_version.magazine_issue.magazine_id
        logos[magazine_id].add(logo.file)

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

    if is_data_endpoint():
        return render_yaml_data_template("magdb/miss-list.yaml.jinja2", context)
    # return render_template("magdb/miss-list.html", **context)
    return redirect('https://herniarchiv.cz/magazines/miss-list/', 308)
