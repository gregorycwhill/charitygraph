import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


def module():
    path = Path(__file__).resolve().parents[1] / "examples/questionnaire_x4a/build_preview.py"
    spec = importlib.util.spec_from_file_location("x4a_preview", path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


@pytest.fixture
def preview(tmp_path):
    m = module()
    if not (m.TEMP / "charitygraph-x3b-20261123/paired-review.json").exists():
        pytest.skip("private frozen experiments unavailable")
    m.main(tmp_path)
    return tmp_path


def test_real_overlay_scope_status_and_privacy(preview):
    text = (preview / "preview-data.json").read_text(encoding="utf8")
    data = json.loads(text); plan, arche = data["charities"]
    assert [x["id"] for x in data["charities"]] == ["plan", "arche"]
    assert plan["finance"]["amount"] > 0 and "finance" not in arche
    assert len(plan["programs"]) == 2 and len(arche["programs"]) == 1
    assert all("finance" not in p and len(p["answers"]) == 5 for p in plan["programs"])
    assert all(sum(a["value"] == "Unknown" for a in p["answers"]) == 3 for p in plan["programs"])
    answers = arche["programs"][0]["answers"]
    assert all("2017–18" in a["period"] for a in answers)
    assert answers[-1]["value"] == "Insufficiently established" and "model selected supported" in answers[-1]["note"]
    assert "probabilities" not in text and "confidence" not in text and "source_references" not in text
    assert "C:\\" not in text and "AppData" not in text and "file://" not in text
    assert all(s["url"].startswith("https://") for c in data["charities"] for s in c["sources"])
    assert len(json.loads((preview / "x4b-cohort-manifest.json").read_text(encoding="utf8"))["charities"]) == 12


def test_browser_script_switches_charities_and_escapes_text(preview):
    if not shutil.which("node"): pytest.skip("node unavailable")
    harness = r'''
const fs = require("fs"), vm = require("vm"), path = require("path");
class Node {
  constructor(tag) { this.tag=tag; this.children=[]; this.textContent=""; this.className=""; this.listeners={}; this.classList={toggle(){}}; }
  append(...v) { this.children.push(...v); } replaceChildren(...v) { this.children=[...v]; }
  setAttribute(k,v) { this[k]=v; } addEventListener(k,v) { this.listeners[k]=v; }
}
const dir=process.argv[1], results=new Node("results"), card=new Node("card");
const document={getElementById(id){return id==="results"?results:card},createElement(tag){return new Node(tag)}};
const data=JSON.parse(fs.readFileSync(path.join(dir,"preview-data.json"),"utf8"));
const context={document,window:{X4A_DATA:data},Intl};
vm.runInNewContext(fs.readFileSync(path.join(dir,"preview.js"),"utf8"),context);
const text=n=>[n.textContent,...n.children.flatMap(c=>[text(c)])].join(" ");
if(results.children.length!==2 || !text(card).includes(data.charities[0].name)) throw Error("Plan failed");
results.children[1].listeners.click();
const rendered=text(card);
if(!rendered.includes(data.charities[1].name) || !rendered.includes("Insufficiently established") || rendered.includes("Fundraising expenditure")) throw Error("Arche failed");
'''
    subprocess.run(["node", "-e", harness, str(preview)], check=True, capture_output=True, text=True)


def test_saved_preview_matches_frozen_inputs():
    path = os.environ.get("X4A_SAVED_PREVIEW")
    if not path: pytest.skip("saved private preview path not provided")
    saved = Path(path); m = module()
    x2=m.TEMP/"charitygraph-x2-plan-20261123"; x3=m.TEMP/"charitygraph-x3-20261123"; x3b=m.TEMP/"charitygraph-x3b-20261123"
    m.verify_set(x2,["answers.json"]); m.verify_set(x3,["x3-results.json"]); m.verify_set(x3b,["paired-review.json"])
    source=m.read(m.E5/"execution/49004875807-B-request.json")
    parts=json.loads(source["input"].split("Evidence candidates (JSON object; only IDs appearing as keys are present):\n",1)[1])
    expected=m.build_overlay(m.read(x2/"answers.json"),m.read(x3/"x3-results.json"),m.read(x3b/"paired-review.json"),parts["A01"]["data"],m.sources())
    assert m.read(saved/"preview-data.json") == expected
    assert (saved/"data.js").read_text(encoding="utf8") == "window.X4A_DATA = "+json.dumps(expected,ensure_ascii=False,indent=2)+";\n"
    assert m.read(saved/"x4b-cohort-manifest.json") == m.cohort()
    for name in ("index.html","preview.js","preview.css"):
        assert (saved/name).read_bytes() == (m.HERE/name).read_bytes()
    assert (saved/"viewer-base.css").read_bytes() == (m.ROOT.parent/"charitygraph-viewer/styles.css").read_bytes()
    test_real_overlay_scope_status_and_privacy(saved)
    test_browser_script_switches_charities_and_escapes_text(saved)
    cohort=m.read(saved/"x4b-cohort-manifest.json")
    assert cohort["status"] == "proposed_not_frozen_or_approved_for_calls"
    assert len({item["abn"] for item in cohort["charities"]}) == 12
    assert all("2024 ACNC AIS" in item["source_families_captured"] for item in cohort["charities"])
    assert {"program-rich", "relatively simple", "captured source-rich", "captured source-poor"} <= {tag for item in cohort["charities"] for tag in item["selection_tags"]}
