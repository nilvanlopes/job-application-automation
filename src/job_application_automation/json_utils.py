from __future__ import annotations

import json


def parse_strict_json_object(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        raise json.JSONDecodeError("Resposta vazia", text, 0)

    candidate = _extract_json_object_fragment(stripped)
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("Resposta não contém um objeto JSON válido", candidate, 0)
    return parsed


def _extract_json_object_fragment(text: str) -> str:
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("Resposta não contém um objeto JSON", text, 0)
    return text[start : end + 1]
