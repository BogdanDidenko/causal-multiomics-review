from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any

import certifi


class ProviderError(RuntimeError):
    def __init__(self, message: str, raw_response: Any | None = None) -> None:
        self.raw_response = raw_response
        super().__init__(message)


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 180,
        temperature: float = 0.0,
        top_p: float = 1.0,
        seed: int = 0,
        n: int = 1,
        max_tokens: int | None = None,
        response_format: str = "json_object",
    ) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.top_p = top_p
        self.seed = seed
        self.n = n
        self.max_tokens = max_tokens
        self.response_format = response_format

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        schema_name: str = "screening_response",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "seed": self.seed,
            "n": self.n,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.response_format == "json_schema" and schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            }
        else:
            payload["response_format"] = {"type": "json_object"}
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
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors="replace")
            raise ProviderError(
                f"HTTP {error.code}: {body[:1000]}", raw_response=body
            ) from error
        except (urllib.error.URLError, json.JSONDecodeError) as error:
            raise ProviderError(str(error)) from error

        try:
            content = raw["choices"][0]["message"]["content"]
            parsed = json.loads(_strip_code_fence(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ProviderError(
                f"Invalid provider response: {error}", raw_response=raw
            ) from error
        if not isinstance(parsed, dict):
            raise ProviderError("Model response is not a JSON object", raw_response=raw)
        return parsed, raw


def _strip_code_fence(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    return text.strip()
