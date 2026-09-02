"""Reusable raw-document to readable-representation boundary."""
from __future__ import annotations
from dataclasses import dataclass
from html.parser import HTMLParser
import hashlib, io

@dataclass(frozen=True)
class DocumentRepresentation:
    material_type: str
    representation_type: str
    text: str
    raw_sha256: str
    representation_sha256: str
    method: str
    complete: bool
    gap: str | None = None
    units: tuple[dict, ...] = ()

class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script","style","noscript","template","nav","footer"}: self.skip += 1
    def handle_endtag(self, tag):
        if tag.lower() in {"script","style","noscript","template","nav","footer"} and self.skip: self.skip -= 1
    def handle_data(self, data):
        if not self.skip and data.strip(): self.parts.append(data.strip())

def represent_document(raw: bytes, *, content_type: str | None = None) -> DocumentRepresentation:
    raw_sha = hashlib.sha256(raw).hexdigest()
    ctype = (content_type or "").lower()
    if raw.startswith(b"%PDF-") or "application/pdf" in ctype:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            text = "\n\n".join(p for p in pages if p.strip())
            if not text.strip():
                return DocumentRepresentation("pdf", "pdf_text", "", raw_sha, hashlib.sha256(b"").hexdigest(), "pdfplumber", False, "image_only_or_scanned", tuple({"kind":"page","page":i+1,"text":t} for i,t in enumerate(pages)))
            method = "pdfplumber"
        except Exception as exc:
            return DocumentRepresentation("pdf", "none", "", raw_sha, hashlib.sha256(b"").hexdigest(), "pdfplumber", False, f"pdf_extraction_failed:{type(exc).__name__}")
        material = "pdf"; units=tuple({"kind":"page","page":i+1,"text":t} for i,t in enumerate(pages))
    else:
        ctype_ok = ctype in {"text/html", "application/xhtml+xml", "text/plain", "text/markdown", "application/json"}
        markup = b"<html" in raw[:4096].lower() or b"<!doctype html" in raw[:4096].lower()
        if not (ctype_ok or markup):
            return DocumentRepresentation("unknown", "none", "", raw_sha, hashlib.sha256(b"").hexdigest(), "none", False, "unsupported_binary_or_content_type")
        if ctype == "application/json":
            return DocumentRepresentation("json", "none", "", raw_sha, hashlib.sha256(b"").hexdigest(), "none", False, "structured_json_not_prose")
        if ctype in {"text/plain", "text/markdown"} and not markup:
            text = raw.decode("utf-8", errors="strict")
            if any(ord(ch) < 9 or (13 < ord(ch) < 32) for ch in text):
                return DocumentRepresentation("text", "none", "", raw_sha, hashlib.sha256(b"").hexdigest(), "text_utf8", False, "binary_control_content")
            method = "text_utf8"; material = "text"
        else:
            parser = _TextParser(); parser.feed(raw.decode("utf-8", errors="strict")); text = "\n".join(parser.parts); method = "html_parser"; material = "html"
    rep_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if material == "html": units=tuple({"kind":"line","line":i+1,"text":line} for i,line in enumerate(text.splitlines()) if line)
    elif material == "text": units=tuple({"kind":"line","line":i+1,"text":line} for i,line in enumerate(text.splitlines()) if line)
    return DocumentRepresentation(material, "readable_text", text, raw_sha, rep_sha, method, True, None, units)
