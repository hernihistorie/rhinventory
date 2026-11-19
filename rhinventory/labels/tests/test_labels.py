import io

import pytest
from PIL import Image

from rhinventory.db import Asset
from rhinventory.labels.labels import (
    LabelContent, LabelLogo, LabelSize, asset_label_content, label_html, label_variant, location_label_content,
    parse_label_variant, render_label,
)
from rhinventory.models.asset import AssetCategory
from rhinventory.models.asset_attributes import Company, Medium
from rhinventory.models.file import pyzbar

CONTENT = LabelContent("HH03175", "GM 123", "Příliš žluťoučký kůň", "Nintendo", "Cartridge")


@pytest.mark.parametrize("size, expected_size", [
    (LabelSize.STANDARD, (696, 314)),
    (LabelSize.SMALL, (696, 112)),
    # Rotated
    (LabelSize.BIG, (970, 2147)),
])
@pytest.mark.parametrize("logo", list(LabelLogo))
def test_render_label(label_renderer, zbar, size, expected_size, logo):
    image = Image.open(io.BytesIO(render_label(CONTENT, size, logo)))

    assert image.size == expected_size
    assert [code.data for code in pyzbar.decode(image)] == [b"HH03175"]


def test_label_html_escapes_content():
    content = LabelContent("HH00001", '<i>"GM"</i>', "<script>alert(1)</script>", "<b>Nin</b>", "<u>CD</u>")

    html = label_html(content, LabelSize.STANDARD, LabelLogo.RH)

    for tag in ["<i>", "<script>", "<b>", "<u>"]:
        assert tag not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


@pytest.mark.parametrize("size, logo, shown, hidden", [
    (LabelSize.STANDARD, LabelLogo.RH, ["GM 123", "Cartridge", "Příliš žluťoučký kůň", "Nintendo"], []),
    (LabelSize.SMALL, LabelLogo.RH, ["GM 123", "Cartridge"], ["Příliš žluťoučký kůň", "Nintendo"]),
    # Small HA labels have no room for a logo, so show the name instead
    (LabelSize.SMALL, LabelLogo.HA, ["Příliš žluťoučký kůň"], ["GM 123", "Cartridge", "Nintendo"]),
])
def test_label_html_content(size, logo, shown, hidden):
    html = label_html(CONTENT, size, logo)

    assert "HH03175" in html
    for text in shown:
        assert text in html
    for text in hidden:
        assert text not in html


@pytest.mark.parametrize("variant, expected", [
    ("", (LabelSize.STANDARD, LabelLogo.RH)),
    ("small", (LabelSize.SMALL, LabelLogo.RH)),
    ("ha", (LabelSize.STANDARD, LabelLogo.HA)),
    ("small-ha", (LabelSize.SMALL, LabelLogo.HA)),
    ("ucm", (LabelSize.STANDARD, LabelLogo.UCM)),
    ("small-ucm", (LabelSize.SMALL, LabelLogo.UCM)),
    ("big", (LabelSize.BIG, LabelLogo.RH)),
    ("big-ha", (LabelSize.BIG, LabelLogo.HA)),
])
def test_parse_label_variant(variant, expected):
    assert parse_label_variant(variant) == expected


@pytest.mark.parametrize("size", list(LabelSize))
@pytest.mark.parametrize("logo", list(LabelLogo))
def test_label_variant(size, logo):
    assert parse_label_variant(label_variant(size, logo)) == (size, logo)


@pytest.mark.parametrize("variant", ["rh", "tiny", "ha-small", "small-", "-small", "small-small", "small-ha-ha", "SMALL"])
def test_parse_label_variant_unknown(variant):
    with pytest.raises(ValueError):
        parse_label_variant(variant)


def test_asset_label_content():
    asset = Asset(id=3175, category=AssetCategory.game, name="Super Mario Bros. 3",
                  companies=[Company(name="Nintendo"), Company(name="Hudson")],
                  mediums=[Medium(name="Cartridge"), Medium(name="Manual")])

    assert asset_label_content(asset) == LabelContent(
        "HH03175", "GM", "Super Mario Bros. 3", "Nintendo, Hudson", "Cartridge; Manual")


@pytest.mark.parametrize("custom_code, expected", [(12, "PC 12"), (None, "PC ???")])
def test_asset_label_content_with_category_number(custom_code, expected):
    asset = Asset(id=7, category=AssetCategory.computer, name="Amiga 500", custom_code=custom_code)

    assert asset_label_content(asset) == LabelContent("HH00007", expected, "Amiga 500")


def test_location_label_content():
    assert location_label_content(12, "Regál A3") == LabelContent("RHL0012", "LOCATION", "Regál A3")
