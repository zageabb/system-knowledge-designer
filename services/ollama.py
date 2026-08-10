from __future__ import annotations

import json
import re

import requests


class OllamaError(RuntimeError): pass


class OllamaClient:
    def __init__(self, base_url: str, timeout: int = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate_json(self, model: str, prompt: str) -> dict:
        try:
            response = requests.post(f"{self.base_url}/api/generate", json={"model": model, "prompt": prompt, "stream": False, "format": "json"}, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc: raise OllamaError(f"Ollama request failed: {exc}") from exc
        raw = str(response.json().get("response", "")).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw); raw = re.sub(r"\s*```$", "", raw)
        start = min([position for position in (raw.find("{"), raw.find("[")) if position >= 0], default=0)
        try: return json.loads(raw[start:])
        except json.JSONDecodeError as exc: raise OllamaError(f"Ollama returned invalid JSON: {exc}") from exc

