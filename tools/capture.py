"""Capture README media from the web viewer (needs `pip install playwright` and a Chrome/Chromium).

Writes to docs/: viewer-<model>.png, viewer-<model>-clay.png / -wireframe.png, angles-<model>.png
(front / 3-4 / side / back), before-after-<model>.png and a 360 turntable (turntable.mp4 + .gif).

Usage: python -m http.server 8765 &  then  python tools/capture.py --chrome /usr/bin/google-chrome
"""
import argparse
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
STAGE_ONLY = ("header,aside,.info,.toolbar,footer,.compare,.modes,.badge{display:none!important}"
              "main{display:block!important;padding:0!important;height:100vh!important}"
              ".stage{height:100vh;border:0;border-radius:0}")
ANGLES = [("Front", "0deg 78deg 145%"), ("3/4", "30deg 74deg 145%"), ("Side", "90deg 78deg 145%"),
          ("Back", "180deg 78deg 145%")]


def ff(*args):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


def open_model(browser, name, url, size=(1440, 860), stage_only=False):
    page = browser.new_page(viewport={"width": size[0], "height": size[1]})
    page.goto(f"{url}/viewer/index.html#{name}")
    page.wait_for_function("document.getElementById('mv').loaded === true", timeout=90000)
    page.evaluate("document.getElementById('mv').autoRotate=false")
    if stage_only:
        page.add_style_tag(content=STAGE_ONLY)
    page.wait_for_timeout(1200)
    return page


def set_orbit(page, orbit):
    page.evaluate(f"const m=document.getElementById('mv'); m.cameraOrbit='{orbit}'; m.jumpCameraToGoal()")
    page.wait_for_timeout(250)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--models", default="vase,box,chest,potion,sneaker")
    ap.add_argument("--hero", default="vase", help="model used for clay/wireframe/before-after shots")
    ap.add_argument("--frames", type=int, default=72)
    a = ap.parse_args()
    docs, out = ROOT / "docs", ROOT / "out"
    docs.mkdir(exist_ok=True)
    names = a.models.split(",")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=a.chrome, headless=True, args=ARGS)
        for n in names:
            page = open_model(b, n, a.url)
            page.screenshot(path=str(docs / f"viewer-{n}.png"))
            if n == a.hero:
                for m in ("clay", "wireframe"):
                    page.evaluate(f"applyMode('{m}')")
                    page.wait_for_timeout(600)
                    page.screenshot(path=str(docs / f"viewer-{n}-{m}.png"))
            page.close()
        # multi-angle sheets + before/after + turntable frames
        tiles = []
        for n in names:
            page = open_model(b, n, a.url, size=(720, 720), stage_only=True)
            adir = out / f"angles_{n}"
            adir.mkdir(parents=True, exist_ok=True)
            for i, (_, orbit) in enumerate(ANGLES):
                set_orbit(page, orbit)
                page.screenshot(path=str(adir / f"{i}.png"))
            fdir = out / f"turn_{n}"
            fdir.mkdir(parents=True, exist_ok=True)
            for i in range(a.frames):
                set_orbit(page, f"{i * 360 / a.frames}deg 72deg 145%")
                page.screenshot(path=str(fdir / f"{i:03d}.png"))
            page.close()
            labels = "".join(
                f"[{i}:v]scale=480:480,drawtext=text='{lab}':fontcolor=white@0.85:fontsize=22:x=18:y=16[a{i}];"
                for i, (lab, _) in enumerate(ANGLES))
            ff(*sum((["-i", str(adir / f"{i}.png")] for i in range(4)), []), "-filter_complex",
               labels + "[a0][a1][a2][a3]hstack=4", str(docs / f"angles-{n}.png"))
            inp = ROOT / "examples" / "models" / n / f"{n}_input.png"
            ff("-i", str(inp), "-i", str(adir / "0.png"), "-filter_complex",
               "[0:v]scale=640:640:force_original_aspect_ratio=decrease,pad=640:640:(ow-iw)/2:(oh-ih)/2:color=0xf2f2f2[a];"
               "[1:v]scale=640:640[b];[a][b]hstack=2", str(docs / f"before-after-{n}.png"))
            mp4 = out / f"turntable-{n}.mp4"
            ff("-framerate", "24", "-i", str(fdir / "%03d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(mp4))
            tiles.append(mp4)
        b.close()
    inputs = sum((["-i", str(t)] for t in tiles), [])
    stack = "".join(f"[{i}:v]scale=360:360[v{i}];" for i in range(len(tiles))) + \
        "".join(f"[v{i}]" for i in range(len(tiles))) + f"hstack={len(tiles)}"
    ff(*inputs, "-filter_complex", stack, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", str(docs / "turntable.mp4"))
    ff("-i", str(docs / "turntable.mp4"), "-vf",
       "fps=12,scale=1080:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
       str(docs / "turntable.gif"))
    print("media written to", docs)


if __name__ == "__main__":
    main()
