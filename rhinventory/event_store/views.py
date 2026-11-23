from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
import msgspec

from rhinventory.event_store.event_store import ConflictingEvent, EventNamespaceName, UnsupportedEventVersion, event_store
from rhinventory.extensions import db
from rhinventory.models.events import DBEvent, EventSession, PushKey

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
                flash("Invalid push key.", "danger")
                return redirect(url_for("index"))

            # has this key already been authorized?
            existing_key = db.session.query(PushKey).filter(
                PushKey.key==key
            ).join(EventSession).filter(
                EventSession.namespace==namespace
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

            push_key = PushKey()
            push_key.key = key
            push_key.authorized_at = datetime.now()
            push_key.authorized_by_user_id = current_user.id
            push_key.uses_remaining = 1
            db.session.add(push_key)

            event_session = EventSession()
            event_session.application_name = application_name
            event_session.namespace = namespace
            event_session.push_key = push_key
            event_session.user_id = current_user.id
            db.session.add(event_session)
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

    push_key = db.session.query(PushKey).filter(
        PushKey.key==key
    ).join(EventSession).filter(
        EventSession.namespace==namespace
    ).first()
    if push_key is None:
        return {"authorized": False}, 404
    else:
        return {"authorized": True}, 200


@event_store_bp.route("/ingest/", methods=["POST"])
def ingest_event():
    if not request.json:
        return {"error": "Invalid JSON"}, 400
    namespace = request.json['namespace']
    key = request.json['key']

    event_session = db.session.query(EventSession).filter(
        EventSession.namespace==namespace,
        EventSession.internal==False
    ).join(PushKey).filter(
        PushKey.key==key
    ).first()
    if event_session is None:
        return {"error": "Unauthorized"}, 401

    # Lock the key so concurrent pushes with it can't both spend its last use
    push_key = db.session.get(PushKey, event_session.push_key_id, with_for_update=True, populate_existing=True)
    assert push_key is not None
    # check event push key validity
    if push_key.authorized_at + timedelta(days=1) < datetime.now():
        db.session.rollback()
        return {"error": "Push key expired"}, 401

    namespace = EventNamespaceName(namespace)

    # The push is stored all or nothing, so a client can retry it after any failure
    try:
        events = [
            event_store.decode(event_data=msgspec.json.encode(event_data), namespace=namespace)
            for event_data in request.json['serialized_events']
        ]
        ingested = [event_store.ingest(event=event, event_session=event_session) for event in events]
    except (ValueError, UnsupportedEventVersion) as e:
        db.session.rollback()
        return {"error": str(e)}, 400
    except ConflictingEvent as e:
        db.session.rollback()
        return {"error": str(e), "event_id": str(e.event_id)}, 409

    num_ingested = sum(ingested)
    # Replaying a push that's already stored, such as a retry after its response
    # was lost, doesn't use up the key
    if num_ingested and push_key.uses_remaining is not None:
        if push_key.uses_remaining <= 0:
            db.session.rollback()
            return {"error": "Push key has no remaining uses"}, 401
        push_key.uses_remaining -= 1

    db.session.commit()

    return {"status": "success", "ingested": num_ingested, "duplicates": len(events) - num_ingested}
