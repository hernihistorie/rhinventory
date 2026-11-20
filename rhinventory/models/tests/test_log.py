import datetime
import json

from rhinventory.db import User
from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.asset_attributes import Packaging, Platform
from rhinventory.models.log import REDACTED, LogItem, log, redact_logged_secrets


def take_logs(db_session) -> list[tuple[str, int, str, dict]]:
    """The logs written since the last call, as (table, object id, event, data)."""
    logs = [
        (item.table, item.object_id, item.event.name, json.loads(item.object_json))
        for item in db_session.query(LogItem).order_by(LogItem.id)
    ]
    db_session.query(LogItem).delete()
    db_session.commit()
    return logs


def make_asset(db_session, **kwargs) -> Asset:
    asset = Asset(organization_id=1, category=AssetCategory.game, name="Logged", **kwargs)
    db_session.add(asset)
    db_session.commit()
    return asset


def test_create_logs_many_to_many_ids(db_session):
    nes = Platform.from_name("NES")
    asset = make_asset(db_session, platforms=[nes])

    created = {(table, data["id"]): data for table, _, event, data in take_logs(db_session) if event == "Create"}
    assert created[("Asset", asset.id)]["platforms"] == [nes.id]
    assert created[("Asset", asset.id)]["tags"] == []
    # Only logged on the side declaring the backref
    assert "assets" not in created[("Platform", nes.id)]


def test_update_logs_added_and_removed(db_session):
    nes, snes = Platform.from_name("NES"), Platform.from_name("SNES")
    db_session.add_all([nes, snes])
    asset = make_asset(db_session)
    take_logs(db_session)

    asset.platforms.append(nes)
    db_session.commit()
    assert take_logs(db_session) == [
        ("Asset", asset.id, "Update", {"platforms": {"added": [nes.id], "removed": []}}),
    ]

    asset.platforms = [snes]
    db_session.commit()
    assert take_logs(db_session) == [
        ("Asset", asset.id, "Update", {"platforms": {"added": [snes.id], "removed": [nes.id]}}),
    ]


def test_update_through_other_side_is_logged_on_asset(db_session):
    nes = Platform.from_name("NES")
    db_session.add(nes)
    asset = make_asset(db_session)
    take_logs(db_session)

    nes.assets.append(asset)
    db_session.commit()
    assert take_logs(db_session) == [
        ("Asset", asset.id, "Update", {"platforms": {"added": [nes.id], "removed": []}}),
    ]


def test_update_logs_each_collection_separately(db_session):
    nes = Platform.from_name("NES")
    box = Packaging(name="Box")
    db_session.add_all([nes, box])
    asset = make_asset(db_session, platforms=[nes])
    take_logs(db_session)

    asset.platforms.remove(nes)
    asset.packaging.append(box)
    asset.name = "Renamed"
    db_session.commit()
    # Loading collections autoflushes, so the changes may be split across logs
    changes = {}
    for table, object_id, event, data in take_logs(db_session):
        assert (table, object_id, event) == ("Asset", asset.id, "Update")
        changes.update(data)
    assert changes == {
        "name": "Renamed",
        "platforms": {"added": [], "removed": [nes.id]},
        "packaging": {"added": [box.id], "removed": []},
    }


def test_delete_logs_removed_links(db_session):
    nes = Platform.from_name("NES")
    asset = make_asset(db_session, platforms=[nes])
    nes_id = nes.id
    take_logs(db_session)

    db_session.delete(nes)
    db_session.commit()
    assert take_logs(db_session) == [
        ("Platform", nes_id, "Delete", {"id": nes_id, "slug": "nes", "name": "NES", "last_used": None, "assets": [asset.id]}),
    ]


def test_explicit_log_isnt_followed_by_empty_update(client, db_session):
    nes = Platform.from_name("NES")
    db_session.add(nes)
    asset = make_asset(db_session)
    take_logs(db_session)

    client.post("/asset/add_platform_bulk/", data={"asset_id": str(asset.id), "platform_id": str(nes.id)})

    logs = take_logs(db_session)
    asset_logs = [data for table, _, _, data in logs if table == "Asset"]
    # The selection action's own log with the full asset, and the change
    assert len(asset_logs) == 2
    assert {"platforms": {"added": [nes.id], "removed": []}} in asset_logs
    assert all(data for _, _, _, data in logs)


def test_secret_columns_are_redacted(db_session):
    take_logs(db_session)
    user = User(username="secretive", github_access_token="gho_created")
    db_session.add(user)
    db_session.commit()
    user.github_access_token = "gho_updated"
    db_session.commit()
    log("Update", user)
    db_session.commit()

    tokens = [data["github_access_token"] for table, _, _, data in take_logs(db_session) if table == "User"]
    assert tokens and all(token == REDACTED for token in tokens)


def test_redact_logged_secrets_rewrites_old_logs(db_session):
    take_logs(db_session)
    now = datetime.datetime.now()
    contents = [
        ("User", {"id": 5, "github_login": "someone", "github_access_token": "gho_old"}),
        ("User", {"id": 6, "github_access_token": None}),
        ("Asset", {"id": 7, "github_access_token": "not a secret of Asset"}),
        ("User", None),
    ]
    db_session.add_all([
        LogItem(table=table, object_id=1, event="Update", datetime=now,
                object_json=json.dumps(data) if data is not None else None)
        for table, data in contents
    ])
    db_session.commit()

    assert redact_logged_secrets(db_session) == 1
    db_session.commit()
    assert redact_logged_secrets(db_session) == 0

    logged = [item.object_json for item in db_session.query(LogItem).order_by(LogItem.id)]
    assert [json.loads(data) if data else None for data in logged] == [
        {"id": 5, "github_login": "someone", "github_access_token": REDACTED},
        {"id": 6, "github_access_token": None},
        {"id": 7, "github_access_token": "not a secret of Asset"},
        None,
    ]
