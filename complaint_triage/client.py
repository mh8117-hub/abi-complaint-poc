"""Minimal Open WebUI client (Python standard library only).

Open WebUI exposes an OpenAI-style chat endpoint at  POST /api/chat/completions
(NOT /v1/chat/completions) with header  Authorization: Bearer <API key>.
Source: https://docs.openwebui.com/getting-started/api-endpoints/
The key is created in Open WebUI: Settings > Account > API Keys.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


class OpenWebUIClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: int = 120):
        self.base_url = (base_url or os.environ.get("OPENWEBUI_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENWEBUI_API_KEY", "")
        self.timeout = timeout
        if not self.base_url:
            raise ValueError("Set OPENWEBUI_BASE_URL (e.g. http://<dgx-host>:8080)")
        if not self.api_key:
            raise ValueError("Set OPENWEBUI_API_KEY (Open WebUI > Settings > Account > API Keys)")

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"HTTP {e.code} from {path}: {detail}") from e

    def list_models(self) -> list:
        data = self._request("GET", "/api/models")
        items = data.get("data", data) if isinstance(data, dict) else data
        return [m.get("id") for m in items if isinstance(m, dict)]

    def chat(self, model: str, messages: list, temperature: float = 0.0, seed: int | None = 42) -> dict:
        body = {"model": model, "messages": messages, "stream": False, "temperature": temperature}
        if seed is not None:
            body["seed"] = seed
        t0 = time.perf_counter()
        data = self._request("POST", "/api/chat/completions", body)
        latency = time.perf_counter() - t0
        return {
            "content": data["choices"][0]["message"]["content"],
            "latency_s": round(latency, 2),
            "usage": data.get("usage"),
            "model_reported": data.get("model"),
        }
