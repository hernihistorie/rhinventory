from io import BytesIO
import base64
import dataclasses
import enum
import functools
import itertools
from pathlib import Path

import barcode.codex
import jinja2
from markupsafe import Markup
from PIL import Image

from rhinventory.labels.render import render_png
from rhinventory.models.asset import Asset

LABELS_DIR = Path(__file__).parent
ASSETS_DIR = LABELS_DIR / "assets"


@dataclasses.dataclass(frozen=True)
class LabelContent:
    code: str
    """Encoded in the barcode, e.g. HH03175"""
    custom_code: str = ""
    """What people call the thing, e.g. "GM 123\""""
    name: str = ""
    subtitle: str = ""
    medium: str = ""


@dataclasses.dataclass(frozen=True)
class _LabelFormat:
    template: str
    width_mm: float
    height_mm: float
    width_px: int
    rotate: bool = False


class LabelSize(enum.Enum):
    # Widths in pixels are the ones the label printers are set up for
    STANDARD = _LabelFormat("label.html", 62, 28, 696)
    SMALL = _LabelFormat("label_small.html", 62, 10, 696)
    # A standard label at a higher resolution, turned on its side
    BIG = _LabelFormat("label.html", 62, 28, 2147, rotate=True)


class LabelLogo(enum.Enum):
    RH = "rh"
    HA = "ha"
    UCM = "ucm"


# The logo for standard labels, and the one for small labels, if they have one
_LOGO_FILES: dict[LabelLogo, tuple[str, str | None]] = {
    LabelLogo.RH: ("rh_logo_greyscale.png", "rh_logo_text.png"),
    # Small HA labels show the name instead
    LabelLogo.HA: ("ha_logo.png", None),
    LabelLogo.UCM: ("ucmfmk_logo.png", "ucmfmk_logo.png"),
}

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(LABELS_DIR / "templates"),
    autoescape=True,
    undefined=jinja2.StrictUndefined,
)


def _data_uri(data: bytes, mimetype: str) -> str:
    return f"data:{mimetype};base64,{base64.b64encode(data).decode('ascii')}"


@functools.cache
def _font_data_uris() -> dict[str, str]:
    return {
        name: _data_uri((ASSETS_DIR / "fonts" / filename).read_bytes(), "font/ttf")
        for name, filename in [("sans", "DejaVuSans.ttf"), ("mono", "DejaVuSansMono.ttf")]
    }


@functools.cache
def _logo_data_uri(filename: str) -> str:
    """The logo cropped to what's visible, so the templates can size it by what you see."""
    image = Image.open(ASSETS_DIR / filename).convert("RGBA")
    on_white = Image.new("RGBA", image.size, "white")
    on_white.alpha_composite(image)
    # Some logos have a transparent border, some a white one
    visible = on_white.convert("L").point(lambda value: 255 if value < 250 else 0)
    image = image.crop(visible.getbbox())
    png = BytesIO()
    image.save(png, format="PNG")
    return _data_uri(png.getvalue(), "image/png")


def barcode_svg(text: str) -> Markup:
    """A Code128 barcode that stretches to fill the element, without the text under it."""
    modules = barcode.codex.Code128(text).build()[0]
    bars = []
    x = 0
    for is_bar, run in itertools.groupby(modules):
        width = len(list(run))
        if is_bar == "1":
            bars.append(f"M{x} 0h{width}v1h-{width}z")
        x += width
    return Markup(
        f'<svg class="barcode" viewBox="0 0 {len(modules)} 1" preserveAspectRatio="none" '
        f'shape-rendering="crispEdges"><path d="{"".join(bars)}"/></svg>'
    )


def label_html(content: LabelContent, size: LabelSize, logo: LabelLogo) -> str:
    """The label as a self-contained HTML page."""
    label_format = size.value
    logo_file = _LOGO_FILES[logo][1 if size == LabelSize.SMALL else 0]
    return _jinja_env.get_template(label_format.template).render(
        content=content,
        width_mm=label_format.width_mm,
        height_mm=label_format.height_mm,
        barcode=barcode_svg(content.code),
        logo=_logo_data_uri(logo_file) if logo_file else None,
        fonts=_font_data_uris(),
    )


def render_label(content: LabelContent, size: LabelSize, logo: LabelLogo) -> bytes:
    """The label as a PNG for the label printer."""
    label_format = size.value
    png = render_png(label_html(content, size, logo),
                     label_format.width_mm, label_format.height_mm, label_format.width_px)
    if label_format.rotate:
        image = Image.open(BytesIO(png)).transpose(Image.Transpose.ROTATE_90)
        out = BytesIO()
        image.save(out, format="PNG")
        png = out.getvalue()
    return png


def parse_label_variant(variant: str) -> tuple[LabelSize, LabelLogo]:
    """The size and logo from how hhprint asks for a label, e.g. "small-ha" ("" for a standard RH label).

    Raises ValueError for anything else.
    """
    parts = variant.split("-") if variant else []
    size = LabelSize.STANDARD
    if parts and parts[0] in ("small", "big"):
        size = LabelSize[parts.pop(0).upper()]
    logo = LabelLogo.RH
    if parts and parts[0] in ("ha", "ucm"):
        logo = LabelLogo(parts.pop(0))
    if parts:
        raise ValueError(f"Unknown label variant {variant!r}")
    return size, logo


def asset_label_content(asset: Asset) -> LabelContent:
    if asset.CATEGORY_EXPOSE_NUMBER:
        custom_code = f"{asset.CATEGORY_PREFIX} {asset.custom_code or '???'}"
    else:
        custom_code = asset.CATEGORY_PREFIX

    return LabelContent(
        code=f"HH{asset.id:05}",
        custom_code=custom_code,
        name=asset.name or "",
        subtitle=", ".join(company.name for company in asset.companies),
        medium="; ".join(medium.name for medium in asset.mediums),
    )


def location_label_content(location_id: int, name: str) -> LabelContent:
    return LabelContent(code=f"RHL{location_id:04}", custom_code="LOCATION", name=name)


def make_barcode(text: str) -> BytesIO:
    """A standalone Code128 barcode as an SVG file, with the text under it."""
    fp = BytesIO()
    barcode.codex.Code128(text).write(fp)
    fp.seek(0)
    return fp
