from os import system
from io import BytesIO

from bs4 import BeautifulSoup as BS
import barcode
from barcode.writer import ImageWriter

import jinja2

def render_jinja_html(template_loc, file_name, **context):

    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_loc+'/')
    ).get_template(file_name).render(context)

def make_barcode(text):
    Code128 = barcode.get_barcode_class('code128')
    code128 = Code128(text)
    fp = BytesIO()
    code128.write(fp)

    fp.seek(0)

    return fp

def make_label(id, custom_code, name):
    PNG_WIDTH = 696
    
    fp = make_barcode(id)
    soup = BS(fp, 'lxml')
    rects = soup.find(id="barcode_group")

    label_svg = render_jinja_html('rhinventory/labels', 'label.svg',
        name=name, custom_code=custom_code, id=id, 
        barcode_rects=rects,
        rh_logo_href="../rh_logo_greyscale.png")
    
    filename = f'rhinventory/labels/out/{id}'
    open(filename+'.svg', 'w').write(label_svg)

    system(f'inkscape -p {filename}.svg -o {filename}.png -w {PNG_WIDTH}')

    return filename+'.png'

