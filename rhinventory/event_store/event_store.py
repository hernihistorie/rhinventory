from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from rhinventory.extensions import db

from rhinventory.models.events import EventPushKey

event_store_bp = Blueprint("event_store", __name__, url_prefix="/event_store")

@event_store_bp.route("/authorize", methods=["GET", "POST"])
def authorize():
    if not current_user.is_authenticated:
        flash("You must be logged in to authorize event pushes.", "danger")
        return redirect(url_for("login", next=request.url))

    application_name = request.args['application_name']
    namespace = request.args['namespace']

    match request.method:
        case "GET":
            key = request.args['key']
            if len(key) < 16:
                flash("Invalid application key.", "danger")
                return redirect(url_for("index"))
            
            # has this key already been authorized?
            existing_key = db.session.query(EventPushKey).filter_by(
                namespace=namespace,
                key=key
            ).first()
            if existing_key is not None:
                flash("This application has already been authorized.", "success")
                return redirect(url_for("index"))

            return render_template(
                "event_store/authorize.html",
                admin_base_template='admin/base.html',
                application_name=application_name,
                namespace=namespace,
                key=key
            )
        case "POST":
            action = request.form.get("action")
            if action == "deny":
                flash("You have denied the event push authorization.", "warning")
                return redirect(url_for("index"))
            elif action != "authorize":
                raise ValueError("Invalid action")
            
            key = request.form.get("key")
            if not key:
                raise ValueError("Missing application key")
            
            # Authorize the event push key

            event_push_key = EventPushKey()
            event_push_key.application_name = application_name
            event_push_key.namespace = namespace
            event_push_key.key = key
            event_push_key.authorized_at = datetime.now()
            event_push_key.authorized_by_user_id = current_user.id
            db.session.add(event_push_key)
            db.session.commit()

            return render_template(
                "event_store/success.html",
                admin_base_template='admin/base.html'
            )
        case _:
            raise ValueError("Invalid method")
