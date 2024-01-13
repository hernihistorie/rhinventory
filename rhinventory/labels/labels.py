from os import system
from io import BytesIO
import subprocess

from bs4 import BeautifulSoup as BS
import barcode
import barcode.codex
from barcode.writer import ImageWriter

import jinja2

from rhinventory.models.asset import Asset

def render_jinja_html(template_loc, file_name, **context):

    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_loc+'/')
    ).get_template(file_name).render(context)

def make_barcode(text):
    code128 = barcode.codex.Code128(text)
    fp = BytesIO()
    code128.write(fp)

    fp.seek(0)

    return fp

# TODO refactor me :(
def make_label(id, custom_code, name, subtitle="", medium="", small=False, logo_ha=False, big=False, logo_ucm=False) -> str:
    png_width = 2147 if big else 696
    
    fp = make_barcode(id)
    soup = BS(fp, 'lxml')
    rects = soup.find(id="barcode_group")

    if logo_ha:
        logo_kwargs = {
            'logo_href': "../assets/ha_logo.png",
            'logo_text_href': "../assets/ha_logo.png"
        }
    elif logo_ucm:
        logo_kwargs = {
            'logo_href': "../assets/ucmfmk_logo.png",
            'logo_text_href': "../assets/ucmfmk_logo.png"
        }
    else:
        logo_kwargs = {
            'logo_href': "../assets/rh_logo_greyscale.png",
            'logo_text_href': "../assets/rh_logo_text.png"
        }

    label_svg = render_jinja_html('rhinventory/labels', 'assets/label.svg',
        name=name, custom_code=custom_code, id=id, 
        subtitle=subtitle or '', medium=medium,
        barcode_rects=rects,
        small=small,
        **logo_kwargs)
    
    filename = f'rhinventory/labels/out/{id}'
    if small:
        filename += "-small"
    if big:
        filename += "-big"
    if logo_ha:
        filename += "-ha"
    if logo_ucm:
        filename += "-ucm"
    open(filename+'.svg', 'w').write(label_svg)

    inkscape_version = subprocess.check_output(['inkscape', '--version']).decode('utf-8').split('\n')[0].split(' ')[1]
    if inkscape_version.startswith('0.'):
        system(f'inkscape -z {filename}.svg -e {filename}.png -w {png_width}')
    else:
        system(f'inkscape -p {filename}.svg -o {filename}.png -w {png_width}')
    
    if big:
        system(f'mogrify -rotate 270 {filename}.png')

    return filename+'.png'

def make_asset_label(asset: Asset, small=False, logo_ha=False, big=False, logo_ucm=False):
    id = f"RH{asset.id:05}"
    if asset.CATEGORY_EXPOSE_NUMBER:
        if asset.custom_code:
            code = f"{asset.CATEGORY_PREFIX} {asset.custom_code}"
        else:
            code = f"{asset.CATEGORY_PREFIX} ???"
    else:
        code = asset.CATEGORY_PREFIX
    
    return make_label(id, code, asset.name,
        subtitle=", ".join([c.name for c in asset.companies]),
        medium="; ".join([m.name for m in asset.mediums]),
        small=small, logo_ha=logo_ha, big=big, logo_ucm=logo_ucm)
    