"""Local web app: serves the viewer and converts uploaded images. Run: python -m studio.server"""
from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .pipeline import ImageTo3D, Options

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "outputs" / "web"
MAX_BYTES = 15 * 1024 * 1024

app = FastAPI(title="Image to 3D Studio")
_engine: ImageTo3D | None = None
_lock = threading.Lock()


def engine() -> ImageTo3D:
    global _engine
    if _engine is None:
        _engine = ImageTo3D(Options())
    return _engine


@app.get("/")
def index():
    return RedirectResponse("/viewer/index.html")


@app.post("/api/convert")
def convert(image: UploadFile = File(...)):
    if not (image.content_type or "").startswith("image/"):
        raise HTTPException(400, "please upload an image")
    job = uuid.uuid4().hex[:8]
    out = JOBS / job
    out.mkdir(parents=True, exist_ok=True)
    src = out / f"upload{Path(image.filename or 'x.png').suffix.lower() or '.png'}"
    with src.open("wb") as fh:
        shutil.copyfileobj(image.file, fh, length=MAX_BYTES)
    name = Path(image.filename or "model").stem[:40] or "model"
    with _lock:  # one reconstruction at a time keeps RAM predictable on CPU boxes
        result = engine().convert(src, out, name=name)
    result["source"] = image.filename
    result["base"] = f"/outputs/web/{job}/"
    return result


JOBS.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=ROOT / "outputs"), name="outputs")
app.mount("/examples", StaticFiles(directory=ROOT / "examples"), name="examples")
app.mount("/viewer", StaticFiles(directory=ROOT / "viewer"), name="viewer")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
