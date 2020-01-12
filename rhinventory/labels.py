from io import BytesIO

import barcode
from barcode.writer import ImageWriter

def make_barcode(text):
    Code128 = barcode.get_barcode_class('code128')
    code128 = Code128(text)
    fp = BytesIO()
    code128.write(fp)

    fp.seek(0)

    return fp

