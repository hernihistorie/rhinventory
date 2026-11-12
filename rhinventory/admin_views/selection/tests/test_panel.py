from flask.testing import FlaskClient

ACTIONS = {
    'labels': 'id="selected-show-sheet"',
    'files': 'id="selected-download-files"',
    'transactions': 'id="selected-add-to-transaction-form"',
    'parent': 'id="selected-set-parent-bulk-form"',
    'location': 'id="selected-set-location-bulk-form"',
    'tag': 'id="selected-add-tag-bulk-form"',
}


def test_asset_list_renders_every_selection_action(client: FlaskClient):
    response = client.get("/asset/")
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    assert html.count('data-toggle="tab"') >= len(ACTIONS)
    for name, pane_marker in ACTIONS.items():
        assert f'href="#selected-tab-{name}"' in html
        assert f'id="selected-tab-{name}"' in html
        assert pane_marker in html
    assert 'class="tab-pane active" id="selected-tab-labels"' in html

    # Action scripts come after the shared script they rely on
    assert html.index('function submitWithSelection') < html.index("submitWithSelection(document.getElementById('selected-add-tag-bulk-form')")


def test_selection_forms_return_to_current_list_page(client: FlaskClient):
    response = client.get("/asset/?page=4&sort=1")
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # One for each of the parent, location and tag forms
    assert html.count('<input type="hidden" name="url" value="/asset/?page=4&amp;sort=1">') == 3


def test_selection_action_redirects_back_to_list_page(client: FlaskClient, make_assets):
    (asset_id,) = make_assets(1)

    response = client.post("/asset/add_tag_bulk/", data={
        "asset_id": str(asset_id),
        "new_tag_name": "Paged",
        "url": "/asset/?page=4&sort=1",
    })
    assert response.status_code == 302
    assert response.location == "/asset/?page=4&sort=1"


def test_selection_action_ignores_offsite_return_url(client: FlaskClient, make_assets):
    (asset_id,) = make_assets(1)

    response = client.post("/asset/add_tag_bulk/", data={
        "asset_id": str(asset_id),
        "new_tag_name": "Offsite",
        "url": "https://example.com/asset/",
    })
    assert response.status_code == 302
    assert response.location == "/asset/"
