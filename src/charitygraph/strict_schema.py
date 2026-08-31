"""Small deterministic preflight for OpenAI strict structured-output schemas."""

from __future__ import annotations

from typing import Any


def strictify_schema(node: Any) -> Any:
    """Convert a Pydantic schema to the repository's strict-output shape."""
    if isinstance(node, dict):
        out = {key: strictify_schema(value) for key, value in node.items() if key != "default"}
        if out.get("enum") == []:
            out.pop("enum", None)
        if out.get("type") == "object" and "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out["properties"])
        return out
    if isinstance(node, list):
        values = []
        for value in node:
            # OpenAI strict Structured Outputs does not support arbitrary
            # recursive map branches.  They are represented by an object with
            # schema-valued additionalProperties and must be omitted from the
            # provider wire schema; the Python contract remains unchanged.
            if isinstance(value, dict) and value.get("type") == "object" and "properties" not in value and isinstance(value.get("additionalProperties"), dict):
                continue
            strict_value = strictify_schema(value)
            # Pydantic can emit annotation-only union branches (for example an
            # Enum branch represented solely by description/title).  They are
            # not JSON Schema nodes and the provider rejects them for lacking
            # a type.  Preserve the Python contract while omitting only this
            # demonstrated malformed transport branch.
            if isinstance(strict_value, dict) and not any(key in strict_value for key in ("type", "$ref", "anyOf", "oneOf", "allOf", "enum", "const", "properties")):
                continue
            values.append(strict_value)
        return values
    return node


def validate_strict_schema(schema: dict[str, Any]) -> None:
    """Reject the bounded classes of request defects caught before dispatch."""
    def walk(node: Any, path: str = "$", parent: dict[str, Any] | None = None) -> None:
        if isinstance(node, dict):
            if "default" in node:
                raise ValueError(f"strict schema contains unsupported default at {path}")
            if node.get("enum") == []:
                raise ValueError(f"strict schema contains empty enum at {path}")
            if node.get("type") == "object":
                props = node.get("properties")
                required = node.get("required")
                if not isinstance(props, dict):
                    # A typed map (used by CanonicalValue) has no fixed
                    # properties; retain it for the contract rather than
                    # misclassifying it as the fixed-object error this
                    # preflight is intended to catch.
                    if isinstance(node.get("additionalProperties"), dict):
                        raise ValueError(f"strict schema contains unsupported typed-map branch at {path}")
                    raise ValueError(f"object schema lacks properties at {path}")
                if node.get("additionalProperties") is not False:
                    raise ValueError(f"object schema must set additionalProperties=false at {path}")
                if not isinstance(required, list) or set(required) != set(props):
                    raise ValueError(f"required properties must exactly match properties at {path}")
            for key, value in node.items():
                walk(value, f"{path}.{key}", node)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                if isinstance(parent, dict) and any(key in parent for key in ("anyOf", "oneOf", "allOf")) and isinstance(value, dict) and not any(key in value for key in ("type", "$ref", "anyOf", "oneOf", "allOf", "enum", "const", "properties")):
                    raise ValueError(f"schema branch lacks a type at {path}[{index}]")
                walk(value, f"{path}[{index}]", parent)
    walk(schema)


__all__ = ["strictify_schema", "validate_strict_schema"]
