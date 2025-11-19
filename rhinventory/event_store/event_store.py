from datetime import datetime, timedelta
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
import msgspec

from hhfloppy.event.events import HHFLOPPY_EVENT_CLASS_UNION
from hhfloppy.event.datatypes import HHFLOPPY_EVENT_DATA_CLASS_UNION

from rhinventory.extensions import db
from rhinventory.models.events import DBEvent, EventPushKey

HHFLOPPY_DATATYPES = HHFLOPPY_EVENT_CLASS_UNION | HHFLOPPY_EVENT_DATA_CLASS_UNION
SUPPORTED_EVENT_VERSION = 3
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
            event_push_key.uses_remaining = 1
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

    # check event push key validity
    if event_push_key.authorized_at + timedelta(days=1) < datetime.now():
        return {"error": "Push key expired"}, 401

    if event_push_key.uses_remaining is not None:
        if event_push_key.uses_remaining <= 0:
            return {"error": "Push key has no remaining uses"}, 401
        event_push_key.uses_remaining -= 1

    # WIP
    events = request.json['serialized_events']
    for event_data in events:
        event = event_decoder.decode(msgspec.json.encode(event_data))
        assert isinstance(event, HHFLOPPY_EVENT_CLASS_UNION)
        if event.event_version > SUPPORTED_EVENT_VERSION:
            return {"error": f"Unsupported event version: {event.event_version}"}, 400

        db_event = DBEvent()
        # Note: We are trusting the event ID from the client here.
        db_event.id = event.event_id
        db_event.namespace = namespace
        db_event.class_name = event.__class__.__name__
        db_event.timestamp = event.event_timestamp
        db_event.ingested_at = datetime.now()
        db_event.event_push_key_id = event_push_key.id
        db_event.data = event_data
        db.session.add(instance=db_event)
    
    db.session.commit()

    return {"status": "success"}