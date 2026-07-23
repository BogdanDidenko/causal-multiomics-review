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
        api_protocol: str = "chat_completions",
        reasoning_effort: str | None = None,
        text_verbosity: str | None = None,
    ) -> None:
        if api_protocol not in {"chat_completions", "openai_responses"}:
            raise ValueError(f"Unsupported API protocol: {api_protocol}")
        self.api_protocol = api_protocol
        endpoint = "/responses" if api_protocol == "openai_responses" else "/chat/completions"
        self.url = base_url.rstrip("/") + endpoint
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.top_p = top_p
        self.seed = seed
        self.n = n
        self.max_tokens = max_tokens
        self.response_format = response_format
        self.reasoning_effort = reasoning_effort
        self.text_verbosity = text_verbosity

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        schema_name: str = "screening_response",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = self._request_payload(prompt, schema, schema_name)
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
            content = (
                _responses_output_text(raw)
                if self.api_protocol == "openai_responses"
                else raw["choices"][0]["message"]["content"]
            )
            parsed = json.loads(_strip_code_fence(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ProviderError(
                f"Invalid provider response: {error}", raw_response=raw
            ) from error
        if not isinstance(parsed, dict):
            raise ProviderError("Model response is not a JSON object", raw_response=raw)
        return parsed, raw

    def _request_payload(
        self,
        prompt: str,
        schema: dict[str, Any] | None,
        schema_name: str,
    ) -> dict[str, Any]:
        if self.api_protocol == "openai_responses":
            return self._responses_payload(prompt, schema, schema_name)
        return self._chat_completions_payload(prompt, schema, schema_name)

    def _chat_completions_payload(
        self,
        prompt: str,
        schema: dict[str, Any] | None,
        schema_name: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
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
        return payload

    def _responses_payload(
        self,
        prompt: str,
        schema: dict[str, Any] | None,
        schema_name: str,
    ) -> dict[str, Any]:
        text: dict[str, Any] = {}
        if self.text_verbosity is not None:
            text["verbosity"] = self.text_verbosity
        if self.response_format == "json_schema" and schema is not None:
            text["format"] = {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        else:
            text["format"] = {"type": "json_object"}
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [{"role": "user", "content": prompt}],
            "text": text,
        }
        if self.reasoning_effort is not None:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if self.max_tokens is not None:
            payload["max_output_tokens"] = self.max_tokens
        return payload


def _strip_code_fence(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _responses_output_text(raw: dict[str, Any]) -> str:
    output_text = raw.get("output_text")
    if isinstance(output_text, str):
        return output_text
    texts: list[str] = []
    for item in raw.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    texts.append(text)
    if not texts:
        raise KeyError("Response contains no output_text")
    return "".join(texts)
