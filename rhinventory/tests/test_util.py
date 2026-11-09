import pytest

from rhinventory.util import safe_next_path


@pytest.mark.parametrize("url,expected", [
    ("/asset/12-foo", "/asset/12-foo"),
    ("/asset/?page=2&sort=1", "/asset/?page=2&sort=1"),
    ("http://localhost/event_store/authorize?key=x", "/event_store/authorize?key=x"),
    ("https://localhost/asset/", "/asset/"),
    (None, None),
    ("", None),
    ("asset/", None),
    ("//evil.example/", None),
    ("///evil.example/", "/evil.example/"),
    ("/\\evil.example/", None),
    ("/\t/evil.example/", None),
    ("https://evil.example/", None),
    ("https://localhost@evil.example/", None),
    ("http:/evil.example/", "/evil.example/"),
    ("javascript:alert(1)", None),
])
def test_safe_next_path(url, expected):
    assert safe_next_path(url, "localhost") == expected
