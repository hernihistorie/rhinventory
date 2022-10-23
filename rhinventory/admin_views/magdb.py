import datetime
from dateutil.rrule import rrule, WEEKLY, MONTHLY, YEARLY
from typing import OrderedDict

import flask
from flask_admin import BaseView, expose
from flask import Blueprint, render_template
from wtforms import SelectField, SubmitField
from wtforms_alchemy import ModelForm

from rhinventory.admin_views import CustomModelView
from rhinventory.models.magdb import Issuer, Magazine, Periodicity, MagazineIssue, Format, MagazineIssueVersion, MagazineIssueVersionPrice, IssueStatus


class MagDbModelView(CustomModelView):
    can_edit = True
    can_create = True
    can_delete = True
    form_excluded_columns = [
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    ]
    column_exclude_list = ["created_at", "created_by", "updated_at", "updated_by"]


class MagDbMagazineView(MagDbModelView):
    list_template = "magdb/magazine/list_view.html"


class MagDbMagazineIssueView(MagDbModelView):
    list_template = "magdb/magazine_issue/list_view.html"

    @expose("/create_wizard", methods=["GET", "POST"])
    def create_wizard(self):
        create_form = self.get_create_form()
        prepared_values = {
            "magazine": Magazine.query.get(flask.request.args.get("magazine_id"))
        }

        last_issue = MagazineIssue.query.order_by(MagazineIssue.created_at.desc()).first()

        if last_issue is not None:
            if last_issue.is_special_issue:
                prepared_values["note"] = "previous was special"
            else:
                pass

            prepared_values["issuer"] = last_issue.issuer
            prepared_values["current_magazine_name"] = last_issue.current_magazine_name

            prepared_values["issue_number"] = last_issue.issue_number + 1

            date = datetime.datetime(day=last_issue.published_day or 1, month=last_issue.published_month, year=last_issue.published_year)
            value = None
            periodicity = last_issue.periodicity
            if periodicity == Periodicity.weekly:
                value = rrule(WEEKLY, dtstart=date.date(), interval=1).after(date)
            elif periodicity == Periodicity.biweekly:
                after_week = rrule(WEEKLY, dtstart=date.date(), interval=1).after(date)
                value = rrule(WEEKLY, dtstart=after_week.date(), interval=1).after(after_week)
            elif periodicity == Periodicity.monthly:
                value = rrule(MONTHLY, dtstart=date.date(), interval=1).after(date)
            elif periodicity == Periodicity.bimonthly:
                after_month = rrule(MONTHLY, dtstart=date.date(), interval=1).after(date)
                value = rrule(MONTHLY, dtstart=after_month.date(), interval=1).after(after_month)
            elif periodicity == Periodicity.annually:
                value = rrule(YEARLY, dtstart=date.date(), interval=1).after(date)
            elif periodicity == Periodicity.quarterly:
                after_month = rrule(MONTHLY, dtstart=date.date(), interval=1).after(date)
                for i in range(3):
                    after_month = rrule(MONTHLY, dtstart=after_month.date(), interval=1).after(after_month)
                value = after_month

            prepared_values["periodicity"] = last_issue.periodicity.name

            if value is not None:
                prepared_values["published_day"] = value.day
                prepared_values["published_month"] = value.month
                prepared_values["published_year"] = value.year

        form = create_form(flask.request.values, **prepared_values)

        if flask.request.method == "POST":
            self.create_model(form)

            if flask.request.values["submit"] == "Add and go to magazine issue":
                return flask.redirect(self.get_url("magdb_magazine_issue.index_view"))
            else:
                return flask.redirect(self.get_url("magdb_magazine.index_view"))

        return self.render(
            "magdb/magazine_issue/create_wizard.html",
            form=form,
            buttons=[
                ("Add and go to magazine issue", "submit"),
                ("Add and go to magazine", "submit"),
            ]
        )


