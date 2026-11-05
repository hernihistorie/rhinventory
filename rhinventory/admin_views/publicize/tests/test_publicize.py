import re
from dataclasses import dataclass
from datetime import datetime

import pytest

from rhinventory.db import Asset, File, User
from rhinventory.extensions import db
from rhinventory.models.asset import AssetCategory
from rhinventory.models.asset_attributes import AssetTag
from rhinventory.models.enums import Privacy
from rhinventory.models.file import FileCategory

URL = "/asset/publicize/"


@dataclass
class Fixture:
    asset_id: int
    photo_id: int
    dump_id: int


@pytest.fixture()
def item(app) -> Fixture:
    return make_asset(app)


def make_asset(app, name="Secret Asset") -> Fixture:
    with app.app_context():
        asset = Asset(organization_id=1, category=AssetCategory.game, name=name)
        db.session.add(asset)
        db.session.flush()
        photo = File(asset_id=asset.id, filepath="photo.jpg", storage="local", category=FileCategory.photo)
        dump = File(asset_id=asset.id, filepath="disk.img", storage="local", category=FileCategory.dump, size=1024)
        db.session.add_all([photo, dump])
        db.session.commit()
        return Fixture(asset.id, photo.id, dump.id)


def set_file(app, file_id, **attributes):
    with app.app_context():
        file = db.session.get(File, file_id)
        for name, value in attributes.items():
            setattr(file, name, value)
        db.session.commit()


def tag_asset(app, asset_id, tag_name):
    with app.app_context():
        asset = db.session.get(Asset, asset_id)
        asset.tags.append(AssetTag(name=tag_name))
        db.session.commit()


def asset_privacy(app, asset_id) -> Privacy:
    with app.app_context():
        return db.session.get(Asset, asset_id).privacy


def file_privacy(app, file_id) -> Privacy:
    with app.app_context():
        return db.session.get(File, file_id).privacy


def skip_url(response) -> str:
    return re.search(rb'href="([^"]+)">Skip</a>', response.data)[1].decode().replace("&amp;", "&")


def get_csrf_token(client) -> str:
    match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', client.get(URL).data)
    assert match
    return match[1].decode()


def submit(client, url=URL, button="save", **decisions):
    data = {key.replace("_", "-"): value for key, value in decisions.items()}
    return client.post(url, data=data | {button: "x", "csrf_token": get_csrf_token(client)})


def test_anonymous_cant_see_queue(anonymous_client, item):
    response = anonymous_client.get(URL)
    assert response.status_code == 302
    assert b"Secret Asset" not in response.data


def test_anonymous_cant_save(app, anonymous_client, item):
    response = anonymous_client.post(URL, data={f"asset-{item.asset_id}": "public", "save": "x"})
    assert response.status_code == 302
    assert asset_privacy(app, item.asset_id) == Privacy.private_implicit


def test_read_only_user_cant_use_publicize(app, item):
    with app.app_context():
        user = User(username="reader", read_access=True, write_access=False)
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    app.login_manager.request_loader(lambda request: db.session.get(User, user_id))
    client = app.test_client()

    assert b"Secret Asset" not in client.get(URL).data
    client.post(URL, data={f"asset-{item.asset_id}": "public", "save": "x"})
    assert asset_privacy(app, item.asset_id) == Privacy.private_implicit


def test_save_requires_csrf_token(app, client, item):
    client.post(URL, data={f"asset-{item.asset_id}": "public", "save": "x"})
    assert asset_privacy(app, item.asset_id) == Privacy.private_implicit


def test_invalid_decision_saves_nothing(app, client, item):
    response = client.post(URL, data={
        f"asset-{item.asset_id}": "public",
        f"file-{item.photo_id}": "nonsense",
        "save": "x",
        "csrf_token": get_csrf_token(client),
    })
    assert response.status_code == 302
    assert asset_privacy(app, item.asset_id) == Privacy.private_implicit


