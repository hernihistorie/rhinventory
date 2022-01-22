from os import system
from io import BytesIO
import subprocess

from bs4 import BeautifulSoup as BS
import barcode
import barcode.codex
from barcode.writer import ImageWriter

import jinja2

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

def make_label(id, custom_code, name, subtitle="", medium="", small=False, logo_ha=False):
    PNG_WIDTH = 696
    
    fp = make_barcode(id)
    soup = BS(fp, 'lxml')
    rects = soup.find(id="barcode_group")

    if logo_ha:
        logo_kwargs = {
            'logo_href': "../ha_logo.png",
            'logo_text_href': "../ha_logo.png"
        }
    else:
        logo_kwargs = {
            'logo_href': "../rh_logo_greyscale.png",
            'logo_text_href': "../rh_logo_text.png"
        }

    label_svg = render_jinja_html('rhinventory/labels', 'label.svg',
        name=name, custom_code=custom_code, id=id, 
        subtitle=subtitle or '', medium=medium,
        barcode_rects=rects,
        small=small,
        **logo_kwargs)
    
    filename = f'rhinventory/labels/out/{id}'
    if small:
        filename += "-small"
    if logo_ha:
        filename += "-ha"
    open(filename+'.svg', 'w').write(label_svg)

    inkscape_version = subprocess.check_output(['inkscape', '--version']).decode('utf-8').split('\n')[0].split(' ')[1]
    if inkscape_version.startswith('0.'):
        system(f'inkscape -z {filename}.svg -e {filename}.png -w {PNG_WIDTH}')
    else:
        system(f'inkscape -p {filename}.svg -o {filename}.png -w {PNG_WIDTH}')

    return filename+'.png'

def make_asset_label(asset, small=False, logo_ha=False):
    id = f"RH{asset.id:05}"
    if asset.custom_code and asset.category.expose_number:
        code = f"{asset.category.prefix} {asset.custom_code}"
    else:
        code = f"{asset.category.prefix}"
    
    return make_label(id, code, asset.name,
        subtitle=asset.manufacturer, medium=asset.medium.name if asset.medium else '',
        small=small, logo_ha=logo_ha)
    