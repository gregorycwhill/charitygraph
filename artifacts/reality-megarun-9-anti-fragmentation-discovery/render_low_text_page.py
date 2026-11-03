"""Disposable local representation diagnostic; no network or semantic inference."""
from pathlib import Path
import fitz

sha = "87546383d699c7b8e4119e9fc95e13eeef7343dfa6147c37f9155cf94358ac5b"
archive = Path(r"C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\Source Archive")
pdf = next((archive / "objects").rglob(sha + ".pdf"))
out = Path(__file__).parent / "representation-diagnostics"
out.mkdir(exist_ok=True)
doc = fitz.open(pdf)
# ARC page 27 is zero-indexed page 26.
pix = doc[26].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
target = out / "australian-red-cross-27-render.png"
pix.save(target)
print(target, target.stat().st_size)
