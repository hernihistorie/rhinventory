#!/usr/bin/python
import asyncio
from io import BytesIO
import sys
import urllib.parse

LABEL_URL = "https://inventory.herniarchiv.cz/label/asset/"
KEY = "Zu2eebo9oNgeequee6ie"

print("hhprint v2.0")

try:
    from brother_ql.conversion import convert
    from brother_ql.backends.helpers import send
    from brother_ql.raster import BrotherQLRaster
except ModuleNotFoundError:
    print("Please install brother_ql:")
    print("pip install brother_ql")
    exit(1)

try:
    import aiohttp
except ModuleNotFoundError:
    print("Please install aiohttp:")
    print("pip install aiohttp[speedups]")
    exit(1)

arg = sys.argv[1]

url = urllib.parse.urlparse(arg)

path = url.path
qs = urllib.parse.parse_qs(url.query)

async def print_labels(qs: dict[str, list[str]]):
    codes = qs['codes'][0].split(";")
    printer = qs.get('printer', ['/dev/usb/lp0'])[0]
    backend = qs.get('backend', [''])[0]
    model = qs.get('model', ['QL-700'])[0]
    label = qs.get('label', ['62'])[0]

    async with aiohttp.ClientSession() as session:
        for code in codes:
            code = code.lower()
            for prefix in ['rh', 'hh']:
                code = code.removeprefix(prefix)
            label_url = LABEL_URL + code + "?key=" + KEY
            print(label_url)
            async with session.get(label_url) as response:
                image = BytesIO(await response.read())

                # https://github.com/pklaus/brother_ql/blob/master/brother_ql/cli.py#L134

                qlr = BrotherQLRaster(model)
                qlr.exception_on_warning = True
                instructions = convert(qlr=qlr, images=[image], label=label, cut=True)
                send(instructions=instructions, printer_identifier=printer, backend_identifier=backend, blocking=True)

if path == 'print':
    asyncio.run(print_labels(qs))
else:
    print("Unknown action", path)
