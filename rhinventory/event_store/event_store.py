from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user
event_store_bp = Blueprint("event_store", __name__, url_prefix="/event_store")

@event_store_bp.route("/authorize", methods=["GET", "POST"])
def authorize():
    if not current_user.is_authenticated:
        flash("You must be logged in to authorize event pushes.", "danger")
        return redirect(url_for("login", next=request.url))
    
    match request.method:
        case "GET":
            application_name = request.args['application_name']
            key = request.args['key']
            if len(key) < 16:
                flash("Invalid application key.", "danger")
                return redirect(url_for("index"))

            return render_template(
                "event_store/authorize.html",
                admin_base_template='admin/base.html',
                application_name=application_name,
                key=key
            )
        case "POST":
            action = request.form.get("action")
            if action == "deny":
                flash("You have denied the event push authorization.", "warning")
                return redirect(url_for("index"))
            elif action != "authorize":
                raise ValueError("Invalid action")

            return render_template(
                "event_store/success.html",
                admin_base_template='admin/base.html'
            )
        case _:
            raise ValueError("Invalid method")
