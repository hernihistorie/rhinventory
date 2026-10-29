import pytest

from rhinventory.files.hh_code import find_hh_code_suggestion, parse_hh_code


@pytest.mark.parametrize("filename, asset_id", [
    ("hh1234.jpg", 1234),
    ("HH1234.jpg", 1234),
    ("hh1234_2.jpg", 1234),
    ("hh1234-front.jpg", 1234),
    ("hh1234 (2).jpg", 1234),
    ("hh01234.jpg", 1234),
    ("hh1234", 1234),
    ("hh12_hh13.jpg", 12),
    ("hh1234a.jpg", None),
    ("hh1234x2.jpg", None),
    ("hh 1234.jpg", None),
    ("hh-1234.jpg", None),
    ("hh0.jpg", None),
    ("rh1234.jpg", None),
    ("IMG_hh1234.jpg", None),
    ("IMG_1234.jpg", None),
])
def test_parse_hh_code(filename: str, asset_id: int):
    assert parse_hh_code(filename) == asset_id


@pytest.mark.parametrize("filename, asset_id", [
    ("hh1234.jpg", 1234),
    ("rh1234.jpg", 1234),
    ("RH01234.jpg", 1234),
    ("IMG_hh1234.jpg", 1234),
    ("scan-hh1234.pdf", 1234),
    ("hh 1234.jpg", 1234),
    ("hh-1234.jpg", 1234),
    ("hh1234a.jpg", 1234),
    ("hh1234x2.jpg", 1234),
    ("bhh1234.jpg", None),
    ("photo.jpg", None),
    ("IMG_1234.jpg", None),
])
def test_find_hh_code_suggestion(filename: str, asset_id: int):
    assert find_hh_code_suggestion(filename) == asset_id
