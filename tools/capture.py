"""Capture README media from the web viewer: UI screenshots + turntable frames (needs `pip install playwright`).

Usage: python -m http.server 8765 &  then  python tools/capture.py --chrome /usr/bin/google-chrome
"""
import argparse
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]


def open_model(browser, name, url, size=(1440, 860)):
    page = browser.new_page(viewport={"width": size[0], "height": size[1]})
    page.goto(f"{url}/viewer/index.html#{name}")
    page.wait_for_function("document.getElementById('mv').loaded === true", timeout=60000)
    page.evaluate("document.getElementById('mv').autoRotate=false")
    page.wait_for_timeout(1200)
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--models", default="robot,sneaker,mug")
    ap.add_argument("--frames", type=int, default=60)
    a = ap.parse_args()
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    names = a.models.split(",")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=a.chrome, headless=True, args=ARGS)
        for n in names:
            page = open_model(b, n, a.url)
            page.screenshot(path=str(docs / f"viewer-{n}.png"))
            page.close()
        # turntables: hide the UI chrome and spin the camera
        tiles = []
        for n in names:
            page = open_model(b, n, a.url, size=(720, 720))
            page.add_style_tag(content="header,aside,.info,.toolbar,footer{display:none!important}"
                                       "main{display:block!important;padding:0!important;height:100vh!important}"
                                       ".stage{height:100vh;border:0;border-radius:0}")
            page.wait_for_timeout(800)
            fdir = ROOT / "out" / f"turn_{n}"
            fdir.mkdir(parents=True, exist_ok=True)
            for i in range(a.frames):
                page.evaluate(f"document.getElementById('mv').cameraOrbit='{i * 360 / a.frames}deg 76deg 105%';"
                              "document.getElementById('mv').jumpCameraToGoal()")
                page.wait_for_timeout(120)
                page.screenshot(path=str(fdir / f"{i:03d}.png"))
            page.close()
            mp4 = ROOT / "out" / f"turntable-{n}.mp4"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "24", "-i", str(fdir / "%03d.png"),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(mp4)], check=True)
            tiles.append(mp4)
        b.close()
    # side-by-side turntable of all models -> mp4 + gif
    inputs = sum((["-i", str(t)] for t in tiles), [])
    stack = "".join(f"[{i}:v]scale=360:360[v{i}];" for i in range(len(tiles))) + \
        "".join(f"[v{i}]" for i in range(len(tiles))) + f"hstack={len(tiles)}"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", stack, "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "22", str(docs / "turntable.mp4")], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(docs / "turntable.mp4"), "-vf",
                    "fps=12,scale=900:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                    str(docs / "turntable.gif")], check=True)
    print("media written to", docs)


if __name__ == "__main__":
    main()