class MagDbMagazineIssueVersionView(MagDbModelView):
    list_template = "magdb/magazine_issue_version/list_view.html"

    @expose("/create_wizard", methods=["GET", "POST"])
    def create_wizard(self):
        create_form = self.get_create_form()

        last_issue = MagazineIssue.query.get(flask.request.args.get("magazine_issue_id"))

        previous_to_last_issue = MagazineIssue.query.filter(MagazineIssue.created_at < last_issue.created_at)\
            .filter(MagazineIssue.magazine_id == last_issue.magazine_id)\
            .order_by(MagazineIssue.created_at.desc()).first()

        last_issue_version = MagazineIssueVersion.query.order_by(MagazineIssueVersion.created_at.desc()).first()

        prepared_values = {
            "magazine_issue": last_issue,
        }

        if last_issue_version is not None:
            prepared_values["format"] = last_issue_version.format
            prepared_values["name_suffix"] = last_issue_version.name_suffix
            prepared_values["form"] = last_issue_version.form.name
            prepared_values["issn_or_isbn"] = last_issue_version.issn_or_isbn
            prepared_values["barcode"] = last_issue_version.barcode

        last_issue_version = None
        if previous_to_last_issue is not None:
            last_issue_version = MagazineIssueVersion.query.order_by(
                MagazineIssueVersion.created_at.desc()
            ).filter(MagazineIssueVersion.magazine_issue_id == previous_to_last_issue.id).first()

        if last_issue_version is not None:
            prepared_values["format"] = last_issue_version.format
            prepared_values["name_suffix"] = last_issue_version.name_suffix
            prepared_values["form"] = last_issue_version.form.name

        form = create_form(flask.request.values, **prepared_values)
        if flask.request.method == "POST":
            self.create_model(form)
            if flask.request.values["submit"] == "Add and go to issue version":
                return flask.redirect(self.get_url("magdb_magazine_issue_version.index_view"))
            else:
                return flask.redirect(self.get_url("magdb_magazine_issue.index_view"))

        return self.render(
            "magdb/magazine_issue_version/create_wizard.html",
            form=form,
            buttons=[
                ("Add and go to magazine issue", "submit"),
                ("Add and go to issue version", "submit"),
            ]
        )


class MagDbMagazineIssueVersionPriceView(MagDbModelView):
    @expose("/create_wizard", methods=["GET", "POST"])
    def create_wizard(self):
        create_form = self.get_create_form()

        prepared_values = {
            "issue_version": MagazineIssueVersion.query.get(flask.request.args.get("magazine_issue_version_id"))
        }

        form = create_form(flask.request.values, **prepared_values)
        if flask.request.method == "POST":
            self.create_model(form)
            return flask.redirect(self.get_url("magdb_magazine_issue_version.index_view"))

        return self.render(
            "magdb/magazine_issue_version_price/create_wizard.html",
            form=form,
            buttons=[
                ("Add and return to issue version ", "submit"),
            ]
        )


def add_magdb_views(admin, session):
    admin.add_view(MagDbModelView(Issuer, session, category="MagDB"))
    admin.add_view(MagDbMagazineView(Magazine, session, category="MagDB", endpoint="magdb_magazine"))
    admin.add_view(MagDbMagazineIssueView(MagazineIssue, session, category="MagDB", endpoint="magdb_magazine_issue"))
    admin.add_view(MagDbModelView(Format, session, category="MagDB"))
    admin.add_view(MagDbMagazineIssueVersionView(MagazineIssueVersion, session, category="MagDB", endpoint="magdb_magazine_issue_version"))
    admin.add_view(MagDbMagazineIssueVersionPriceView(MagazineIssueVersionPrice, session, category="MagDB", endpoint="magdb_magazine_issue_version_price"))


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

        context["magazines"][magazine_id] = issue.magazine_issue.magazine.title

    context["magazines"] = OrderedDict(
        sorted(
            context["magazines"].items(),
            key=lambda x: x[1]
        )
    )

    return render_template("magdb/miss-list.html", **context)