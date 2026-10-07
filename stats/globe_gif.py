"""Render the interactive globe page into a spinning GIF for READMEs.

Uses headless Chromium (Playwright) to screenshot site/index.html at a series of
longitudes, then assembles the frames with Pillow. Static hosts like GitHub
READMEs cannot embed the live page, so this is the embeddable version.
"""
from __future__ import annotations

import http.server
import socketserver
import threading
from pathlib import Path

from .config import CHARTS_DIR, ROOT, Project

FRAMES = 36
WIDTH, HEIGHT = 720, 450


def _serve(root: Path) -> tuple[socketserver.TCPServer, int]:
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(root), **k)  # noqa: E731
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def render_gif(p: Project, out: Path | None = None) -> Path:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    out = out or (p.charts_dir / "globe.gif")
    httpd, port = _serve(ROOT)
    frames: list[Image.Image] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
            url = f"http://127.0.0.1:{port}/site/index.html?project={p.name}&ui=0&spin=0&bg=0&alt=1.9&lng=-20"
            page.goto(url, wait_until="networkidle")
            page.wait_for_function("window.__globeReady === true", timeout=60000)
            page.wait_for_timeout(2500)  # textures + heatmap settle
            for i in range(FRAMES):
                lng = -20 + 360 * i / FRAMES
                page.evaluate("lng => { const g = window.__globe; if (g) g.pointOfView({lat: 25, lng, altitude: 1.9}, 0); }", lng)
                page.wait_for_timeout(120)
                png = page.screenshot(type="png")
                frames.append(Image.open(__import__("io").BytesIO(png)).convert("RGB").quantize(colors=96, method=Image.Quantize.MEDIANCUT))
            browser.close()
    finally:
        httpd.shutdown()
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=100, loop=0, optimize=True)
    return out
