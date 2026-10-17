"""Mechanical representations and payload choices for provider transmission.

Permission to transmit is decided in :mod:`source_rights`. This module only
preserves source-native content and records a cost/latency payload choice.
"""
from __future__ import annotations

import io
import zipfile
from typing import Any
from xml.etree import ElementTree

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def render_complete_workbook(workbook_bytes: bytes, source_artifact_id: str) -> dict[str, Any]:
    """Render every nonempty cell; sparse encoding is not a sheet/range cap."""
    archive = zipfile.ZipFile(io.BytesIO(workbook_bytes))
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    relations = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {item.attrib["Id"]: item.attrib["Target"].lstrip("/") for item in relations.findall(f"{{{_PKG_REL}}}Relationship")}
    if "xl/sharedStrings.xml" in archive.namelist():
        shared = ["".join(item.itertext()) for item in ElementTree.fromstring(archive.read("xl/sharedStrings.xml")).findall(f"{{{_MAIN}}}si")]
    else:
        shared = []
    sheets: list[dict[str, Any]] = []
    for sheet in workbook.findall(f".//{{{_MAIN}}}sheet"):
        target = targets[sheet.attrib[f"{{{_REL}}}id"]]
        path = target if target.startswith("xl/") else f"xl/{target}"
        root = ElementTree.fromstring(archive.read(path))
        cells = []
        for cell in root.findall(f".//{{{_MAIN}}}c"):
            formula = cell.find(f"{{{_MAIN}}}f")
            value_node = cell.find(f"{{{_MAIN}}}v")
            inline = cell.find(f"{{{_MAIN}}}is")
            if formula is not None:
                value: Any = "=" + (formula.text or "")
            elif inline is not None:
                value = "".join(inline.itertext())
            elif value_node is None:
                continue
            elif cell.attrib.get("t") == "s":
                value = shared[int(value_node.text or "0")]
            else:
                value = value_node.text or ""
            cells.append({"coordinate": cell.attrib["r"], "value": value})
        sheets.append({"title": sheet.attrib["name"], "cells": cells})
    return {"representation_kind": "complete_source_native_workbook", "source_artifact_id": source_artifact_id, "sheets": sheets}


def payload_selection(*, candidate_representation_artifact_id: str, selection_reason: str) -> dict[str, str]:
    """Record an exact payload choice without implying a rights limitation."""
    if selection_reason not in {"economic_optimization", "transport_rendering"}:
        raise ValueError("payload selection reason must be economic_optimization or transport_rendering")
    return {"candidate_representation_artifact_id": candidate_representation_artifact_id, "selection_reason": selection_reason}