@pytest.mark.parametrize("query", ["?offset=abc", "?count=abc", "?count=0", "?count=-1", "?offset=-1", "?sort=nonsense"])
def test_invalid_filter_redirects(client, query):
    response = client.get(URL + query)
    assert response.status_code == 302
    assert response.location == URL


def test_queue_shows_all_files_except_deleted(app, client, item):
    with app.app_context():
        db.session.add(File(asset_id=item.asset_id, filepath="gone.img", storage="local",
                            category=FileCategory.dump, is_deleted=True))
        db.session.commit()

    response = client.get(URL)

    assert f'name="file-{item.photo_id}-public"'.encode() in response.data
    assert f'name="file-{item.dump_id}-public"'.encode() in response.data
    assert b"disk.img" in response.data
    assert b"1.0 kB" in response.data
    assert b"gone.img" not in response.data


def set_asset(app, asset_id, privacy):
    with app.app_context():
        db.session.get(Asset, asset_id).privacy = privacy
        db.session.commit()


@pytest.mark.parametrize("privacy", [Privacy.public, Privacy.private])
def test_judged_asset_resurfaces_for_unjudged_files(app, client, item, privacy):
    set_asset(app, item.asset_id, privacy)

    response = client.get(URL)

    assert b"Secret Asset" in response.data
    assert b"Total assets to judge:\n        1 / 1" in response.data


@pytest.mark.parametrize("privacy", [Privacy.public, Privacy.private])
def test_only_unjudged_assets_are_affected_by_set_all(app, client, item, privacy):
    unjudged = make_asset(app, name="Unjudged Asset")
    set_asset(app, item.asset_id, privacy)

    html = client.get(URL + "?sort=oldest").data.decode()

    assert html.count('class="asset-row asset-unjudged"') == 1
    assert html.index('class="asset-row asset-unjudged"') > html.index(f'name="asset-{item.asset_id}-public"')
    assert html.index('class="asset-row asset-unjudged"') < html.index(f'name="asset-{unjudged.asset_id}-public"')


def test_fully_judged_asset_stays_out_of_the_queue(app, client, item):
    set_asset(app, item.asset_id, Privacy.public)
    set_file(app, item.photo_id, privacy=Privacy.public)
    set_file(app, item.dump_id, privacy=Privacy.private)

    response = client.get(URL)

    assert b"Secret Asset" not in response.data
    assert b"Total assets to judge:\n        0 / 1" in response.data


def test_deleted_unjudged_file_doesnt_resurface_asset(app, client, item):
    """The page doesn't show deleted files, so the asset could never leave the queue."""
    set_asset(app, item.asset_id, Privacy.public)
    set_file(app, item.photo_id, privacy=Privacy.public)
    set_file(app, item.dump_id, is_deleted=True)

    assert b"Secret Asset" not in client.get(URL).data


@pytest.mark.parametrize("privacy", [Privacy.public, Privacy.private])
def test_resurfaced_asset_leaves_queue_after_save(app, client, item, privacy):
    set_asset(app, item.asset_id, privacy)

    submit(client, **{
        f"asset_{item.asset_id}": privacy.name,
        f"file_{item.photo_id}": "default",
        f"file_{item.dump_id}": "private",
    })

    assert asset_privacy(app, item.asset_id) == privacy
    assert file_privacy(app, item.photo_id) == privacy
    assert file_privacy(app, item.dump_id) == Privacy.private
    assert b"Secret Asset" not in client.get(URL).data


def test_tag_filter_applies_to_resurfaced_assets(app, client, item):
    tagged = make_asset(app, name="Tagged Asset")
    with app.app_context():
        asset = db.session.get(Asset, tagged.asset_id)
        asset.tags.append(AssetTag(name="foo"))
        asset.privacy = Privacy.public
        db.session.commit()

    response = client.get(URL + "?tag=foo")

    assert b"Tagged Asset" in response.data
    assert b"Secret Asset" not in response.data


def test_empty_queue_renders(client):
    response = client.get(URL)
    assert response.status_code == 200
    assert b"no assets to judge" in response.data


