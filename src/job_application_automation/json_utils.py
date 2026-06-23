from __future__ import annotations

import json


def parse_strict_json_object(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        raise json.JSONDecodeError("Resposta vazia", text, 0)

    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("Resposta não contém um objeto JSON válido", stripped, 0)
    return parsed
