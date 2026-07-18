from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any

import certifi


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 180) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=ssl.create_default_context(cafile=certifi.where()),
            ) as response:
                raw = json.loads(response.read())
        except (urllib.error.URLError, json.JSONDecodeError) as error:
            raise ProviderError(str(error)) from error

        try:
            content = raw["choices"][0]["message"]["content"]
            parsed = json.loads(_strip_code_fence(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ProviderError(f"Invalid provider response: {error}") from error
        if not isinstance(parsed, dict):
            raise ProviderError("Model response is not a JSON object")
        return parsed, raw


def _strip_code_fence(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    return text.strip()
