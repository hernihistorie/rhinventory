import datetime
from dateutil.rrule import rrule, WEEKLY, MONTHLY, YEARLY

import flask
from flask_admin import BaseView, expose
from flask import Blueprint, render_template
from wtforms import SelectField, SubmitField
from wtforms_alchemy import ModelForm

from rhinventory.admin_views import CustomModelView
from rhinventory.models.magdb import Issuer, Magazine, Periodicity, MagazineIssue, Format, MagazineIssueVersion, MagazineIssueVersionPrice


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


class IssueForm(ModelForm):
    class Meta:
        model = MagazineIssue
        exclude = ["created_at", "created_by", "updated_at", "updated_by"]

    periodicity = SelectField(choices=Periodicity.choices(), coerce=Periodicity.coerce)


class MagDbMagazineView(MagDbModelView):
    list_template = "magdb/magazine/list_view.html"


class MagDbMagazineIssueView(MagDbModelView):
    @expose("/create_wizard", methods=["GET", "POST"])
    def create_wizard(self):
        create_form = self.get_create_form()

        prepared_values = {
            "magazine": Magazine.query.get(flask.request.args.get("magazine_id"))
        }

        last_issue = MagazineIssue.query.order_by(MagazineIssue.created_at.desc()).first()

        if last_issue.is_special_issue:
            prepared_values["note"] = "previous was special"
        else:
            prepared_values["issue_number"] = last_issue.issue_number + 1


            date = datetime.datetime(day=last_issue.published_day, month=last_issue.published_month, year=last_issue.published_year)
            value = None
            match last_issue.periodicity:
                case Periodicity.weekly:
                    value = rrule(WEEKLY, dtstart=date.date(), interval=1).after(date)
                case Periodicity.biweekly:
                    after_week = rrule(WEEKLY, dtstart=date.date(), interval=1).after(date)
                    value = rrule(WEEKLY, dtstart=after_week.date(), interval=1).after(after_week)
                case Periodicity.monthly:
                    value = rrule(MONTHLY, dtstart=date.date(), interval=1).after(date)
                case Periodicity.bimonthly:
                    after_month = rrule(MONTHLY, dtstart=date.date(), interval=1).after(date)
                    value = rrule(MONTHLY, dtstart=after_month.date(), interval=1).after(after_month)
                case Periodicity.annually:
                    value = rrule(YEARLY, dtstart=date.date(), interval=1).after(date)
                case Periodicity.quarterly:
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

        return self.render("magdb/magazine_issue/create_wizard.html", form=form)


def add_magdb_views(admin, session):
    admin.add_view(MagDbModelView(Issuer, session, category="MagDB"))
    admin.add_view(MagDbMagazineView(Magazine, session, category="MagDB"))
    admin.add_view(MagDbMagazineIssueView(MagazineIssue, session, category="MagDB", endpoint="magdb_magazine_issue"))
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