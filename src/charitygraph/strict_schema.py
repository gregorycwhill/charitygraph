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
        return [strictify_schema(value) for value in node]
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
                        return
                    raise ValueError(f"object schema lacks properties at {path}")
                if node.get("additionalProperties") is not False:
                    raise ValueError(f"object schema must set additionalProperties=false at {path}")
                if not isinstance(required, list) or set(required) != set(props):
                    raise ValueError(f"required properties must exactly match properties at {path}")
            for key, value in node.items():
                walk(value, f"{path}.{key}", node)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]", parent)
    walk(schema)


__all__ = ["strictify_schema", "validate_strict_schema"]
