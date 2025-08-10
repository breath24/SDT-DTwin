from __future__ import annotations

import json


def extract_first_json_object(text: str) -> dict:
    if not text:
        return {}
    # Fast path: attempt full parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to locate the first JSON object using a simple brace matching
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # Try to find the first balanced object with incremental scanning
    depth = 0
    start_idx = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start_idx = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start_idx is not None:
                candidate = text[start_idx : i + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    start_idx = None
                    continue
    return {}


