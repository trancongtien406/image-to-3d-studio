"""Screenshots of the delivery features (before/after slider, 3 views, print panel, share + QR, share page).

Usage: python -m http.server 8765 &  then  python tools/capture_features.py --chrome /usr/bin/google-chrome
"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]


def open_model(b, url, name, size=(1520, 900)):
    page = b.new_page(viewport={"width": size[0], "height": size[1]}, device_scale_factor=1)
    page.goto(f"{url}/viewer/index.html#{name}")
    page.wait_for_function("document.getElementById('mv').loaded === true", timeout=90000)
    page.evaluate("document.getElementById('mv').autoRotate=false")
    page.wait_for_timeout(1500)
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--chrome", default=None)
    a = ap.parse_args()
    docs = ROOT / "docs"
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=a.chrome, headless=True, args=ARGS)
        page = open_model(b, a.url, "chest")
        page.evaluate("document.getElementById('mv').cameraOrbit='25deg 74deg 145%'")
        page.fill("#hIn", "150")
        page.dispatch_event("#hIn", "input")
        page.wait_for_timeout(800)
        page.screenshot(path=str(docs / "studio-print-panel.png"))
        page.locator(".info").screenshot(path=str(docs / "print-report-chest.png"))
        page.evaluate("setTab('ba')")
        page.wait_for_timeout(900)
        page.evaluate("setSplit(50)")
        page.wait_for_timeout(300)
        page.screenshot(path=str(docs / "before-after-slider.png"))
        page.evaluate("setTab('views')")
        page.wait_for_function("document.getElementById('views').dataset.ready === '1'", timeout=60000)
        page.wait_for_timeout(600)
        page.screenshot(path=str(docs / "three-views.png"))
        page.evaluate("setTab('3d')")
        page.click("#shareBtn")
        page.wait_for_timeout(500)
        page.screenshot(path=str(docs / "share-qr-embed.png"))
        page.close()
        for n in ("sneaker", "vase"):
            sp = b.new_page(viewport={"width": 1280, "height": 800})
            sp.goto(f"{a.url}/viewer/share.html?src=../examples/models/{n}/{n}.glb&name={n}")
            sp.wait_for_function("document.getElementById('mv').loaded === true", timeout=90000)
            sp.evaluate("document.getElementById('mv').autoRotate=false")
            sp.wait_for_timeout(1500)
            sp.screenshot(path=str(docs / f"share-page-{n}.png"))
            sp.close()
        b.close()
    print("written to", docs)


if __name__ == "__main__":
    main()
