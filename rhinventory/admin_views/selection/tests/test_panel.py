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
