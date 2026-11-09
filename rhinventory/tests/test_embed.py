import re

import pytest
from flask.testing import FlaskClient


EMBED_HEADERS = {
    'X-Forwarded-Prefix': '/inventory/_frame',
    'X-Haweb-Embed': '1',
    'X-Haweb-Theme': 'dark',
}


# Root-relative URL in an attribute that doesn't start with the embed prefix
UNPREFIXED_URL = re.compile(r'(?:href|src|action)="/(?!/|inventory/_frame/)[^"]*"')


@pytest.mark.parametrize("url", ["/", "/asset/", "/file/", "/transaction/"])
def test_embedded(client: FlaskClient, url: str):
    response = client.get(url, headers=EMBED_HEADERS)
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert 'class="ha-header"' not in html
    assert 'src="/inventory/_frame/static/embed.js" data-theme="dark"' in html
    assert UNPREFIXED_URL.findall(html) == []


def test_embedded_does_not_leak(client: FlaskClient):
    client.get("/asset/", headers=EMBED_HEADERS)

    response = client.get("/asset/")
    html = response.data.decode('utf-8')
    assert '/inventory/_frame' not in html
    assert 'embed.js' not in html
    assert 'class="ha-header"' in html
    assert 'X-Haweb-Embed' in response.headers['Vary']
