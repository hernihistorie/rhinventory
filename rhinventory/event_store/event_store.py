from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
import msgspec

from hhfloppy.event.events import HHFLOPPY_EVENT_CLASS_UNION
from hhfloppy.event.datatypes import HHFLOPPY_EVENT_DATA_CLASS_UNION

from rhinventory.extensions import db
from rhinventory.models.events import DBEvent, EventPushKey

HHFLOPPY_DATATYPES = HHFLOPPY_EVENT_CLASS_UNION | HHFLOPPY_EVENT_DATA_CLASS_UNION
SUPPORTED_EVENT_VERSION = 1
event_decoder: msgspec.json.Decoder[HHFLOPPY_DATATYPES] = msgspec.json.Decoder(HHFLOPPY_DATATYPES)

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


@event_store_bp.route("/check_key/", methods=["GET"])
def check_key():
    namespace = request.args['namespace']
    key = request.args['key']

    event_push_key = db.session.query(EventPushKey).filter_by(
        namespace=namespace,
        key=key
    ).first()
    if event_push_key is None:
        return {"authorized": False}, 404
    else:
        return {"authorized": True}, 200


@event_store_bp.route("/ingest/", methods=["POST"])
def ingest_event():
    if not request.json:
        return {"error": "Invalid JSON"}, 400
    namespace = request.json['namespace']
    key = request.json['key']

    event_push_key = db.session.query(EventPushKey).filter_by(
        namespace=namespace,
        key=key
    ).first()
    if event_push_key is None:
        return {"error": "Unauthorized"}, 401

    # WIP
    # events = request.json.get('events', [])
    # for event_data in events:
    #     event = DBEvent()
    #     event.namespace = namespace
    #     event.class_name = event_data['class_name']
    #     event.timestamp = datetime.fromisoformat(event_data['timestamp'])
    #     event.ingested_at = datetime.now()
    #     event.event_push_key_id = event_push_key.id
    #     event.data = event_data['data']
    #     db.session.add(event)
    
    db.session.commit()

    return {"status": "success"}, 201