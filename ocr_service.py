"""ONE TAP OCR service (Tesseract).

A separate, OCR-only service. It does NOT load the card index or CLIP, so it starts fast and
uses little memory, and it cannot affect the live recognition service.

POST /ocr  (multipart form)
  file: the card photo (JPEG/PNG)
  lang: Tesseract language code, e.g. "eng", "jpn" or "eng+jpn" (default "eng")
Returns: { "ok": bool, "text": str, "engine": "tesseract" }

GET /  returns a health message, so you can check the service is up.
"""
import io
import pytesseract
from PIL import Image, ImageOps
from fastapi import FastAPI, UploadFile, File, Form

app = FastAPI()


def _read(img, lang):
    """Run Tesseract on one image. Returns "" on any failure rather than raising."""
    try:
        gray = ImageOps.autocontrast(img.convert("L"))
        # Enlarge small images so the small print (the collector number) is readable.
        if gray.width < 1200:
            scale = 1200 / float(max(gray.width, 1))
            gray = gray.resize((int(gray.width * scale), int(gray.height * scale)), Image.LANCZOS)
        return pytesseract.image_to_string(gray, lang=lang, config="--psm 11") or ""
    except Exception as e:
        print(f"[ocr] tesseract error ({lang}): {e}")
        return ""


def read_card(img, lang="eng"):
    """Two passes, joined: the whole card (name and set text), and the bottom 30% enlarged
    (where the collector number sits)."""
    w, h = img.size
    full = _read(img, lang)
    bottom = _read(img.crop((0, int(h * 0.70), w, h)), lang)
    return (full + "\n" + bottom).strip()


@app.get("/")
def health():
    return {"status": "ok", "engine": "tesseract"}


@app.post("/ocr")
async def ocr(file: UploadFile = File(...), lang: str = Form(default="eng")):
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(await file.read()))).convert("RGB")
    except Exception as e:
        return {"ok": False, "text": "", "engine": "tesseract", "error": f"bad image: {e}"}
    text = read_card(img, lang=(lang or "eng").strip())
    return {"ok": bool(text), "text": text, "engine": "tesseract"}