# blank asset/file decisions are "default"; the expected privacy is for the file
@pytest.mark.parametrize("button,asset_value,file_value,expected_asset,expected_file", [
    ("publicize_all", "public", "default", Privacy.public, Privacy.public),
    ("publicize_all", "default", "default", Privacy.public, Privacy.public),
    ("publicize_all", "private", "default", Privacy.private, Privacy.private),
    ("publicize_all", "public", "private", Privacy.public, Privacy.private),
    ("publicize_all", "private", "public", Privacy.private, Privacy.public),
    ("save", "public", "default", Privacy.public, Privacy.public),
    ("save", "private", "default", Privacy.private, Privacy.private),
    ("save", "default", "default", Privacy.private_implicit, Privacy.private_implicit),
    ("save", "default", "public", Privacy.private_implicit, Privacy.public),
])
def test_decisions(app, client, item, button, asset_value, file_value, expected_asset, expected_file):
    submit(client, button=button, **{
        f"asset_{item.asset_id}": asset_value,
        f"file_{item.photo_id}": file_value,
    })

    assert asset_privacy(app, item.asset_id) == expected_asset
    assert file_privacy(app, item.photo_id) == expected_file


def test_asset_decision_only_reaches_submitted_files(app, client, item):
    """A file uploaded while the page was open wasn't reviewed."""
    submit(client, button="publicize_all", **{
        f"asset_{item.asset_id}": "public",
        f"file_{item.photo_id}": "default",
    })

    assert file_privacy(app, item.photo_id) == Privacy.public
    assert file_privacy(app, item.dump_id) == Privacy.private_implicit


def test_deleted_files_are_left_alone(app, client, item):
    token = get_csrf_token(client)
    set_file(app, item.photo_id, is_deleted=True)

    client.post(URL, data={
        f"asset-{item.asset_id}": "public",
        f"file-{item.photo_id}": "default",
        "publicize_all": "x",
        "csrf_token": token,
    })

    assert file_privacy(app, item.photo_id) == Privacy.private_implicit


def test_blank_doesnt_override_earlier_decisions(app, client, item):
    """Someone else can judge an asset or file while the page is open."""
    token = get_csrf_token(client)
    with app.app_context():
        db.session.get(Asset, item.asset_id).privacy = Privacy.private
        db.session.commit()
    set_file(app, item.photo_id, privacy=Privacy.private)
    set_file(app, item.dump_id, privacy=Privacy.unlinked)

    client.post(URL, data={
        f"asset-{item.asset_id}": "default",
        f"file-{item.photo_id}": "default",
        f"file-{item.dump_id}": "default",
        "publicize_all": "x",
        "csrf_token": token,
    })

    assert asset_privacy(app, item.asset_id) == Privacy.private
    assert file_privacy(app, item.photo_id) == Privacy.private
    assert file_privacy(app, item.dump_id) == Privacy.unlinked


def test_unknown_ids_are_ignored(app, client, item):
    response = submit(client, **{"asset_999999": "public", "file_999999": "public"})
    assert response.status_code == 302


def test_made_public_at_is_set(app, client, item):
    submit(client, **{f"asset_{item.asset_id}": "public"})
    with app.app_context():
        assert db.session.get(Asset, item.asset_id).made_public_at is not None


def test_only_real_changes_are_counted(app, client, item):
    set_file(app, item.photo_id, privacy=Privacy.public)

    submit(client, **{f"asset_{item.asset_id}": "public", f"file_{item.photo_id}": "public"})

    assert b"Saved 1 assets and 0 files." in client.get(URL).data


def test_save_keeps_filters(client, item):
    query = "?offset=5&count=10&tag=foo&sort=name"
    response = submit(client, url=URL + query)
    assert response.location == URL + query


