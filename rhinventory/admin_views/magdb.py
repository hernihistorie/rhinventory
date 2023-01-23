import datetime
from dateutil.rrule import rrule, WEEKLY, MONTHLY, YEARLY

import flask
from flask import flash
from flask_admin import expose
from wtforms import Form, FileField, SelectField, SubmitField, BooleanField

from rhinventory.admin_views import CustomModelView
from rhinventory.admin_views.file import upload_file, DuplicateFile
from rhinventory.extensions import db
from rhinventory.models.magdb import Issuer, Magazine, Periodicity, MagazineIssue, Format, MagazineIssueVersion, MagazineIssueVersionPrice, MagazineIssueVersionFiles, MagDBFileType


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
    column_default_sort = ('id', True)
    column_exclude_list = ["created_at", "created_by", "updated_at", "updated_by"]


class MagDbMagazineView(MagDbModelView):
    list_template = "magdb/magazine/list_view.html"


class MagDbMagazineIssueView(MagDbModelView):
    list_template = "magdb/magazine_issue/list_view.html"

    @expose("/create_wizard", methods=["GET", "POST"])
    def create_wizard(self):
        create_form = self.get_create_form()

        magazine = Magazine.query.get(flask.request.args.get("magazine_id"))

        prepared_values = {
            "magazine": magazine
        }

        last_issue = MagazineIssue.query.order_by(MagazineIssue.created_at.desc()).filter(MagazineIssue.magazine_id==magazine.id).first()

        if last_issue is not None:
            if last_issue.is_special_issue:
                prepared_values["note"] = "previous was special"
            else:
                pass

            prepared_values["issuer"] = last_issue.issuer
            prepared_values["current_magazine_name"] = last_issue.current_magazine_name

            prepared_values["issue_number"] = (last_issue.issue_number or 0) + 1

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
                if last_issue.published_day is not None:
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

class UploadForm(Form):
    file = FileField(label="File to upload")
    file_type = SelectField(label="File type", choices=MagDBFileType.choices())
    submit = SubmitField(label="Upload file")


class MagDbMagazineIssueVersionView(MagDbModelView):
    list_template = "magdb/magazine_issue_version/list_view.html"

    form_extra_fields = {
        "copy_logos": BooleanField(),
    }

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
            prepared_values["register_number_mccr"] = last_issue_version.register_number_mccr
            prepared_values["issn_or_isbn"] = last_issue_version.issn_or_isbn
            prepared_values["barcode"] = last_issue_version.barcode
        # last_issue_version = None
        # if previous_to_last_issue is not None:
        #     last_issue_version = MagazineIssueVersion.query.order_by(
        #         MagazineIssueVersion.created_at.desc()
        #     ).filter(MagazineIssueVersion.magazine_issue_id == previous_to_last_issue.id).first()
        #
        # if last_issue_version is not None:
            prepared_values["format"] = last_issue_version.format
            prepared_values["name_suffix"] = last_issue_version.name_suffix
            prepared_values["form"] = last_issue_version.form.name

        form = create_form(flask.request.values, **prepared_values)
        if flask.request.method == "POST":
            new_version = self.create_model(form)

            if form.copy_logos.data:
                for file in last_issue_version.files:
                    if file.file_type == MagDBFileType.logo:
                        new_logo = MagazineIssueVersionFiles(
                            magazine_issue_version_id=new_version.id,
                            file_id=file.file_id,
                            file_type=MagDBFileType.logo,
                        )
                        db.session.add(new_logo)
                        db.session.commit()

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

    @expose("/manage_files", methods=["GET", "POST"])
    def manage_files(self):
        magazine_version_id = flask.request.args.get("magazine_version_id")
        context = {}
        version = MagazineIssueVersion.query.get(magazine_version_id)

        context["magazine_version"] = version
        context["files"] = MagazineIssueVersionFiles.query.filter(MagazineIssueVersionFiles.magazine_issue_version_id == magazine_version_id)

        context["MagDBFileType"] = MagDBFileType
        context["version_str"] = str(version)
        form = UploadForm(data=flask.request.values or {})
        context["upload_form"] = form

        if flask.request.method == "POST":
            file = flask.request.files.get("file")
            try:
                file_entry = upload_file(file)
            except DuplicateFile as e:
                flash("Uploaded file is a duplicate -> logo not added.", "error")
                return self.render("magdb/magazine_issue_version/manage_files.html", **context)

            db.session.add(file_entry)
            db.session.commit()

            magdb_file_entry = MagazineIssueVersionFiles(
                magazine_issue_version_id=magazine_version_id,
                file_id=file_entry.id,
                file_type=MagDBFileType.coerce(form.file_type.data)
            )

            db.session.add(magdb_file_entry)
            db.session.commit()

        return self.render("magdb/magazine_issue_version/manage_files.html", **context)


class MagDbMagazineIssueVersionPriceView(MagDbModelView):
    @expose("/create_wizard", methods=["GET", "POST"])
    def create_wizard(self):
        create_form = self.get_create_form()

        magazine_issue_version_id = flask.request.args.get("magazine_issue_version_id")

        last_issue_versions = MagazineIssueVersion.query.order_by(MagazineIssueVersion.created_at.desc()).all()

        last_issue_version = None
        if len(last_issue_versions) >= 2:
            last_issue_version = last_issue_versions[1]

        already_assigned_prices = MagazineIssueVersionPrice.query.filter(MagazineIssueVersionPrice.issue_version_id == magazine_issue_version_id).all()

        suggested_prices = MagazineIssueVersionPrice.query.filter(MagazineIssueVersionPrice.issue_version_id == last_issue_version.id).all() if last_issue_version is not None else []

        prepared_values = {
            "issue_version": MagazineIssueVersion.query.get(magazine_issue_version_id)
        }

        form = create_form(flask.request.values, **prepared_values)
        if flask.request.method == "POST":
            if flask.request.values.get("submit") == "Copy":
                for suggested_price in suggested_prices:
                    new_price = MagazineIssueVersionPrice(
                        issue_version_id=magazine_issue_version_id,
                        value=suggested_price.value,
                        currency=suggested_price.currency,
                    )
                    db.session.add(new_price)
                db.session.commit()
            else:
                self.create_model(form)
            return flask.redirect(self.get_url("magdb_magazine_issue_version.index_view"))

        return self.render(
            "magdb/magazine_issue_version_price/create_wizard.html",
            form=form,
            buttons=[
                ("Add and return to issue version ", "submit"),
            ],
            previous_issue_version=last_issue_version,
            assigned_prices=already_assigned_prices,
            suggested_prices=suggested_prices,
        )


class MagazineIssueFileView(MagDbModelView):
    pass



def add_magdb_views(admin, session):
    admin.add_view(MagDbModelView(Issuer, session, category="MagDB"))
    admin.add_view(MagDbMagazineView(Magazine, session, category="MagDB", endpoint="magdb_magazine"))
    admin.add_view(MagDbMagazineIssueView(MagazineIssue, session, category="MagDB", endpoint="magdb_magazine_issue"))
    admin.add_view(MagDbModelView(Format, session, category="MagDB"))
    admin.add_view(MagDbMagazineIssueVersionView(MagazineIssueVersion, session, category="MagDB", endpoint="magdb_magazine_issue_version"))
    admin.add_view(MagDbMagazineIssueVersionPriceView(MagazineIssueVersionPrice, session, category="MagDB", endpoint="magdb_magazine_issue_version_price"))
    admin.add_view(MagazineIssueFileView(MagazineIssueVersionFiles, session, category="MagDB", endpoint="magdb_file"))

