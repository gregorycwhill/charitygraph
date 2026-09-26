"""Bounded public seed acquisition and representation preflight (no providers)."""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import sys
sys.path.insert(0, "src")
from charitygraph.document_representation import represent_document

ROOT = Path(r"C:\CharityGraph-runtime\broad-compact-diagnostic-v12")
RAW = ROOT / "raw"
SEEDS = {
    "The Smith Family": "https://www.thesmithfamily.com.au/media/research/reports",
    "Australian Red Cross Society": "https://www.redcross.org.au/publications/annual-reports/",
    "Australian Communities Foundation Limited": "https://communityfoundation.org.au/about/publications/",
    "Australian Conservation Foundation Incorporated": "https://www.acf.org.au/about/our-organisation/annual-reports",
    "Mission Australia": "https://www.missionaustralia.com.au/who-we-are/our-governance/annual-report/",
    "World Vision Australia": "https://www.worldvision.com.au/our-work/about-us/annual-reports",
    "The Fred Hollows Foundation": "https://www.hollows.org/what-we-do/annual-reports/",
    "Landscape Recovery Foundation Ltd.": "https://landscaperecovery.com.au/",
    "Indigenous Literacy Foundation Ltd.": "https://www.indigenousliteracyfoundation.org.au/reports",
    "Life Without Barriers": "https://www.lwb.org.au/",
    "Life Without Barriers regulator": "https://www.ndiscommission.gov.au/node/1532",
}

def fetch(url):
    try:
        with urlopen(Request(url, headers={"User-Agent": "CharityGraph research client/1.0"}), timeout=30) as r:
            return r.read(), r.headers.get_content_type(), r.geturl(), None
    except Exception as exc:
        return b"", None, None, f"{type(exc).__name__}: {exc}"

def main():
    ROOT.mkdir(parents=True, exist_ok=True); RAW.mkdir(exist_ok=True)
    rows, packets = [], []
    for target, seed in SEEDS.items():
        body, ctype, final, error = fetch(seed)
        row = {"target": target, "requested_url": seed, "final_url": final,
               "publisher": urlparse(seed).netloc, "source_relation": "regulator" if "regulator" in target else "first_party",
               "material_role": "regulator_or_compliance" if "regulator" in target else "annual_report",
               "origin_kind": "fresh_web", "status": "failed" if error else "success", "error": error, "artifacts": []}
        rows.append(row)
        if error: continue
        links = [urljoin(final, x) for x in re.findall(r'href=["\']([^"\']+)', body.decode("utf-8", "ignore"), re.I)]
        links = [u for u in links if urlparse(u).netloc == urlparse(final).netloc and urlparse(u).path.lower().endswith((".pdf", ".html", ".htm"))]
        for idx, url in enumerate([final] + links[:3], 1):
            data, ct, resolved, err = (body, ctype, final, None) if idx == 1 else fetch(url)
            if err or not data: continue
            rep = represent_document(data, content_type=ct); raw_sha = hashlib.sha256(data).hexdigest()
            ext = ".pdf" if "pdf" in (ct or "") or data.startswith(b"%PDF-") else ".html"
            path = RAW / f"{re.sub(r'[^A-Za-z0-9]', '_', target)}-{idx}{ext}"; path.write_bytes(data)
            row["artifacts"].append({"url": resolved, "raw_path": str(path), "raw_sha256": raw_sha, "content_type": ct, "representation_sha256": rep.representation_sha256, "representation_method": rep.method, "complete": rep.complete, "gap": rep.gap, "units": len(rep.units), "characters": len(rep.text)})
            if rep.complete and rep.text.strip(): packets.append({"target": target, "source_url": resolved, "material_role": row["material_role"], "raw_sha256": raw_sha, "representation_sha256": rep.representation_sha256, "locators": len(rep.units)})
    (ROOT / "acquisition-preflight.json").write_text(json.dumps({"campaign": "broad-compact-diagnostic-v12", "provider_calls": 0, "targets": list(SEEDS), "rows": rows, "prepared_packets": packets}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"attempts": len(rows), "successes": sum(r["status"] == "success" for r in rows), "prepared_packets": len(packets), "provider_calls": 0}, indent=2))

if __name__ == "__main__": main()
