import base64
import http.server
import io
import threading

import pytest
from PIL import Image


def render(label_renderer, body: str, style: str = "", size=(62, 28, 696)) -> Image.Image:
    html = f"""<!doctype html>
        <style>html, body {{ margin: 0; background: white; }} {style}</style>
        {body}"""
    return Image.open(io.BytesIO(label_renderer(html, *size))).convert("L")


@pytest.mark.parametrize("size, expected", [
    # The sizes the Inkscape labels came out as, which the printers are set up for
    ((62, 28, 696), (696, 314)),
    ((62, 10, 696), (696, 112)),
    ((62, 28, 2147), (2147, 970)),
])
def test_render_size(label_renderer, size, expected):
    image = render(label_renderer, "", size=size)

    assert image.size == expected


@pytest.mark.parametrize("width_px", [696, 2147])
def test_render_scales_mm_to_label_width(label_renderer, width_px):
    image = render(label_renderer, '<div class="half"></div>',
                   ".half { position: absolute; left: 0; top: 0; width: 31mm; height: 14mm; background: black; }",
                   size=(62, 28, width_px))
    width, height = image.size

    # Chromium snaps boxes to CSS pixels, so allow a little either way
    margin = width_px // 200
    assert image.getpixel((width // 2 - margin, height // 2 - margin)) == 0
    assert image.getpixel((width // 2 + margin, height // 2 - margin)) == 255
    assert image.getpixel((width // 2 - margin, height // 2 + margin)) == 255


def test_render_shows_data_uri_images(label_renderer):
    png = io.BytesIO()
    Image.new("L", (4, 4), 0).save(png, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(png.getvalue()).decode()

    image = render(label_renderer, f'<img src="{data_uri}">', "img { width: 62mm; height: 28mm; display: block; }")

    # All but the edge, which is antialiased where 28mm falls between pixels
    black = image.histogram()[0]
    assert black > 0.98 * image.width * image.height


def test_render_doesnt_run_scripts(label_renderer):
    image = render(label_renderer, "<script>document.body.style.background = 'black'</script>")

    assert image.getextrema() == (255, 255)


@pytest.fixture()
def black_stylesheet_server():
    """Serves a stylesheet that turns the page black, and records requests for it."""
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            body = b"body { background: black !important; }"
            self.send_response(200)
            self.send_header("Content-Type", "text/css")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", requests
    server.shutdown()
    server.server_close()


def test_render_doesnt_load_anything(label_renderer, black_stylesheet_server):
    url, requests = black_stylesheet_server

    image = render(label_renderer, f"""
        <link rel="stylesheet" href="{url}/style.css">
        <img src="{url}/image.png">
        <iframe src="{url}/frame.html"></iframe>
    """)

    assert requests == []
    # Away from the broken image and the iframe's border
    assert image.getpixel((image.width - 1, image.height - 1)) == 255