def test_skip_links_to_the_next_batch_and_keeps_filters(app, client):
    first = make_asset(app, name="Earlier Asset")
    second = make_asset(app, name="Later Asset")
    with app.app_context():
        assets = [db.session.get(Asset, first.asset_id), db.session.get(Asset, second.asset_id)]
        tag = AssetTag(name="foo")
        for asset in assets:
            asset.tags.append(tag)
        db.session.commit()

    response = client.get(URL + "?tag=foo&count=1&sort=oldest")
    assert b"Earlier Asset" in response.data
    assert b"Later Asset" not in response.data

    response = client.get(skip_url(response))
    assert b"Earlier Asset" not in response.data
    assert b"Later Asset" in response.data


def test_saving_a_batch_brings_in_the_next_one(app, client):
    first = make_asset(app, name="Earlier Asset")
    make_asset(app, name="Later Asset")

    submit(client, url=URL + "?count=1&sort=oldest", **{
        f"asset_{first.asset_id}": "public",
        f"file_{first.photo_id}": "default",
        f"file_{first.dump_id}": "default",
    })

    assert b"Later Asset" in client.get(URL + "?count=1&sort=oldest").data


def test_no_skip_link_at_the_end_of_the_queue(client, item):
    response = client.get(URL + "?offset=1")
    assert b">Skip<" not in response.data
    assert b"Back to the first batch" in response.data


def asset_order(client, query="") -> list[str]:
    html = client.get(URL + query).data.decode()
    return re.findall(r'font-size: 24px;">\s*<a href="[^"]*">([^<]+)</a>', html)


def test_newest_assets_are_shown_first_by_default(app, client):
    make_asset(app, name="First")
    make_asset(app, name="Second")

    assert asset_order(client) == ["Second", "First"]


@pytest.mark.parametrize("sort,expected", [
    ("newest", ["banana", "Cherry", "apple"]),
    ("oldest", ["apple", "Cherry", "banana"]),
    ("name", ["apple", "banana", "Cherry"]),
    ("latest_files", ["Cherry", "apple", "banana"]),
])
def test_sorting(app, client, sort, expected):
    apple = make_asset(app, name="apple")
    cherry = make_asset(app, name="Cherry")
    banana = make_asset(app, name="banana")
    set_file(app, apple.photo_id, upload_date=datetime(2020, 1, 1))
    set_file(app, cherry.photo_id, upload_date=datetime(2024, 1, 1))
    # The newest file was deleted, so it shouldn't count
    set_file(app, banana.photo_id, upload_date=datetime(2026, 1, 1), is_deleted=True)

    assert asset_order(client, f"?sort={sort}") == expected


def test_sort_links_keep_filters_but_restart_the_queue(app, client, item):
    tag_asset(app, item.asset_id, "foo")

    html = client.get(URL + "?tag=foo&count=10&offset=5").data.decode().replace("&amp;", "&")

    assert 'href="/asset/publicize/?count=10&tag=foo&sort=name"' in html


def test_clearing_the_tag_keeps_sort(app, client, item):
    tag_asset(app, item.asset_id, "foo")

    html = client.get(URL + "?tag=foo&sort=name").data.decode()

    assert f'<a href="{URL}?sort=name">Clear filter</a>' in html


def test_tag_form_keeps_sort_and_count(client):
    html = client.get(URL + "?sort=name&count=10").data.decode()

    assert '<input type="hidden" name="sort" value="name">' in html
    assert '<input type="hidden" name="count" value="10">' in html


def test_tag_filter_prefers_id_and_handles_ambiguous_names(app, client):
    with app.app_context():
        first = AssetTag(name="shared")
        db.session.add_all([first, AssetTag(name="shared")])
        db.session.flush()
        numeric_name = AssetTag(name=str(first.id))
        db.session.add(numeric_name)
        db.session.commit()
        first_id = first.id

    assert f"(id {first_id})".encode() in client.get(URL + "?tag=shared").data
    assert f"(id {first_id})".encode() in client.get(URL + f"?tag={first_id}").data


def test_unknown_tag_redirects(client):
    response = client.get(URL + "?tag=nonexistent")
    assert response.status_code == 302
    assert response.location == URL
